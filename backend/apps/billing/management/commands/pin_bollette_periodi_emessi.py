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

Regole (conservative per costruzione)
-------------------------------------
Un periodo emesso viene pinnato solo se:

1. **tutte** le bollette che lo intersecano vi sono interamente contenute —
   il pinning conta l'importo intero, quindi su una bolletta a cavallo
   cambierebbe i numeri (e un pinning parziale perderebbe il contributo di
   quella a cavallo);
2. la ricostruzione combacia con i ``tot_*`` già persistiti entro
   ``--tolleranza`` — se il periodo fu emesso con più di quanto le bollette
   a DB giustifichino, il dato mancante è la bolletta, e scrivere la M2M
   registrerebbe una mezza verità.

Ne segue l'invariante: **il pinning non cambia nessun importo**. Il comando
lo verifica sui dati veri prima di applicare (ricalcolo prima/dopo dentro un
savepoint) e rifiuta di pinnare i periodi che non lo rispettano.

Uso::

    uv run manage.py pin_bollette_periodi_emessi              # dry-run
    uv run manage.py pin_bollette_periodi_emessi --apply
    uv run manage.py pin_bollette_periodi_emessi --year 2026
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from properties.context import resolve_property_cli


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
            "--tolleranza",
            type=str,
            default="1.00",
            help="Scarto ammesso tra bollette ricostruite e tot_* persistiti (€).",
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
        tolleranza = Decimal(options["tolleranza"])
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

        pinnati = saltati = 0
        for period in periodi:
            esito = self._valuta(period, tolleranza)
            if esito["ok"]:
                if applica:
                    with transaction.atomic():
                        period.utility_bills.set(esito["bollette"])
                pinnati += 1
            else:
                saltati += 1
            self._riga(period, esito)

        prefix = "" if applica else "[DRY-RUN] "
        self.stdout.write("")
        self.stdout.write(
            f"{prefix}Periodi emessi senza bollette agganciate: {periodi.count()} "
            f"— pinnabili {pinnati}, da guardare a mano {saltati}"
        )
        if not applica and pinnati:
            self.stdout.write("Rilancia con --apply per scrivere gli agganci.")

    # ------------------------------------------------------------------
    def _valuta(self, period, tolleranza: Decimal) -> dict:
        """Decide se il periodo è pinnabile e verifica l'invariante sui dati."""
        from billing.calc.utility import (
            _giorni_intersezione,
            _voci_fatturabili,
            calcola_conguaglio_periodo,
        )
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
            return {"ok": False, "motivo": "nessuna bolletta interseca il periodo"}

        a_cavallo = [
            b
            for b in bollette
            if _giorni_intersezione(
                b.periodo_da, b.periodo_a, period.periodo_da, period.periodo_a
            )
            < (b.periodo_a - b.periodo_da).days + 1
        ]
        if a_cavallo:
            elenco = ", ".join(
                f"{b.pk}:{b.prodotto} {b.periodo_da}→{b.periodo_a}" for b in a_cavallo
            )
            return {"ok": False, "motivo": f"bollette a cavallo ({elenco})"}

        ricostruito = sum((b.importo_ripartibile for b in bollette), Decimal("0.00"))
        persistito = (
            (period.tot_luce or Decimal("0"))
            + (period.tot_gas or Decimal("0"))
            + (period.tot_altro or Decimal("0"))
        )
        delta = ricostruito - persistito
        if abs(delta) > tolleranza:
            return {
                "ok": False,
                "motivo": (
                    f"le bollette a DB giustificano {ricostruito:.2f} € dei "
                    f"{persistito:.2f} € addebitati (delta {delta:+.2f} €): "
                    f"manca una bolletta, non l'aggancio"
                ),
            }

        # Invariante: il pinning non deve cambiare nessun importo. Verificato
        # sui dati veri, non solo in test: pin dentro un savepoint, ricalcolo,
        # rollback.
        prima = calcola_conguaglio_periodo(period.pk, persist=False)
        with transaction.atomic():
            sid = transaction.savepoint()
            period.utility_bills.set(bollette)
            dopo = calcola_conguaglio_periodo(period.pk, persist=False)
            transaction.savepoint_rollback(sid)
        if prima["totali_per_voce"] != dopo["totali_per_voce"]:
            return {
                "ok": False,
                "motivo": (
                    f"il pinning cambierebbe gli importi: "
                    f"{prima['totali_per_voce']} → {dopo['totali_per_voce']}"
                ),
            }

        return {"ok": True, "bollette": bollette, "delta": delta}

    def _riga(self, period, esito: dict) -> None:
        testa = f"  [{period.pk}] {period.periodo_da} → {period.periodo_a}"
        if esito["ok"]:
            elenco = " ".join(
                f"{b.pk}:{b.prodotto}:{b.importo_ripartibile}€" for b in esito["bollette"]
            )
            self.stdout.write(
                self.style.SUCCESS(f"{testa} pin {len(esito['bollette'])} → {elenco}")
            )
        else:
            self.stdout.write(self.style.WARNING(f"{testa} salto: {esito['motivo']}"))
