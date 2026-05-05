"""Genera Receivable storici (causale=affitto) per tutti i mesi dei contratti.

Uso:
  ENV=dev uv run manage.py genera_storico --dal 2024-01 --al 2026-05

La riconciliazione con i bonifici (BankTransaction → BankTransactionAllocation
→ Receivable) è ora un comando separato e idempotente:

  ENV=dev uv run manage.py riconcilia_bonifici

Lanciato dopo `genera_storico`, processa solo le BT non ancora riconciliate.
"""
from datetime import date

from django.core.management.base import BaseCommand

from billing.calc.rent import genera_pagamenti_mese
from billing.models import Receivable, StatoPagamento


class Command(BaseCommand):
    help = "Genera Receivable storici causale=affitto per ogni mese dei contratti."

    def add_arguments(self, parser):
        parser.add_argument("--dal", default="2024-01", help="YYYY-MM inizio")
        parser.add_argument("--al", default=None, help="YYYY-MM fine (default: oggi)")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Sovrascrive importo_dovuto/scadenza/competenza_a anche su "
            "Receivable già esistenti (rigenerazione storica).",
        )

    def handle(self, *args, **opts):
        dal_y, dal_m = map(int, opts["dal"].split("-"))
        if opts["al"]:
            al_y, al_m = map(int, opts["al"].split("-"))
        else:
            today = date.today()
            al_y, al_m = today.year, today.month

        totale_creati = 0
        totale_aggiornati = 0
        anno, mese = dal_y, dal_m
        while (anno, mese) <= (al_y, al_m):
            res = genera_pagamenti_mese(anno, mese, force=opts["force"])
            totale_creati += res["creati"]
            totale_aggiornati += res["aggiornati"]
            if res["creati"] or res["aggiornati"]:
                self.stdout.write(
                    f"  {anno}-{mese:02d}: +{res['creati']} creati, "
                    f"{res['aggiornati']} aggiornati"
                )
            mese += 1
            if mese > 12:
                mese = 1
                anno += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nGenerati {totale_creati} Receivable affitto "
                f"({totale_aggiornati} aggiornati)"
            )
        )

        tot = Receivable.objects.filter(causale=Receivable.Causale.AFFITTO).count()
        pagati = Receivable.objects.filter(
            causale=Receivable.Causale.AFFITTO, stato=StatoPagamento.PAGATO
        ).count()
        attesi = Receivable.objects.filter(
            causale=Receivable.Causale.AFFITTO, stato=StatoPagamento.ATTESO
        ).count()
        self.stdout.write(
            f"\nTotale Receivable affitto: {tot} "
            f"(pagati: {pagati}, in attesa: {attesi})"
        )
        self.stdout.write(
            self.style.NOTICE(
                "\nPer riconciliare con i bonifici esistenti:\n"
                "  uv run manage.py riconcilia_bonifici"
            )
        )
