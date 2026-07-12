"""Genera UtilityChargePeriod mensili dal 2024-01 in poi e calcola i
conguagli per ogni mese chiamando calcola_conguaglio_periodo(persist=True).

Uso:
  ENV=dev uv run manage.py genera_conguagli_storici --dal 2024-01 --al 2026-04
"""
from calendar import monthrange
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from billing.calc.utility import calcola_conguaglio_periodo
from billing.models import UtilityChargePeriod
from properties.context import resolve_property_cli


class Command(BaseCommand):
    help = "Genera UtilityChargePeriod mensili e calcola i conguagli."

    def add_arguments(self, parser):
        parser.add_argument("--dal", default="2024-01")
        parser.add_argument("--al", default=None)
        parser.add_argument(
            "--property", type=str, default=None,
            help="Immobile (id o nome). Obbligatorio se ci sono più immobili.",
        )

    def handle(self, *args, **opts):
        try:
            prop = resolve_property_cli(opts.get("property"))
        except ValueError as e:
            raise CommandError(str(e)) from e
        dal_y, dal_m = map(int, opts["dal"].split("-"))
        if opts["al"]:
            al_y, al_m = map(int, opts["al"].split("-"))
        else:
            t = date.today()
            al_y, al_m = t.year, t.month

        n_creati = 0
        n_calcolati = 0
        anno, mese = dal_y, dal_m
        while (anno, mese) <= (al_y, al_m):
            last = monthrange(anno, mese)[1]
            periodo, created = UtilityChargePeriod.objects.update_or_create(
                property=prop,
                periodo_da=date(anno, mese, 1),
                periodo_a=date(anno, mese, last),
                defaults={
                    "criterio_ripartizione": "pro_rata_giorni",
                    "stato": "inviato",  # storico
                    "data_invio": date(anno, mese, last),
                },
            )
            if created:
                n_creati += 1
            try:
                with transaction.atomic():
                    res = calcola_conguaglio_periodo(periodo.id, persist=True)
                n_calcolati += 1
                tot = res.get("totale_periodo", 0)
                quote_n = len(res.get("quote", []))
                self.stdout.write(f"  {anno}-{mese:02d}: tot={tot}€, quote={quote_n}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  {anno}-{mese:02d}: skip ({type(e).__name__}: {e})"))

            mese += 1
            if mese > 12:
                mese, anno = 1, anno + 1

        self.stdout.write(self.style.SUCCESS(
            f"\nPeriodi creati: {n_creati}, calcolati: {n_calcolati}"
        ))
