"""Ricostruisce gli incassi dei Receivable chiusi senza «incassato da».

Fino al vincolo ``receivable_pagato_ha_incassante`` il bottone «Conferma» della
pagina Ritardi poteva portare un addebito a PAGATO senza dire su quale conto
fosse entrato il denaro: quegli addebiti restano fuori dai saldi tra
proprietari, che li segnalano come «incassi esclusi dal calcolo».

Questo command applica una lista CHIUSA di ricostruzioni decise caso per caso,
nello stile di ``riconcilia_storico_manuale``:

  * **Idempotente**: la BankTransaction è cercata per (data, importo, conto,
    descrizione) e le allocazioni con ``get_or_create``. Rilanciare non
    duplica nulla.
  * **Fail-safe sul replay in prod**: prima di scrivere verifica che ogni
    Receivable esista, appartenga all'inquilino atteso, valga l'importo
    atteso e sia ancora senza incassante. Se qualcosa diverge il caso viene
    SALTATO con un warning.
  * Stato, data pagamento e ``incassato_da_owner`` li aggiorna il signal su
    ``BankTransactionAllocation``: qui non si scrive nulla a mano. Se
    un'attribuzione risulta sbagliata, si corregge il **movimento** (conto o
    data) — anche dall'admin — e gli addebiti si riallineano da soli.

Va eseguito **prima** della migration che introduce il vincolo: finché restano
addebiti pagati senza incassante, quella migration fallisce.

Uso::

    uv run manage.py sana_incassi_senza_incassante            # dry-run
    uv run manage.py sana_incassi_senza_incassante --apply
"""
from dataclasses import dataclass, field
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    Expense,
    ExpenseCategory,
    Receivable,
    StatoPagamento,
)
from properties.models import OwnerBankAccount, OwnerProfile


@dataclass
class Quota:
    """Un Receivable da coprire con la BT del caso."""

    receivable_id: int
    importo: Decimal
    tenant_contains: str
    dovuto_atteso: Decimal


@dataclass
class SpesaCollegata:
    """Contropartita di un incasso non monetario (bene entrato in casa).

    L'inquilino non ha versato denaro: ha lasciato un bene. L'incasso finto e
    la spesa finta si compensano esattamente nei saldi (chi «incassa» deve agli
    altri la loro quota, chi «anticipa» la riceve), e restano la traccia del
    bene acquisito e del deposito da restituire.
    """

    importo: Decimal
    descrizione: str
    categoria_codice: str
    owner_id: int


@dataclass
class Caso:
    bt_data: str                # ISO
    bt_importo: Decimal
    bt_descrizione: str
    conto_id: int
    conto_intestatario_contains: str   # asserzione di sicurezza sul conto
    quote: list[Quota]
    nota: str
    bt_note: str = ""
    spesa: SpesaCollegata | None = None
    _extra: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Lista chiusa (snapshot prod). Gli id sono stabili: il DB locale è una copia
# della produzione.
# ---------------------------------------------------------------------------
CASI: list[Caso] = [
    # Arun Singarayar — affitto luglio e utenze maggio, confermati dalla pagina
    # Ritardi senza indicare il conto (la data 04/07 registrata dalla conferma
    # non è quella dell'incasso). Due incassi distinti, non un unico bonifico:
    # l'affitto va sul conto di Bruna — come gli altri canoni di Arun — mentre
    # le utenze le ha incassate Alessandro.
    Caso(
        bt_data="2026-07-06",
        bt_importo=Decimal("540.00"),
        bt_descrizione="Arun Singarayar — Affitto Lug 2026",
        conto_id=15,
        conto_intestatario_contains="Bruna",
        quote=[
            Quota(
                receivable_id=965, importo=Decimal("540.00"),
                tenant_contains="Arun", dovuto_atteso=Decimal("540.00"),
            ),
        ],
        bt_note=(
            "Incasso ricostruito a posteriori: confermato dalla pagina Ritardi "
            "senza indicare il conto."
        ),
        nota="Arun: affitto lug 2026 (540) → conto Bruna",
    ),
    Caso(
        bt_data="2026-07-06",
        bt_importo=Decimal("55.15"),
        bt_descrizione="Arun Singarayar — Utenze Mag 2026",
        conto_id=14,
        conto_intestatario_contains="Alessandro",
        quote=[
            Quota(
                receivable_id=959, importo=Decimal("55.15"),
                tenant_contains="Arun", dovuto_atteso=Decimal("55.15"),
            ),
        ],
        bt_note=(
            "Incasso ricostruito a posteriori: confermato dalla pagina Ritardi "
            "senza indicare il conto."
        ),
        nota="Arun: utenze mag 2026 (55,15) → conto Alessandro",
    ),
    # Arun Singarayar — quota di deposito saldata in natura: materasso
    # acquistato dall'inquilino e lasciato in dotazione alla casa. Nessun
    # movimento bancario reale: l'incasso e la spesa di arredo si compensano.
    Caso(
        bt_data="2026-07-26",
        bt_importo=Decimal("130.00"),
        bt_descrizione="Arun Singarayar — Deposito in natura (materasso in dotazione)",
        conto_id=14,
        conto_intestatario_contains="Alessandro",
        quote=[
            Quota(
                receivable_id=375, importo=Decimal("130.00"),
                tenant_contains="Arun", dovuto_atteso=Decimal("130.00"),
            ),
        ],
        bt_note=(
            "Nessun movimento bancario: deposito saldato con un materasso "
            "lasciato in dotazione alla casa. Contropartita: spesa di arredo "
            "di pari importo."
        ),
        spesa=SpesaCollegata(
            importo=Decimal("130.00"),
            descrizione="Materasso lasciato in dotazione da Arun Singarayar (deposito in natura)",
            categoria_codice="arredo-manutenzione",
            owner_id=19,
        ),
        nota="Arun: deposito 130 in natura → incasso + spesa arredo che si compensano",
    ),
]


