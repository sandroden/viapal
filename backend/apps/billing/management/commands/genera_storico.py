"""Genera RentPayment storici per tutti i mesi dei contratti
e tenta matching automatico con BankTransaction esistenti.

Uso:
  ENV=dev uv run manage.py genera_storico --dal 2024-01 --al 2026-05
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from billing.calc.rent import genera_pagamenti_mese
from billing.models import BankTransaction, RentPayment, StatoPagamento
from properties.models import RoomAssignment


# Mappa nominativi inquilini -> stringa di match nelle descrizioni bonifici
# (case-insensitive, OR su keywords)
MATCH_INQUILINO = {
    # Le keyword sono testate in ordine, prima match vince.
    # Coprono sia descrizioni Webank ("BON.DA <NOMINATIVO>") sia
    # foglio sintetico Bruna ("ARUN", "ESHANI", "DIANA", ecc.)
    "Davide Di Maio": ["DI MAIO DAVIDE", "DI MAIO  DAVIDE", "DAVIDE"],
    "Maria Severa Armas": [
        "MARIA SEVERA ARMAS", "ARMAS MARIA SEVERA", "ARMAS MARIA  SEVERA",
        "MARIASEVERA", "SEVERA",
    ],
    "Salvatore D'Angella": ["D'ANGELLA SALVATORE", "DANGELLA SALVATORE", "SALVATORE"],
    "Eugenia Blundetto": ["BLUNDETTO EUGENIA", "EUGENIA"],
    "Marianna Di Marino": ["DI MARINO MARIANNA", "MARIANNA"],
    "Eshani Nimansha Polkotu Hetti Arachchilage": ["POLKOTU", "ESHANI"],
    "Arun Singarayar": ["SINGARAYAR ARUN", "SINGARAYAR  ARUN", "ARUN"],
    "Elisa Chiappini": ["CHIAPPINI ELISA", "CHIAPPINI  ELISA", "ELISA"],
    "Diana Carolina Porras Rodriguez": ["PORRAS DIANA", "PORRAS  DIANA", "DIANA"],
    "Lindy Jo-Anne Nyathi": ["NYATHI", "LINDY"],
}


class Command(BaseCommand):
    help = "Genera RentPayment storici e fa matching con BankTransaction."

    def add_arguments(self, parser):
        parser.add_argument("--dal", default="2024-01", help="YYYY-MM inizio")
        parser.add_argument("--al", default=None, help="YYYY-MM fine (default: oggi)")
        parser.add_argument("--no-match", action="store_true", help="Non fare matching bancario")

    def handle(self, *args, **opts):
        dal_y, dal_m = map(int, opts["dal"].split("-"))
        if opts["al"]:
            al_y, al_m = map(int, opts["al"].split("-"))
        else:
            today = date.today()
            al_y, al_m = today.year, today.month

        # 1) Genera RentPayment per ogni mese
        totale_creati = 0
        totale_aggiornati = 0
        anno, mese = dal_y, dal_m
        while (anno, mese) <= (al_y, al_m):
            res = genera_pagamenti_mese(anno, mese)
            totale_creati += res["creati"]
            totale_aggiornati += res["aggiornati"]
            if res["creati"] or res["aggiornati"]:
                self.stdout.write(f"  {anno}-{mese:02d}: +{res['creati']} creati, {res['aggiornati']} aggiornati")
            mese += 1
            if mese > 12:
                mese = 1
                anno += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nGenerati {totale_creati} RentPayment ({totale_aggiornati} aggiornati)"
        ))

        # 2) Matching con BankTransaction
        if opts["no_match"]:
            return

        n_match = 0
        for rp in RentPayment.objects.filter(stato=StatoPagamento.ATTESO):
            tenant = rp.assignment.tenant
            keywords = MATCH_INQUILINO.get(tenant.nominativo, [])
            if not keywords:
                continue
            # Cerco un BankTransaction con:
            # - importo positivo (entrata)
            # - data tra (competenza_da - 10gg) e (competenza_a + 35gg)
            # - descrizione contenente uno dei keyword
            # - non gia' riconciliato
            candidate = BankTransaction.objects.filter(
                importo__gt=0,
                data__gte=rp.competenza_da - timedelta(days=10),
                data__lte=rp.competenza_a + timedelta(days=40),
                riconciliato_con_payment__isnull=True,
            )
            for kw in keywords:
                bt = candidate.filter(descrizione__icontains=kw).order_by("data").first()
                if bt:
                    rp.stato = StatoPagamento.PAGATO
                    rp.data_pagamento = bt.data
                    rp.importo_pagato = rp.importo_dovuto  # o bt.importo (vedi caveat)
                    rp.save(update_fields=["stato", "data_pagamento", "importo_pagato", "updated_at"])
                    bt.riconciliato_con_payment = rp
                    bt.save(update_fields=["riconciliato_con_payment", "updated_at"])
                    n_match += 1
                    break

        self.stdout.write(self.style.SUCCESS(
            f"Matching: {n_match} RentPayment riconciliati con BankTransaction"
        ))

        # 3) Statistiche finali
        tot = RentPayment.objects.count()
        pagati = RentPayment.objects.filter(stato=StatoPagamento.PAGATO).count()
        attesi = RentPayment.objects.filter(stato=StatoPagamento.ATTESO).count()
        self.stdout.write(f"\nTotale RentPayment: {tot} (pagati: {pagati}, in attesa: {attesi})")
