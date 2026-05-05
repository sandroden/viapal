"""Riconcilia BankTransaction con Receivable in modo idempotente.

Procedura:

  0. **Reset (opzionale, ``--reset``)**: cancella *tutte* le
     ``BankTransactionAllocation`` e riporta a ATTESO i Receivable
     correlati. Distruttivo — usato per ripartire da zero quando il matching
     automatico precedente ha prodotto abbinamenti errati.
  1. **Sweep allocations errate**: elimina ``BankTransactionAllocation`` in
     cui la classifica del bonifico (regex su descrizione) differisce dalla
     causale del Receivable allocato. Saltato con ``--reset``.
  2. **Reset Receivable orfani**: i Receivable con ``stato=pagato`` ma senza
     alcuna allocation valida vengono resettati a ATTESO. Saltato con
     ``--reset`` (già fatto al passo 0).
  3. **Match BT non riconciliate** (limitato a ``--causali``): per ogni
     ``BankTransaction`` la cui classifica rientra nelle causali ammesse,
     cerca i Receivable candidati (tenant + causale + finestra) e alloca.

Per default processa solo gli **affitti** (``--causali affitto``): gli
importi dell'affitto sono uguali al dovuto e cadono nel mese di competenza,
quindi il match è affidabile. Le utenze (importi variabili, periodi a
cavallo) si gestiscono a mano dalla pagina di Riconciliazione.

Idempotente: rilanciato dopo l'import di nuovi estratti conto, processa
solo le BT non ancora interpretate. Non duplica allocazioni esistenti.

Uso:
    uv run manage.py riconcilia_bonifici --dry-run
    uv run manage.py riconcilia_bonifici
    uv run manage.py riconcilia_bonifici --reset --causali affitto
    uv run manage.py riconcilia_bonifici --causali affitto,utenze
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from billing.calc.matching import (
    alloca_bonifico,
    classifica_descrizione,
    receivables_compagni,
    trova_receivables_per_bt,
)
from billing.models import BankTransaction, BankTransactionAllocation, Receivable
from billing.models.payments import StatoPagamento

CAUSALI_VALIDE = {
    Receivable.Causale.AFFITTO,
    Receivable.Causale.UTENZE,
    Receivable.Causale.EXTRA,
}


def _reset_receivable(receivable: Receivable) -> None:
    receivable.stato = StatoPagamento.ATTESO
    receivable.data_pagamento = None
    receivable.importo_pagato = None
    receivable.incassato_da_owner = None
    receivable.save(
        update_fields=[
            "stato",
            "data_pagamento",
            "importo_pagato",
            "incassato_da_owner",
            "updated_at",
        ]
    )


class Command(BaseCommand):
    help = "Riconcilia BankTransaction con Receivable (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Non scrive nel DB, mostra solo cosa farebbe.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Distruttivo: cancella TUTTE le allocations e resetta i "
            "Receivable correlati a ATTESO prima del matching.",
        )
        parser.add_argument(
            "--causali",
            default="affitto",
            help="Comma-separated: affitto,utenze,extra (default: affitto).",
        )

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]
        reset = opts["reset"]
        causali_str = (opts["causali"] or "").strip().lower()
        causali_ammesse = {c.strip() for c in causali_str.split(",") if c.strip()}
        invalide = causali_ammesse - CAUSALI_VALIDE
        if invalide:
            self.stderr.write(
                self.style.ERROR(
                    f"Causali non valide: {sorted(invalide)}. "
                    f"Ammesse: {sorted(CAUSALI_VALIDE)}"
                )
            )
            return
        if not causali_ammesse:
            self.stderr.write(self.style.ERROR("Almeno una causale richiesta"))
            return

        self.stdout.write(f"Mode: {'DRY-RUN' if dry_run else 'WRITE'}")
        self.stdout.write(f"Causali ammesse: {sorted(causali_ammesse)}")
        if reset:
            self.stdout.write(self.style.WARNING("Reset: ATTIVO"))
        self.stdout.write("")

        with transaction.atomic():
            n_reset = 0
            n_alloc_errate = 0
            n_reset_orfani = 0
            if reset:
                n_reset = self._reset_tutte_allocations()
            else:
                n_alloc_errate = self._sweep_allocations_errate()
                n_reset_orfani = self._reset_receivable_orfani()
            n_alloc_create, n_bt_processate, n_bt_skip = (
                self._match_bt_non_riconciliate(causali_ammesse)
            )
            n_owner_fix = self._fix_incassato_da_owner()

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Riepilogo"))
        if reset:
            self.stdout.write(
                f"  0. RESET: allocations cancellate e Receivable "
                f"resettati a ATTESO: {n_reset}"
            )
        else:
            self.stdout.write(
                f"  1. Allocations errate eliminate: {n_alloc_errate}"
            )
            self.stdout.write(
                f"  2. Receivable orfani resettati: {n_reset_orfani}"
            )
        self.stdout.write(
            f"  3. BT processate: {n_bt_processate} (skip causale fuori "
            f"perimetro: {n_bt_skip}), allocations create: {n_alloc_create}"
        )
        self.stdout.write(
            f"  4. incassato_da_owner valorizzato: {n_owner_fix} Receivable"
        )

        # Stato finale
        non_ric = BankTransaction.objects.non_riconciliate().count()
        ric = BankTransaction.objects.riconciliate().count()
        tot = BankTransaction.objects.filter(importo__gt=0).count()
        self.stdout.write("")
        self.stdout.write(
            f"BT entrate totali: {tot} — riconciliate: {ric}, "
            f"non riconciliate: {non_ric}"
        )

        if dry_run:
            self.stdout.write(self.style.NOTICE("\nDRY-RUN: nessuna modifica scritta."))

    # -----------------------------------------------------------------
    # Step 0 (--reset): wipe + reset Receivable
    # -----------------------------------------------------------------
    def _reset_tutte_allocations(self) -> int:
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "\n[0] RESET: cancello tutte le allocations"
            )
        )
        receivable_ids = list(
            BankTransactionAllocation.objects.values_list(
                "receivable_id", flat=True
            ).distinct()
        )
        n_alloc = BankTransactionAllocation.objects.count()
        BankTransactionAllocation.objects.all().delete()
        n_reset = 0
        for r in Receivable.objects.filter(id__in=receivable_ids):
            _reset_receivable(r)
            n_reset += 1
        self.stdout.write(
            f"  cancellate {n_alloc} allocations; "
            f"{n_reset} Receivable resettati a ATTESO"
        )
        return n_reset

    # -----------------------------------------------------------------
    # Step 1: allocations con classifica BT ≠ causale Receivable
    # -----------------------------------------------------------------
    def _sweep_allocations_errate(self) -> int:
        self.stdout.write(self.style.MIGRATE_HEADING("\n[1] Sweep allocations errate"))
        errate: list[BankTransactionAllocation] = []
        for alloc in BankTransactionAllocation.objects.select_related(
            "bank_transaction", "receivable"
        ):
            classe = classifica_descrizione(alloc.bank_transaction.descrizione)
            if classe == "unknown":
                continue
            if classe != alloc.receivable.causale:
                errate.append(alloc)

        for a in errate:
            self.stdout.write(
                f"  alloc#{a.id}: BT {a.bank_transaction.data} "
                f"{a.bank_transaction.importo}€ "
                f"[{classifica_descrizione(a.bank_transaction.descrizione)}] "
                f"→ Receivable#{a.receivable_id} ({a.receivable.causale})"
            )
        for a in errate:
            a.delete()
        return len(errate)

    # -----------------------------------------------------------------
    # Step 2: Receivable Pagato senza allocation valida
    # -----------------------------------------------------------------
    def _reset_receivable_orfani(self) -> int:
        self.stdout.write(
            self.style.MIGRATE_HEADING("\n[2] Reset Receivable Pagato senza allocation")
        )
        orfani = (
            Receivable.objects.filter(stato=StatoPagamento.PAGATO)
            .filter(allocations__isnull=True)
            .select_related("assignment__tenant")
        )
        n = 0
        for r in orfani:
            self.stdout.write(
                f"  Receivable#{r.id} ({r.causale}) "
                f"tenant={r.assignment.tenant.nominativo} "
                f"data_pagamento={r.data_pagamento}"
            )
            _reset_receivable(r)
            n += 1
        return n

    # -----------------------------------------------------------------
    # Step 4: valorizza incassato_da_owner per Receivable già allocati
    # -----------------------------------------------------------------
    def _fix_incassato_da_owner(self) -> int:
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "\n[4] Fix incassato_da_owner per Receivable allocati"
            )
        )
        n = 0
        candidati = (
            Receivable.objects.filter(
                stato=StatoPagamento.PAGATO, incassato_da_owner__isnull=True
            )
            .filter(allocations__isnull=False)
            .prefetch_related("allocations__bank_transaction__owner_account")
            .distinct()
        )
        for r in candidati:
            alloc = r.allocations.first()
            if not alloc:
                continue
            owner_id = alloc.bank_transaction.owner_account.owner_id
            self.stdout.write(
                f"  Receivable#{r.id} ({r.causale}) → owner#{owner_id}"
            )
            r.incassato_da_owner_id = owner_id
            r.save(update_fields=["incassato_da_owner", "updated_at"])
            n += 1
        return n

    # -----------------------------------------------------------------
    # Step 3: match BT non riconciliate (filtrato per causali ammesse)
    # -----------------------------------------------------------------
    def _match_bt_non_riconciliate(
        self, causali_ammesse: set[str]
    ) -> tuple[int, int, int]:
        from decimal import Decimal

        self.stdout.write(
            self.style.MIGRATE_HEADING("\n[3] Match BT non riconciliate")
        )
        n_alloc_create = 0
        n_bt = 0
        n_skip = 0
        for bt in BankTransaction.objects.non_riconciliate().order_by("data"):
            classe = classifica_descrizione(bt.descrizione)
            # Filtro: scarta BT la cui classifica è fuori perimetro.
            if classe == "unknown":
                # Fallback solo se "affitto" è ammesso e l'importo è
                # plausibile per un canone (≥ 400€).
                if (
                    Receivable.Causale.AFFITTO not in causali_ammesse
                    or bt.importo < Decimal("400")
                ):
                    n_skip += 1
                    continue
            elif classe not in causali_ammesse:
                n_skip += 1
                continue
            n_bt += 1
            candidati = trova_receivables_per_bt(bt, escludi_pagati=True)
            # Restringi i candidati alle sole causali ammesse (la funzione
            # potrebbe restituire utenze per fallback su importo basso).
            candidati = [c for c in candidati if c.causale in causali_ammesse]
            if not candidati:
                self.stdout.write(
                    f"  - BT {bt.data} {bt.importo}€ [{classe}] "
                    f"— nessun Receivable candidato"
                )
                continue
            primario = candidati[0]
            # Compagni (utenze + affitto in un solo BT): solo se le utenze
            # sono ammesse. In modalità solo-affitto NON aggiungiamo compagni.
            extra: list[Receivable] = []
            if (
                primario.causale == Receivable.Causale.AFFITTO
                and bt.importo > primario.importo_dovuto
                and Receivable.Causale.UTENZE in causali_ammesse
            ):
                extra = [
                    c
                    for c in receivables_compagni(primario)
                    if c.causale in causali_ammesse
                ]
            allocs = alloca_bonifico(bt, [primario, *extra])
            n_alloc_create += len(allocs)
            descr_alloc = ", ".join(
                f"R#{a.receivable_id}({a.receivable.causale}={a.importo}€)"
                for a in allocs
            )
            self.stdout.write(
                f"  ✓ BT {bt.data} {bt.importo}€ → {descr_alloc}"
                + (f" [residuo {bt.importo - sum(a.importo for a in allocs)}€]"
                   if bt.importo_allocato < bt.importo else "")
            )
        return n_alloc_create, n_bt, n_skip
