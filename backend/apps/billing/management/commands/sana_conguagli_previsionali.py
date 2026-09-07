"""
Riallinea le rettifiche dei previsionali alla regola "annulla la stima".

Fino al 2026-09-07 la rettifica del conguaglio valeva −somma delle utenze
reali: bolletta e rettifica si annullavano e il dovuto restava la stima,
qualunque fossero le bollette. Ora vale −previsionale (vedi
``dashboard_views/previsionale.py``). Questo comando porta le rettifiche
esistenti alla nuova regola: importo = −previsionale, descrizione aggiornata.

Dry-run di default; ``--apply`` per scrivere. Salta (e segnala) le rettifiche
con allocazioni: un dato riconciliato non si tocca (guardia allocations).
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from billing.dashboard_views.previsionale import descrizione_rettifica
from billing.models import Receivable


class Command(BaseCommand):
    help = "Rettifiche dei previsionali: importo = −previsionale (dry-run senza --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Scrive le modifiche.")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        rettifiche = (
            Receivable.objects.filter(conguaglio_di__isnull=False)
            .select_related("conguaglio_di", "assignment__tenant")
            .order_by("id")
        )
        da_fare = saltate = ok = 0
        for rett in rettifiche:
            prev = rett.conguaglio_di
            atteso = (-prev.importo_dovuto).quantize(Decimal("0.01"))
            nome = rett.assignment.tenant.nominativo
            if rett.importo_dovuto == atteso:
                ok += 1
                continue
            if rett.allocations.exists():
                saltate += 1
                self.stdout.write(self.style.WARNING(
                    f"SALTATA rettifica {rett.id} ({nome}): ha allocazioni, "
                    f"importo {rett.importo_dovuto} ≠ {atteso}"
                ))
                continue
            da_fare += 1
            self.stdout.write(
                f"rettifica {rett.id} ({nome}): {rett.importo_dovuto} → {atteso}"
            )
            if apply:
                with transaction.atomic():
                    rett.importo_dovuto = atteso
                    rett.descrizione = descrizione_rettifica(prev)
                    rett.save(update_fields=["importo_dovuto", "descrizione", "updated_at"])
        verbo = "aggiornate" if apply else "da aggiornare"
        self.stdout.write(self.style.SUCCESS(
            f"{da_fare} {verbo}, {ok} già corrette, {saltate} saltate"
            + ("" if apply else " (dry-run: aggiungi --apply)")
        ))
