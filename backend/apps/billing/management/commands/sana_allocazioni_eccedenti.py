"""Sana le ``BankTransactionAllocation`` che eccedono l'importo della loro BT.

Contesto
--------

Le allocazioni nascono già validate: sia la riconciliazione da frontend
(``POST bank-transactions/riconcilia/``) sia ``registra-pagamento``
garantiscono che la somma algebrica delle allocations di una BT non superi
``BankTransaction.importo`` in valore assoluto.

L'invariante però si rompe **a posteriori**: se si corregge l'importo di una
BT già riconciliata (tipicamente da admin, dopo un errore di digitazione) le
allocations restano quelle di prima, e il Receivable continua a risultare
pagato per un importo mai incassato.

Il command trova le BT sovra-allocate e riduce le allocations — a partire
dalla più recente — fino a farle rientrare nell'importo del movimento;
un'allocazione che si azzera viene eliminata. Poi riallinea i Receivable
coinvolti (``stato``/``data_pagamento``/``importo_pagato``). Idempotente.

Non tocca le BT con ``importo = 0`` (nulla su cui clampare: vanno guardate a
mano) e non tocca le allocations di segno opposto alla BT, che sono
legittime — es. restituzione deposito con trattenuta utenze: BT −984 ↔
alloc −1060 + alloc +76, somma −984.

Default è dry-run; serve ``--apply`` per scrivere::

    uv run manage.py sana_allocazioni_eccedenti             # dry-run
    uv run manage.py sana_allocazioni_eccedenti --apply
    uv run manage.py sana_allocazioni_eccedenti --bt 2775 --apply
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from billing.models import BankTransaction
from billing.signals import _riallinea_receivable

TOLLERANZA = Decimal("0.01")


class Command(BaseCommand):
    help = (
        "Riduce le allocazioni che eccedono l'importo della transazione "
        "bancaria (tipico dopo la correzione manuale di un importo) e "
        "riallinea i Receivable coinvolti. Default dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Scrive le modifiche (default: dry-run).",
        )
        parser.add_argument(
            "--bt",
            type=int,
            action="append",
            dest="bt_ids",
            help="Limita a una BT (ripetibile).",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        bt_ids = options.get("bt_ids")

        qs = (
            BankTransaction.objects.annotate(tot=Sum("allocations__importo"))
            .exclude(tot=None)
            .select_related("owner_account__owner")
            .order_by("data", "pk")
        )
        if bt_ids:
            qs = qs.filter(pk__in=bt_ids)

        sistemate = 0
        saltate = 0
        receivable_toccati: set[int] = set()

        with transaction.atomic():
            for bt in qs:
                somma = bt.tot or Decimal("0")
                if abs(somma) <= abs(bt.importo) + TOLLERANZA:
                    continue
                if bt.importo == 0:
                    saltate += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"  BT #{bt.pk} {bt.data} importo 0 con allocazioni "
                            f"per {somma} € — da correggere a mano."
                        )
                    )
                    continue

                sistemate += 1
                self.stdout.write(
                    f"  BT #{bt.pk} {bt.data} {bt.descrizione[:50]} — "
                    f"importo {bt.importo} €, allocato {somma} € "
                    f"(eccesso {abs(somma) - abs(bt.importo)} €)"
                )
                receivable_toccati |= self._clampa(bt, somma, apply)

            if apply:
                for r_id in receivable_toccati:
                    _riallinea_receivable(r_id)
            else:
                transaction.set_rollback(True)

        if sistemate == 0 and saltate == 0:
            self.stdout.write(
                self.style.SUCCESS("Nessuna transazione sovra-allocata.")
            )
        elif apply:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Sistemate {sistemate} transazioni "
                    f"({len(receivable_toccati)} addebiti riallineati)."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry-run: {sistemate} transazioni da sistemare "
                    "(rilancia con --apply)."
                )
            )

    def _clampa(self, bt: BankTransaction, somma: Decimal, apply: bool) -> set[int]:
        """Riduce le allocations concordi col segno della BT, dalla più
        recente, finché la somma rientra nell'importo. Ritorna gli id dei
        Receivable toccati."""
        eccesso = abs(somma) - abs(bt.importo)
        toccati: set[int] = set()
        allocs = list(
            bt.allocations.select_related("receivable__assignment__tenant").order_by(
                "-created_at", "-pk"
            )
        )
        for alloc in allocs:
            if eccesso <= 0:
                break
            if (alloc.importo > 0) != (bt.importo > 0):
                # Allocazione di segno opposto alla BT: legittima (partite
                # compensate), non è lei a generare l'eccesso.
                continue
            riducibile = min(abs(alloc.importo), eccesso)
            nuovo = alloc.importo - riducibile * (1 if alloc.importo > 0 else -1)
            tenant = (
                alloc.receivable.assignment.tenant.nominativo
                if alloc.receivable.assignment_id
                else "?"
            )
            azione = "elimina" if nuovo == 0 else f"→ {nuovo} €"
            self.stdout.write(
                f"    alloc #{alloc.pk} ({tenant} · addebito #{alloc.receivable_id} "
                f"{alloc.receivable.causale}) {alloc.importo} € {azione}"
            )
            toccati.add(alloc.receivable_id)
            if apply:
                if nuovo == 0:
                    alloc.delete()
                else:
                    alloc.importo = nuovo
                    alloc.save(update_fields=["importo", "updated_at"])
            eccesso -= riducibile
        if eccesso > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"    residuo eccesso non assorbito: {eccesso} € — "
                    "controllare a mano."
                )
            )
        return toccati
