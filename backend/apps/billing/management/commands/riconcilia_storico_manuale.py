"""Abbinamenti storici curati a mano — riconciliazione forense inquilini passati.

A differenza di ``riconcilia_bonifici`` (matcher automatico euristico), questo
command applica una lista CHIUSA di abbinamenti BankTransaction → Receivable
decisi caso per caso dopo analisi del libro mastro di ogni inquilino uscito.
Serve per i casi che l'automatico non sa risolvere: bonifici cumulativi,
voci sintetiche del «libro mano», pagamenti mai imputati.

Caratteristiche:

  * **Idempotente**: ogni allocation è creata con ``get_or_create`` sulla
    coppia (bank_transaction, receivable). Rilanciare non duplica nulla.
  * **Fail-safe sul replay in prod**: prima di scrivere, ogni match verifica
    che il BT e il Receivable abbiano gli importi/tenant attesi. Se i dati
    divergono (ID riusati, importi diversi) il match viene SALTATO con un
    warning invece di scrivere un'allocazione sbagliata. Gli ID sono stabili
    perché il DB locale è uno snapshot della prod.
  * Lo stato del Receivable (pagato/importo_pagato/data_pagamento) è
    aggiornato automaticamente dal signal su ``BankTransactionAllocation``.

Default è dry-run; serve ``--apply`` per scrivere.

Uso::

    uv run manage.py riconcilia_storico_manuale            # dry-run
    uv run manage.py riconcilia_storico_manuale --apply
"""
from dataclasses import dataclass
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import BankTransaction, BankTransactionAllocation, Receivable


@dataclass
class Match:
    bt_id: int
    receivable_id: int
    importo: Decimal
    # asserzioni di sicurezza (verificate prima di scrivere)
    tenant_contains: str           # sottostringa attesa nel nominativo tenant
    receivable_dovuto: Decimal     # importo_dovuto atteso del Receivable
    nota: str                      # spiegazione dell'abbinamento


# ---------------------------------------------------------------------------
# Lista chiusa degli abbinamenti storici curati a mano (snapshot prod).
# Ogni voce è stata verificata sul libro mastro completo dell'inquilino.
# ---------------------------------------------------------------------------
MATCHES: list[Match] = [
    # Lindy Nyathi — caparra versata su conto Bruna, mai imputata.
    Match(
        bt_id=2527, receivable_id=367, importo=Decimal("1060.00"),
        tenant_contains="Nyathi", receivable_dovuto=Decimal("1060.00"),
        nota="BT 'caparra Lindy' 1060 → deposito Lindy (esatto, stesso giorno)",
    ),
    # Maria Severa Armas — residuo della voce «libro mano» utenze 90€ (resto
    # 71,24 dopo i 18,76 già imputati a R#911) = somma esatta di due utenze
    # scoperte 2023: marzo 51,24 + saldo luglio 20,00.
    Match(
        bt_id=2720, receivable_id=908, importo=Decimal("51.24"),
        tenant_contains="Armas", receivable_dovuto=Decimal("51.24"),
        nota="utenze libro mano (res. 71,24) → utenze marzo 2023 (51,24)",
    ),
    Match(
        bt_id=2720, receivable_id=917, importo=Decimal("20.00"),
        tenant_contains="Armas", receivable_dovuto=Decimal("105.53"),
        nota="utenze libro mano (res. 71,24) → saldo utenze luglio 2023 (20,00)",
    ),
    # Salvatore D'Angella — il bonifico 262 di chiusura contratto dichiara in
    # descrizione 'UTENZE 37 CONCLUSIONE'; residuo 122,62 copre l'ultima
    # utenza scoperta (39,00).
    Match(
        bt_id=2340, receivable_id=856, importo=Decimal("39.00"),
        tenant_contains="D'Angella", receivable_dovuto=Decimal("39.00"),
        nota="BT 'D'Angella …UTENZE 37 CONCLUSIONE' (res. 122,62) → utenze finali (39,00)",
    ),
    # Manuel Traina — unico bonifico 500 (conto Sandro) a ridosso dell'uscita;
    # i suoi unici addebiti aperti sono due utenze. Imputo solo i 72€ utenze
    # (il resto del bonifico è canone/deposito non modellato a receivable).
    Match(
        bt_id=2651, receivable_id=909, importo=Decimal("51.24"),
        tenant_contains="Manuel", receivable_dovuto=Decimal("51.24"),
        nota="BT 'MANUEL TRAINA' 500 → utenze marzo 2023 (51,24)",
    ),
    Match(
        bt_id=2651, receivable_id=912, importo=Decimal("20.76"),
        tenant_contains="Manuel", receivable_dovuto=Decimal("20.76"),
        nota="BT 'MANUEL TRAINA' 500 → utenze maggio 2023 (20,76)",
    ),
]