class Command(BaseCommand):
    help = (
        "Ricostruisce gli incassi dei Receivable pagati senza «incassato da» "
        "(lista chiusa, idempotente). Default dry-run: usa --apply per scrivere."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Scrive davvero (senza, mostra solo cosa farebbe).",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        if not apply:
            self.stdout.write(self.style.WARNING("DRY-RUN — nessuna scrittura.\n"))

        applicati = saltati = 0
        for caso in CASI:
            if self._esegui(caso, apply):
                applicati += 1
            else:
                saltati += 1

        self.stdout.write("")
        self.stdout.write(f"Casi applicati: {applicati} — saltati: {saltati}")
        residui = Receivable.objects.filter(
            stato=StatoPagamento.PAGATO, incassato_da_owner__isnull=True
        ).count()
        stile = self.style.SUCCESS if residui == 0 else self.style.ERROR
        self.stdout.write(
            stile(f"Addebiti pagati senza incassante rimasti: {residui}")
        )

    # -- interno ----------------------------------------------------------

    def _esegui(self, caso: Caso, apply: bool) -> bool:
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{caso.nota}"))

        conto = OwnerBankAccount.objects.filter(pk=caso.conto_id).first()
        if conto is None:
            return self._salta(f"conto id={caso.conto_id} inesistente")
        if caso.conto_intestatario_contains not in str(conto.owner):
            return self._salta(
                f"conto id={caso.conto_id} intestato a «{conto.owner}», "
                f"atteso «{caso.conto_intestatario_contains}»"
            )

        receivables = []
        for q in caso.quote:
            r = Receivable.objects.filter(pk=q.receivable_id).first()
            if r is None:
                return self._salta(f"receivable id={q.receivable_id} inesistente")
            if q.tenant_contains.lower() not in r.assignment.tenant.nominativo.lower():
                return self._salta(
                    f"receivable id={r.pk} è di «{r.assignment.tenant.nominativo}», "
                    f"atteso «{q.tenant_contains}»"
                )
            if r.importo_dovuto != q.dovuto_atteso:
                return self._salta(
                    f"receivable id={r.pk} vale {r.importo_dovuto}, "
                    f"atteso {q.dovuto_atteso}"
                )
            if r.incassato_da_owner_id is not None:
                self.stdout.write(
                    f"  · receivable id={r.pk}: già con incassante "
                    f"({r.incassato_da_owner}) — nulla da fare"
                )
                return True
            receivables.append((r, q.importo))

        for r, importo in receivables:
            self.stdout.write(
                f"  → {importo} € su receivable id={r.pk} "
                f"({r.get_causale_display()} {r.assignment.tenant.nominativo})"
            )
        self.stdout.write(
            f"  BT {caso.bt_data} {caso.bt_importo} € su {conto.banca} ({conto.owner})"
        )
        if caso.spesa:
            self.stdout.write(
                f"  Spesa {caso.spesa.importo} € — {caso.spesa.descrizione}"
            )
        if not apply:
            return True

        with transaction.atomic():
            bt, creata = BankTransaction.objects.get_or_create(
                data=caso.bt_data,
                importo=caso.bt_importo,
                owner_account=conto,
                descrizione=caso.bt_descrizione,
                defaults={"note": caso.bt_note},
            )
            for r, importo in receivables:
                BankTransactionAllocation.objects.get_or_create(
                    bank_transaction=bt,
                    receivable=r,
                    defaults={"importo": importo},
                )
            if caso.spesa:
                self._crea_spesa(caso.spesa, caso.bt_data, receivables[0][0])

        self.stdout.write(self.style.SUCCESS(f"  ✔ applicato (BT id={bt.pk})"))
        return True

    def _crea_spesa(self, spesa: SpesaCollegata, data: str, receivable: Receivable):
        prop = receivable.assignment.room.property
        categoria = ExpenseCategory.objects.filter(
            property=prop, codice=spesa.categoria_codice
        ).first()
        if categoria is None:
            self.stdout.write(
                self.style.WARNING(
                    f"  ! categoria «{spesa.categoria_codice}» assente: "
                    "spesa non creata"
                )
            )
            return
        owner = OwnerProfile.objects.filter(pk=spesa.owner_id).first()
        if owner is None:
            self.stdout.write(
                self.style.WARNING(
                    f"  ! owner id={spesa.owner_id} assente: spesa non creata"
                )
            )
            return
        _, creata = Expense.objects.get_or_create(
            property=prop,
            data=data,
            importo=spesa.importo,
            descrizione=spesa.descrizione,
            defaults={
                "category": categoria,
                "anticipata_da_owner": owner,
                "ripartibile_su_inquilini": False,
            },
        )
        if creata:
            self.stdout.write(self.style.SUCCESS("  ✔ spesa di contropartita creata"))
        else:
            self.stdout.write("  · spesa di contropartita già presente")

    def _salta(self, motivo: str) -> bool:
        self.stdout.write(self.style.WARNING(f"  SALTATO: {motivo}"))
        return False
