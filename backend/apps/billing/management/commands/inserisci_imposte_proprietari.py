"""IMU e cedolare secca dei proprietari come costo dell'immobile.

Le imposte sulla locazione sono di ciascun proprietario pro-quota: ognuno
paga il proprio F24. Restano però un'uscita dell'affitto, e senza di loro il
conto economico racconta un guadagno che non esiste — è la ragione per cui
Sandro le vuole a bilancio (2026-09-15).

Ogni voce è una `Expense` con **anticipante e beneficiario coincidenti**
(`anticipata_da_owner == riferimento_quota_owner`): entra nel conto economico
come costo e `saldi_live` la ignora per costruzione, quindi non sposta nulla
fra i proprietari. Il denaro che Bruna ha anticipato per Fabio è una partita
separata, registrata come trasferimento da
``importa_trasferimenti_fabio``: le due cose non si sommano.

Dati (Sandro, 2026-09-15): «abbiamo sempre pagato la stessa cifra di IMU e di
cedolare secca; se hai quella di Fabio tienila buona anche per noi». Gli
importi sono quindi quelli documentati dagli F24 di Fabio, replicati sui tre.
Due eccezioni:

  * **2026**: il contratto unico a canone concordato porta lo sconto del
    Comune e quello dello Stato, e l'IMU scende da ~877 a **471** a testa.
    Fabio quest'anno non l'ha versata (ha ricevuto i 470 € ma non ha pagato):
    per lui non c'è nessuna voce, il costo 2026 è di due quote su tre;
  * **cedolare secca**: sono documentati i soli F24 2024 (834 a luglio + 358
    a novembre). Gli altri anni non sono registrati finché non arrivano gli
    importi.

Le date sono quelle di competenza: la scadenza dell'anno, o il pagamento
reale dove noto. L'IMU 2022 di Fabio, versata in ritardo il 2023-12-15
insieme a quella del 2023, viene riportata al 2022 perché il conto economico
usa un'unica data per cassa e competenza, e leggere due anni di IMU dentro il
2023 sarebbe fuorviante; la data reale resta nelle note.

Idempotente sulla chiave (immobile, data, categoria, proprietario, importo):
rilanciare non duplica. Default dry-run, `--apply` per scrivere.

Uso::

    uv run manage.py inserisci_imposte_proprietari            # anteprima
    uv run manage.py inserisci_imposte_proprietari --apply
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from billing.models import Expense, ExpenseCategory
from properties.models import Property


@dataclass(frozen=True)
class Imposta:
    data: date
    importo: Decimal
    categoria: str          # codice ExpenseCategory
    descrizione: str        # senza il nome del proprietario, aggiunto dopo
    solo: tuple[str, ...] = ()   # se valorizzato, i soli proprietari indicati
    nota: str = ""


CATEGORIE = {
    "imu": "IMU",
    "cedolare": "Cedolare secca",
}

IMPOSTE: list[Imposta] = [
    Imposta(
        date(2022, 12, 16), Decimal("317"), "imu", "IMU 2022 (set-dic)",
        nota="Fabio l'ha versata il 2023-12-15 insieme a quella del 2023.",
    ),
    Imposta(date(2023, 12, 15), Decimal("904"), "imu", "IMU 2023"),
    Imposta(date(2024, 6, 17), Decimal("877"), "imu", "IMU 2024"),
    Imposta(date(2025, 6, 16), Decimal("877"), "imu", "IMU 2025"),
    Imposta(
        date(2026, 6, 16), Decimal("471"), "imu", "IMU 2026",
        solo=("Alessandro", "Bruna"),
        nota=(
            "Canone concordato: sconto comunale e statale, da ~877 a 471. "
            "Fabio non ha versato: ha ricevuto i 470 € da Bruna il 2026-06-16."
        ),
    ),
    Imposta(
        date(2024, 7, 31), Decimal("834"), "cedolare",
        "Cedolare secca 2024 (saldo e primo acconto)",
    ),
    Imposta(
        date(2024, 11, 20), Decimal("358"), "cedolare",
        "Cedolare secca 2024 (secondo acconto)",
    ),
]


class Command(BaseCommand):
    help = "Registra IMU e cedolare secca dei proprietari come costo dell'immobile."

    def add_arguments(self, parser):
        parser.add_argument(
            "--property", default="1",
            help="id o slug dell'immobile (default: 1).",
        )
        parser.add_argument(
            "--apply", action="store_true",
            help="Scrive le modifiche (default: anteprima con rollback).",
        )

    def handle(self, *args, **options):
        immobile = self._immobile(options["property"])
        proprietari = {
            q.owner.nominativo.split()[0]: q.owner
            for q in immobile.ownership_shares.select_related("owner")
        }
        if not proprietari:
            raise CommandError(f"{immobile} non ha quote di proprietà.")
        categorie = self._categorie(immobile)

        try:
            with transaction.atomic():
                # Prima si allineano le date, poi si crea: altrimenti la voce
                # di Fabio spostata a fine giro resterebbe accanto a una
                # nuova, identica, appena creata al suo posto.
                spostate = self._allinea_date(immobile, categorie)
                create = self._crea(immobile, proprietari, categorie)
                self._riepilogo(immobile)
                self.stdout.write(
                    f"\nSpese create: {create} — date allineate: {spostate}"
                )
                if not options["apply"]:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING(
                "\nAnteprima: nulla è stato scritto. Rilanciare con --apply."
            ))
            return
        self.stdout.write(self.style.SUCCESS("\nModifiche applicate."))

    # -- passi -------------------------------------------------------------

    def _crea(self, immobile, proprietari, categorie) -> int:
        creati = 0
        for imposta in IMPOSTE:
            nomi = imposta.solo or tuple(proprietari)
            for nome in nomi:
                owner = proprietari.get(nome)
                if owner is None:
                    self.stdout.write(self.style.WARNING(
                        f"  ~ {nome} non è proprietario di {immobile}: saltato."
                    ))
                    continue
                _, creato = Expense.objects.get_or_create(
                    property=immobile,
                    data=imposta.data,
                    category=categorie[imposta.categoria],
                    anticipata_da_owner=owner,
                    riferimento_quota_owner=owner,
                    importo=imposta.importo,
                    defaults={
                        "descrizione": f"{imposta.descrizione} — {owner.nominativo}",
                        "ripartibile_su_inquilini": False,
                        "note": imposta.nota,
                    },
                )
                if creato:
                    creati += 1
                    self.stdout.write(
                        f"  + {imposta.data} {imposta.importo:>6} "
                        f"{imposta.descrizione} — {nome}"
                    )
        return creati

    def _allinea_date(self, immobile, categorie) -> int:
        """Riporta al 2022 l'IMU 2022 di Fabio, versata in ritardo nel 2023."""
        spostate = 0
        for e in Expense.objects.filter(
            property=immobile, category=categorie["imu"],
            data=date(2023, 12, 15), importo=Decimal("317.00"),
        ):
            e.data = date(2022, 12, 16)
            e.note = (f"{e.note}\n" if e.note else "") + (
                "Versata in ritardo il 2023-12-15; data riportata all'anno di "
                "competenza perché il conto economico usa un'unica data."
            )
            e.save(update_fields=["data", "note"])
            spostate += 1
            self.stdout.write(f"  ~ Expense {e.pk} «{e.descrizione}» → 2022-12-16")
        return spostate

    # -- output ------------------------------------------------------------

    def _riepilogo(self, immobile) -> None:
        from django.db.models import Sum
        self.stdout.write("\nImposte a bilancio per anno:")
        righe = (
            Expense.objects.filter(
                property=immobile, category__codice__in=CATEGORIE,
            )
            .values("data__year", "category__nome")
            .annotate(totale=Sum("importo"))
            .order_by("data__year", "category__nome")
        )
        for r in righe:
            self.stdout.write(
                f"  {r['data__year']}  {r['category__nome']:16} "
                f"{r['totale']:>9,.2f}"
            )

    # -- risoluzione -------------------------------------------------------

    def _immobile(self, riferimento: str) -> Property:
        qs = Property.objects.filter(pk=riferimento) if riferimento.isdigit() \
            else Property.objects.filter(slug=riferimento)
        immobile = qs.first()
        if immobile is None:
            raise CommandError(f"Immobile «{riferimento}» inesistente.")
        return immobile

    def _categorie(self, immobile) -> dict:
        categorie = {}
        for codice, nome in CATEGORIE.items():
            # Le categorie sono per immobile: stesso codice può esistere più
            # volte nel DB, ma una sola volta qui.
            cat = (
                ExpenseCategory.objects.filter(property=immobile, codice=codice)
                .order_by("id").first()
            )
            if cat is None:
                cat = ExpenseCategory.objects.create(
                    property=immobile, codice=codice, nome=nome,
                    ripartibile_inquilini=False,
                )
                self.stdout.write(f"  + categoria di spesa «{nome}»")
            categorie[codice] = cat
        return categorie


class _Rollback(Exception):
    """Interrompe la transaction dell'anteprima."""