class Command(BaseCommand):
    help = "Applica abbinamenti storici BankTransaction→Receivable curati a mano (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Scrive nel DB. Senza questo flag è dry-run.",
        )

    def handle(self, *args, **opts):
        apply = opts["apply"]
        self.stdout.write(f"Mode: {'APPLY' if apply else 'DRY-RUN'}\n")

        n_create = n_skip_esiste = n_skip_assert = 0
        with transaction.atomic():
            for m in MATCHES:
                esito = self._applica(m, apply)
                if esito == "create":
                    n_create += 1
                elif esito == "esiste":
                    n_skip_esiste += 1
                else:
                    n_skip_assert += 1
            if not apply:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Riepilogo"))
        self.stdout.write(f"  allocations create:        {n_create}")
        self.stdout.write(f"  già presenti (idempotente): {n_skip_esiste}")
        self.stdout.write(f"  saltate (assert fallita):   {n_skip_assert}")
        if not apply:
            self.stdout.write(self.style.NOTICE("\nDRY-RUN: nessuna modifica scritta. Usa --apply."))

    def _applica(self, m: Match, apply: bool) -> str:
        try:
            bt = BankTransaction.objects.get(pk=m.bt_id)
        except BankTransaction.DoesNotExist:
            self.stderr.write(self.style.WARNING(f"  SKIP {m.nota}: BT#{m.bt_id} inesistente"))
            return "assert"
        try:
            r = Receivable.objects.select_related("assignment__tenant").get(pk=m.receivable_id)
        except Receivable.DoesNotExist:
            self.stderr.write(self.style.WARNING(f"  SKIP {m.nota}: R#{m.receivable_id} inesistente"))
            return "assert"

        # --- asserzioni di sicurezza (fail-safe sul replay) ---
        tenant_nome = r.assignment.tenant.nominativo
        if m.tenant_contains.lower() not in tenant_nome.lower():
            self.stderr.write(self.style.WARNING(
                f"  SKIP {m.nota}: tenant atteso ~{m.tenant_contains!r}, trovato {tenant_nome!r}"))
            return "assert"
        if r.importo_dovuto != m.receivable_dovuto:
            self.stderr.write(self.style.WARNING(
                f"  SKIP {m.nota}: dovuto atteso {m.receivable_dovuto}, trovato {r.importo_dovuto}"))
            return "assert"
        residuo = bt.importo - bt.importo_allocato
        # residuo già al netto di eventuali allocation di QUESTO match su re-run:
        esiste = BankTransactionAllocation.objects.filter(
            bank_transaction=bt, receivable=r
        ).first()
        if esiste:
            self.stdout.write(f"  = già presente: {m.nota} (alloc#{esiste.id})")
            return "esiste"
        if residuo + Decimal("0.01") < m.importo:
            self.stderr.write(self.style.WARNING(
                f"  SKIP {m.nota}: residuo BT {residuo} < importo {m.importo}"))
            return "assert"

        self.stdout.write(self.style.SUCCESS(f"  ✓ {m.nota}  [{m.importo}€]"))
        if apply:
            BankTransactionAllocation.objects.create(
                bank_transaction=bt, receivable=r, importo=m.importo,
            )
        return "create"
