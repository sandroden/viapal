"""Riconcilia BankTransaction con Receivable in modo idempotente.

Procedura:

  1. **Sweep allocations errate**: elimina ``BankTransactionAllocation`` in
     cui la classifica del bonifico (regex su descrizione) differisce dalla
     causale del Receivable allocato.
  2. **Reset Receivable orfani**: i Receivable con ``stato=pagato`` ma senza
     alcuna allocation valida vengono resettati a ATTESO (la "prova"
     bancaria del pagamento manca: lo `stato pagato` non è giustificato).
  3. **Match BT non riconciliate**: per ogni ``BankTransaction`` la cui somma
     allocations è inferiore all'importo (vedi `is_riconciliato`), cerca i
     Receivable candidati (tenant + causale + finestra di tolleranza) e
     alloca greedy. Un BT può chiudere più Receivable se il suo importo è
     sufficiente (caso "bonifico cumulativo": affitto + utenze in un unico
     versamento).

Idempotente: rilanciato dopo l'import di nuovi estratti conto, processa
solo le BT non ancora interpretate. Non duplica allocazioni esistenti.

Uso:
    uv run manage.py riconcilia_bonifici --dry-run
    uv run manage.py riconcilia_bonifici
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

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]
        self.stdout.write(f"Mode: {'DRY-RUN' if dry_run else 'WRITE'}\n")

        with transaction.atomic():
            n_alloc_errate = self._sweep_allocations_errate()
            n_reset_orfani = self._reset_receivable_orfani()
            n_alloc_create, n_bt_processate = self._match_bt_non_riconciliate()
            n_owner_fix = self._fix_incassato_da_owner()

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Riepilogo"))
        self.stdout.write(
            f"  1. Allocations errate eliminate: {n_alloc_errate}"
        )
        self.stdout.write(
            f"  2. Receivable orfani resettati: {n_reset_orfani}"
        )
        self.stdout.write(
            f"  3. BT processate: {n_bt_processate}, "
            f"allocations create: {n_alloc_create}"
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
    # Step 3: match BT non riconciliate
    # -----------------------------------------------------------------
    def _match_bt_non_riconciliate(self) -> tuple[int, int]:
        self.stdout.write(
            self.style.MIGRATE_HEADING("\n[3] Match BT non riconciliate")
        )
        n_alloc_create = 0
        n_bt = 0
        for bt in BankTransaction.objects.non_riconciliate().order_by("data"):
            n_bt += 1
            candidati = trova_receivables_per_bt(bt, escludi_pagati=True)
            if not candidati:
                self.stdout.write(
                    f"  - BT {bt.data} {bt.importo}€ [{classifica_descrizione(bt.descrizione)}] "
                    f"— nessun Receivable candidato"
                )
                continue
            primario = candidati[0]
            # Compagni: solo se la classe del bonifico è AFFITTO e l'importo
            # eccede il dovuto del primario (es. canone + spese in un solo BT).
            extra: list[Receivable] = []
            if (
                primario.causale == Receivable.Causale.AFFITTO
                and bt.importo > primario.importo_dovuto
            ):
                extra = receivables_compagni(primario)
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
        return n_alloc_create, n_bt
