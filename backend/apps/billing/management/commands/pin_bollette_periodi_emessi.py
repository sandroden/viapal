"""
Riempie la M2M ``utility_bills`` dei periodi già emessi che ne sono privi.

Perché serve
------------
La M2M viene scritta solo dall'emissione (``calcola_conguaglio_periodo`` con
``persist=True``). I periodi nati dagli import storici hanno i ``tot_*``
valorizzati ma nessuna bolletta agganciata: l'abbinamento esiste solo come
calcolo al volo (overlap di date), non come dato. Da lì due conseguenze:
l'admin non mostra le bollette di quei mesi, e soprattutto le bollette
restano "libere", quindi candidabili al ribaltamento retroattivo su un
periodo aperto — la strada da cui i segnaposto 2023 sono finiti nel
conguaglio di luglio 2026.

Cosa aggancia
-------------
**Tutte** le bollette che intersecano il periodo, comprese le bimestrali che
lo eccedono: una bolletta che copre due mesi appartiene a entrambi, e
agganciarla a entrambi è la verità documentale. Il calcolo lo regge perché in
modalità pinning una bolletta condivisa fra più periodi si ripartisce
pro-rata sui giorni (vedi ``_attribuisci_bollette``): la somma sui periodi
che la condividono resta l'importo della bolletta, niente doppia imputazione.

Il piano si valuta **in blocco**, non periodo per periodo: quanto vale una
bimestrale su maggio dipende dal fatto che anche giugno la agganci.

Un periodo viene saltato se:

1. i suoi ``tot_*`` addebitano una voce di cui a DB non esiste nessuna
   bolletta (manca il dato, non l'aggancio: registrare la M2M scriverebbe
   una mezza verità);
2. il pinning allontanerebbe il ricalcolo dai ``tot_*`` effettivamente
   addebitati — verificato sui dati veri applicando il piano dentro un
   savepoint, non assunto. Avvicinarsi invece va benissimo: un periodo che
   oggi si vede attribuire arretrati fantasma (perché le bollette dei mesi
   precedenti non erano agganciate a nessuno) torna al suo importo vero.

Uso::

    uv run manage.py pin_bollette_periodi_emessi              # dry-run
    uv run manage.py pin_bollette_periodi_emessi --apply
    uv run manage.py pin_bollette_periodi_emessi --year 2026
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from properties.context import resolve_property_cli

CENTESIMO = Decimal("0.01")


class Command(BaseCommand):
    help = "Aggancia le bollette ai periodi già emessi che hanno la M2M vuota."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help="Applica davvero il pinning (default: dry-run).",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=None,
            help="Filtra i periodi che iniziano in quell'anno.",
        )
        parser.add_argument(
            "--property",
            type=str,
            default=None,
            help="Immobile (id, nome o slug). Obbligatorio se ce n'è più d'uno.",
        )

    def handle(self, *args, **options):
        from billing.models import UtilityChargePeriod

        applica = options["apply"]
        try:
            prop = resolve_property_cli(options.get("property"))
        except ValueError as e:
            raise CommandError(str(e)) from e

        periodi = UtilityChargePeriod.objects.filter(
            property=prop,
            stato=UtilityChargePeriod.StatoPeriodo.INVIATO,
            utility_bills__isnull=True,
        ).distinct().order_by("periodo_da")
        if options.get("year"):
            periodi = periodi.filter(periodo_da__year=options["year"])
        periodi = list(periodi)

        piano: dict = {}
        scartati: list[tuple] = []
        for period in periodi:
            bollette, motivo = self._candidate(period)
            if motivo:
                scartati.append((period, motivo))
            else:
                piano[period.pk] = (period, bollette)

        # Il piano va verificato tutto insieme: togliere un periodo cambia la
        # ripartizione delle bollette che condivideva con gli altri.
        for _ in range(5):
            cambia = self._verifica_in_blocco(piano)
            if not cambia:
                break
            for pk in cambia:
                period, _bollette = piano.pop(pk)
                scartati.append(
                    (period, "il pinning allontanerebbe il ricalcolo dagli importi addebitati")
                )

        if applica and piano:
            with transaction.atomic():
                for period, bollette in piano.values():
                    period.utility_bills.set(bollette)

        for period in periodi:
            if period.pk in piano:
                self._riga_ok(period, piano[period.pk][1])
        for period, motivo in sorted(scartati, key=lambda t: t[0].periodo_da):
            self.stdout.write(
                self.style.WARNING(
                    f"  [{period.pk}] {period.periodo_da} → {period.periodo_a} "
                    f"salto: {motivo}"
                )
            )

        prefix = "" if applica else "[DRY-RUN] "
        self.stdout.write("")
        self.stdout.write(
            f"{prefix}Periodi emessi senza bollette agganciate: {len(periodi)} "
            f"— pinnabili {len(piano)}, da guardare a mano {len(scartati)}"
        )
        if not applica and piano:
            self.stdout.write("Rilancia con --apply per scrivere gli agganci.")

    # ------------------------------------------------------------------
    def _candidate(self, period) -> tuple[list, str]:
        """Bollette da agganciare al periodo, o il motivo per cui non si tocca."""
        from billing.calc.utility import _voci_fatturabili
        from billing.models import UtilityBill

        voci = _voci_fatturabili(period.property_id)
        bollette = list(
            UtilityBill.objects.filter(
                immobile_id=period.property_id,
                prodotto__in=voci,
                periodo_da__lte=period.periodo_a,
                periodo_a__gte=period.periodo_da,
            ).order_by("periodo_da")
        )
        if not bollette:
            return [], "nessuna bolletta interseca il periodo"

        # Una voce addebitata di cui non esiste alcuna bolletta è un dato
        # mancante: l'aggancio non lo inventa.
        addebitato = {
            "luce": period.tot_luce or Decimal("0"),
            "gas": period.tot_gas or Decimal("0"),
        }
        con_bolletta = {b.prodotto for b in bollette}
        scoperte = [
            f"{voce} ({importo:.2f} €)"
            for voce, importo in addebitato.items()
            if voce in voci and importo > CENTESIMO and voce not in con_bolletta
        ]
        if scoperte:
            return [], (
                f"addebitate senza bolletta a DB: {', '.join(scoperte)} "
                "— manca il dato, non l'aggancio"
            )
        return bollette, ""

    def _verifica_in_blocco(self, piano: dict) -> list:
        """Applica il piano in un savepoint e torna i periodi che il pinning
        allontanerebbe dagli importi addebitati (lista vuota = piano sano)."""
        from billing.calc.utility import calcola_conguaglio_periodo

        if not piano:
            return []
        prima = {
            pk: calcola_conguaglio_periodo(pk, persist=False)["totali_per_voce"]
            for pk in piano
        }
        with transaction.atomic():
            sid = transaction.savepoint()
            for period, bollette in piano.values():
                period.utility_bills.set(bollette)
            dopo = {
                pk: calcola_conguaglio_periodo(pk, persist=False)["totali_per_voce"]
                for pk in piano
            }
            transaction.savepoint_rollback(sid)
        return [
            pk
            for pk, (period, _b) in piano.items()
            if self._scarto(dopo[pk], period) > self._scarto(prima[pk], period) + CENTESIMO
        ]

    @staticmethod
    def _scarto(totali: dict, period) -> Decimal:
        """Distanza tra il ricalcolo e i tot_* addebitati (la verità storica).

        La TARI non entra: viene dai costi annuali, non dalle bollette.
        """
        ricalcolo = sum(
            (v for k, v in totali.items() if k != "tari"), Decimal("0.00")
        )
        addebitato = (
            (period.tot_luce or Decimal("0"))
            + (period.tot_gas or Decimal("0"))
            + (period.tot_altro or Decimal("0"))
        )
        return abs(ricalcolo - addebitato)

    def _riga_ok(self, period, bollette) -> None:
        from billing.calc.utility import _giorni_intersezione

        pezzi = []
        for b in bollette:
            giorni_b = (b.periodo_a - b.periodo_da).days + 1
            giorni = _giorni_intersezione(
                b.periodo_da, b.periodo_a, period.periodo_da, period.periodo_a
            )
            quota = (
                f"{b.importo_ripartibile}€"
                if giorni >= giorni_b
                else f"{b.importo_ripartibile}€×{giorni}/{giorni_b}gg"
            )
            pezzi.append(f"{b.pk}:{b.prodotto}:{quota}")
        self.stdout.write(
            self.style.SUCCESS(
                f"  [{period.pk}] {period.periodo_da} → {period.periodo_a} "
                f"pin {len(bollette)} → {' '.join(pezzi)}"
            )
        )
