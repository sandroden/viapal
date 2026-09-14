"""Trasferimenti di Bruna a Fabio — import e riclassificazione (lista chiusa).

Bruna incassa gli affitti sul proprio conto e gira a Fabio la sua quota:
bonifici mensili (di norma 300 €) e, in alcuni anni, il pagamento diretto
dei suoi F24 (IMU e cedolare secca). Fino al 2026-09 nulla di tutto ciò
entrava nei saldi: cinque movimenti erano registrati come partite
*bilaterali* (che per costruzione non toccano la cassa comune), altri due
erano aggregati sintetici del «libro mano» di Bruna, il resto mancava.
Il credito di Fabio risultava perciò gonfiato di ~19.000 €.

Questo command allinea la contabilità all'estratto bonifici del conto di
Bruna (ricerca 2022-09-14 → 2026-09-14, 44 righe) secondo tre decisioni
prese con Sandro il 2026-09-15:

  1. **tutto ciò che è andato a Fabio è un trasferimento**, qualunque sia
     la causale: anche gli F24 pagati per lui e i 470 € di giugno 2026
     (che Fabio ha ricevuto ma non ha versato al fisco). Nessuno di questi
     movimenti è una spesa dell'immobile: sono modi di dargli la sua quota,
     e vanno quindi marcati `distribuzione` verso Fabio;
  2. i due movimenti estranei all'immobile («rimborso spese monza» 324 del
     2023-11-22 e «rimborso malattia mamma» 3.300 del 2024-12-11) restano
     **fuori** da viapal: non compaiono in questa lista;
  3. vale ciò che la banca documenta. Gli aggregati del libro mano vengono
     rimossi: la BT «4 quote Fabio» -1200 coincide esattamente con i quattro
     bonifici set-dic 2024, mentre «affitti Fabio» -1900 ne copre sei di cui
     la banca ne documenta cinque (1.600 €) — aprile 2024 non risulta
     bonificato e lo scarto di 300 € è voluto, non un errore di questo import.

Le due Expense «IMU fabio 2022/2023» (317 e 904) non vengono cancellate ma
**convertite**: `anticipata_da_owner` passa da Bruna a Fabio, così l'IMU resta
un costo nel conto economico mentre il trasferimento di denaro è già
rappresentato dalle BT del 2023-12-15. Con anticipante e beneficiario
coincidenti i saldi fra proprietari le ignorano (`saldi_live`), quindi il
movimento non è contato due volte.

Caratteristiche:

  * **Idempotente**: le BT sono cercate sulla chiave naturale esatta
    (conto, data, importo), come il bulk-import dell'estratto conto; le
    marcature sono saltate se la BT ha già voci ledger. Rilanciare non
    duplica nulla.
  * **Fail-safe sul replay in prod**: ogni rimozione verifica descrizione e
    importo attesi e salta (con warning) se la BT ha allocazioni verso
    inquilini. Gli ID non sono mai usati: si lavora per chiave naturale.
  * Default dry-run — le scritture avvengono comunque dentro una
    transaction che viene ribaltata, così l'anteprima mostra i saldi veri.

Uso::

    uv run manage.py importa_trasferimenti_fabio            # anteprima
    uv run manage.py importa_trasferimenti_fabio --apply
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounting.services.bt_inter_owner import disfa_marcatura, marca_bt_come_ledger
from accounting.services.saldi_live import calcola_saldi_correnti
from billing.models import Expense
from billing.models.payments import BankTransaction
from properties.models import OwnerBankAccount


@dataclass(frozen=True)
class Riga:
    data: date
    importo: Decimal      # negativo: esce dal conto di Bruna
    causale: str          # causale della banca, tenuta com'è


# Conto di Bruna (BPER 3122360) e beneficiario, risolti per cognome/nome:
# gli ID non sono citati perché il replay in prod non deve dipenderne.
IBAN_FRAMMENTO = "2360"
BENEFICIARIO = "Fabio"
INTESTATARIO = "Bruna"

# ---------------------------------------------------------------------------
# Estratto bonifici del conto di Bruna, righe in perimetro (42 su 44).
# Le date sono quelle dell'ordine tranne dove annotato.
# ---------------------------------------------------------------------------
TRASFERIMENTI: list[Riga] = [
    Riga(date(2023, 12, 15), Decimal("-317"), "F24 IMU 2022 sett-dic"),
    Riga(date(2023, 12, 15), Decimal("-904"), "F24 IMU 2023"),
    Riga(date(2024, 1, 13), Decimal("-400"), "quota parte affitto"),
    Riga(date(2024, 2, 3), Decimal("-300"), "quota parte affitto"),
    Riga(date(2024, 3, 28), Decimal("-300"), "quota parte affitto"),
    Riga(date(2024, 5, 1), Decimal("-300"), "quota parte affitto"),
    Riga(date(2024, 6, 2), Decimal("-300"), "quota parte affitto"),
    # ordine 16/06, addebito 17/06: la BT a DB porta la data dell'addebito.
    Riga(date(2024, 6, 17), Decimal("-877"), "F24 IMU 2024"),
    Riga(date(2024, 7, 1), Decimal("-300"), "quota parte affitto"),
    Riga(date(2024, 7, 31), Decimal("-834"), "F24 cedolare secca"),
    Riga(date(2024, 8, 2), Decimal("-300"), "quota parte affitto"),
    Riga(date(2024, 9, 1), Decimal("-300"), "quota parte affitto"),
    Riga(date(2024, 10, 3), Decimal("-300"), "quota parte affitto"),
    Riga(date(2024, 11, 1), Decimal("-300"), "quota parte affitto"),
    Riga(date(2024, 11, 20), Decimal("-358"), "F24 cedolare secca"),
    Riga(date(2024, 12, 3), Decimal("-300"), "quota parte affitto"),
    Riga(date(2025, 1, 2), Decimal("-300"), "quota parte affitto"),
    Riga(date(2025, 2, 1), Decimal("-300"), "quota parte affitto"),
    Riga(date(2025, 3, 2), Decimal("-300"), "quota parte affitto"),
    Riga(date(2025, 4, 4), Decimal("-300"), "quota parte affitto"),
    # Maggio 2025 doppio: confermato da Bruna, poi reso da Fabio (vedi RIENTRI).
    Riga(date(2025, 5, 2), Decimal("-300"), "quota parte affitto"),
    Riga(date(2025, 5, 5), Decimal("-300"), "quota parte affitto"),
    Riga(date(2025, 6, 2), Decimal("-300"), "quota parte affitto"),
    Riga(date(2025, 6, 16), Decimal("-877"), "F24 IMU 2025"),
    Riga(date(2025, 6, 29), Decimal("-300"), "quota parte affitto"),
    Riga(date(2025, 7, 31), Decimal("-300"), "quota parte affitto"),
    Riga(date(2025, 9, 1), Decimal("-300"), "quota parte affitto"),
    Riga(date(2025, 10, 3), Decimal("-300"), "quota parte affitto"),
    Riga(date(2025, 11, 2), Decimal("-300"), "quota parte affitto"),
    Riga(date(2025, 12, 2), Decimal("-300"), "quota parte affitto"),
    Riga(date(2025, 12, 18), Decimal("-1000"), "quota parte affitto"),
    Riga(date(2026, 1, 2), Decimal("-300"), "quota parte affitto"),
    Riga(date(2026, 2, 2), Decimal("-300"), "quota parte affitto"),
    Riga(date(2026, 2, 27), Decimal("-300"), "quota parte affitto"),
    Riga(date(2026, 3, 2), Decimal("-300"), "quota parte affitto"),
    Riga(date(2026, 3, 31), Decimal("-300"), "quota parte affitto"),
    Riga(date(2026, 5, 1), Decimal("-300"), "quota parte affitto"),
    Riga(date(2026, 6, 4), Decimal("-300"), "quota parte affitto"),
    # Dato a Fabio perché pagasse l'IMU 2026: non l'ha versata, resta un
    # trasferimento come gli altri.
    Riga(date(2026, 6, 16), Decimal("-470"), "per pagamento IMU"),
    Riga(date(2026, 7, 3), Decimal("-300"), "quota parte affitto"),
    Riga(date(2026, 8, 2), Decimal("-300"), "quota parte affitto"),
    Riga(date(2026, 9, 4), Decimal("-300"), "quota parte affitto"),
]

# Rientri di Fabio verso Bruna, già a DB e non documentati dall'estratto
# (che elenca i soli bonifici in uscita): vanno marcati nello stesso modo,
# con il segno opposto. Da confermare con Sandro se il «reso» di 300 sia la
# restituzione del doppio bonifico di maggio 2025.
RIENTRI: list[Riga] = [
    Riga(date(2024, 12, 1), Decimal("630"), "4 quote  Fabio"),
    Riga(date(2026, 3, 2), Decimal("300"), "FABIO reso"),
]

# Aggregati del libro mano di Bruna, sostituiti dai bonifici reali.
SINTETICHE: list[Riga] = [
    Riga(date(2024, 6, 1), Decimal("-1900"), "affitti Fabio"),
    Riga(date(2024, 12, 1), Decimal("-1200"), "4 quote  Fabio"),
]

# Spese IMU di Fabio anticipate da Bruna: l'anticipo diventa suo (il denaro
# è già rappresentato dalle BT del 2023-12-15), la spesa resta nel conto
# economico.
EXPENSE_DA_CONVERTIRE = [
    (date(2023, 12, 15), Decimal("317.00")),
    (date(2023, 12, 15), Decimal("904.00")),
]


class Command(BaseCommand):
    help = "Importa e riclassifica i trasferimenti di Bruna a Fabio (lista chiusa)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Scrive le modifiche (default: anteprima con rollback).",
        )

    def handle(self, *args, **options):
        applica = options["apply"]
        conto = self._conto()
        immobile = conto.properties.first()
        if immobile is None:
            raise CommandError(
                f"Il conto {conto} non è collegato ad alcun immobile: "
                "collegarlo prima di importare."
            )
        fabio = self._beneficiario(immobile)

        try:
            with transaction.atomic():
                self._stampa_saldi(immobile, "Saldi prima")
                self._rimuovi_sintetiche(conto)
                creati, marcati = self._importa(conto, immobile, fabio)
                convertite = self._converti_expense(immobile, fabio)
                self._stampa_saldi(immobile, "Saldi dopo")
                self.stdout.write(
                    f"\nBT create: {creati} — marcate distribuzione: {marcati} — "
                    f"Expense convertite: {convertite}"
                )
                if not applica:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING(
                "\nAnteprima: nulla è stato scritto. Rilanciare con --apply."
            ))
            return
        self.stdout.write(self.style.SUCCESS("\nModifiche applicate."))

    # -- risoluzione attori ------------------------------------------------

    def _conto(self) -> OwnerBankAccount:
        qs = OwnerBankAccount.objects.filter(
            iban__contains=IBAN_FRAMMENTO, owner__nominativo__icontains=INTESTATARIO,
        )
        if qs.count() != 1:
            raise CommandError(
                f"Atteso un solo conto di {INTESTATARIO} con IBAN ...{IBAN_FRAMMENTO}, "
                f"trovati {qs.count()}."
            )
        return qs.select_related("owner").get()

    def _beneficiario(self, immobile):
        qs = immobile.ownership_shares.filter(
            owner__nominativo__icontains=BENEFICIARIO,
        ).select_related("owner")
        owners = {q.owner for q in qs}
        if len(owners) != 1:
            raise CommandError(
                f"Atteso un solo proprietario di nome {BENEFICIARIO} su {immobile}, "
                f"trovati {len(owners)}."
            )
        return owners.pop()

    # -- passi -------------------------------------------------------------

    def _rimuovi_sintetiche(self, conto) -> None:
        for r in SINTETICHE:
            for bt in BankTransaction.objects.filter(
                owner_account=conto, data=r.data, importo=r.importo,
            ):
                if bt.descrizione.strip() != r.causale:
                    self.stdout.write(self.style.WARNING(
                        f"  ~ BT {bt.pk} {r.data} {r.importo}: descrizione "
                        f"«{bt.descrizione}» diversa da «{r.causale}», lasciata."
                    ))
                    continue
                if bt.allocations.exists():
                    self.stdout.write(self.style.WARNING(
                        f"  ~ BT {bt.pk} «{bt.descrizione}» ha allocazioni verso "
                        "inquilini: lasciata intatta."
                    ))
                    continue
                disfa_marcatura(bt)
                bt.delete()
                self.stdout.write(
                    f"  - rimossa sintetica {r.data} {r.importo} «{r.causale}»"
                )

    def _importa(self, conto, immobile, fabio) -> tuple[int, int]:
        creati = marcati = 0
        for r in TRASFERIMENTI + RIENTRI:
            bt = BankTransaction.objects.filter(
                owner_account=conto, data=r.data, importo=r.importo,
            ).order_by("id").first()
            if bt is None:
                bt = BankTransaction.objects.create(
                    owner_account=conto, data=r.data, importo=r.importo,
                    descrizione=r.causale,
                    note="Da estratto bonifici del conto di Bruna (set. 2026).",
                )
                creati += 1
                self.stdout.write(f"  + BT {r.data} {r.importo} «{r.causale}»")
            if bt.ledger_entries.exists():
                continue
            # Una partita bilaterale sullo stesso movimento è la vecchia
            # classificazione: va sostituita, non affiancata.
            if bt.inter_owner_entries.exists():
                disfa_marcatura(bt)
                self.stdout.write(
                    f"  ~ BT {bt.pk} {r.data}: bilaterale → distribuzione"
                )
            verso = "a" if r.importo < 0 else "da"
            marca_bt_come_ledger(
                bt, property=immobile, tipo="distribuzione", controparte_owner=fabio,
                descrizione=f"Quota {verso} {fabio.nominativo} — {r.causale}",
            )
            marcati += 1
        return creati, marcati

    def _converti_expense(self, immobile, fabio) -> int:
        convertite = 0
        for data, importo in EXPENSE_DA_CONVERTIRE:
            for e in Expense.objects.filter(
                property=immobile, data=data, importo=importo,
                riferimento_quota_owner=fabio,
            ).exclude(anticipata_da_owner=fabio):
                e.anticipata_da_owner = fabio
                e.note = (
                    f"{e.note}\n" if e.note else ""
                ) + (
                    "Pagata materialmente da Bruna; il trasferimento di denaro è "
                    "registrato come movimento bancario del 2023-12-15."
                )
                e.save(update_fields=["anticipata_da_owner", "note"])
                convertite += 1
                self.stdout.write(
                    f"  ~ Expense {e.pk} «{e.descrizione}»: anticipante → "
                    f"{fabio.nominativo}"
                )
        return convertite

    # -- output ------------------------------------------------------------

    def _stampa_saldi(self, immobile, titolo: str) -> None:
        saldi = calcola_saldi_correnti(immobile, date.today())
        self.stdout.write(f"\n{titolo}:")
        for owner, s in sorted(saldi.items(), key=lambda kv: kv[0].nominativo):
            self.stdout.write(f"  {owner.nominativo:28} {s.totale:>12,.2f}")


class _Rollback(Exception):
    """Interrompe la transaction dell'anteprima."""
