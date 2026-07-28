"""Riallinea ``importo_pagato`` dei Receivable in stato DICHIARATO.

Contesto
--------

Fino al fix, l'action ``dichiara_pagato`` sovrascriveva ``importo_pagato``
con l'intero dovuto: un addebito coperto solo in parte dai bonifici
(es. 33,50 su 44,10) perdeva il residuo e nella home inquilino appariva
"0,00 €" senza indicatore di pagamento parziale.

Questo command sana i dati esistenti: per ogni Receivable in stato
``dichiarato`` ricalcola ``importo_pagato`` dalla somma delle sue
``BankTransactionAllocation`` (None se non ce ne sono), senza toccare lo
stato — la dichiarazione dell'inquilino resta valida e in attesa di
conferma. Idempotente.

Default è dry-run; servono ``--apply`` per scrivere::

    uv run manage.py riallinea_dichiarati            # dry-run
    uv run manage.py riallinea_dichiarati --apply
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from billing.models import Receivable
from billing.models.payments import StatoPagamento


class Command(BaseCommand):
    help = (
        "Ricalcola importo_pagato dalle allocazioni per i Receivable in "
        "stato 'dichiarato' (sovrascritti dal vecchio dichiara_pagato). "
        "Default dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Scrive le modifiche (default: dry-run).",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        qs = (
            Receivable.objects.filter(stato=StatoPagamento.DICHIARATO)
            .annotate(coperto=Sum("allocations__importo"))
            .select_related("assignment__tenant")
            .order_by("scadenza")
        )

        da_sistemare = 0
        with transaction.atomic():
            for r in qs:
                coperto = r.coperto  # None se nessuna allocazione
                if r.importo_pagato == coperto:
                    continue
                da_sistemare += 1
                tenant = r.assignment.tenant.nominativo if r.assignment_id else "?"
                self.stdout.write(
                    f"  #{r.id} {tenant} — {r.causale} scad. {r.scadenza} "
                    f"dovuto {r.importo_dovuto} · pagato {r.importo_pagato} "
                    f"→ {coperto if coperto is not None else 'None'}"
                )
                if apply:
                    r.importo_pagato = coperto
                    r.save(update_fields=["importo_pagato", "updated_at"])

            if not apply:
                transaction.set_rollback(True)

        if da_sistemare == 0:
            self.stdout.write(self.style.SUCCESS("Nessun dichiarato da riallineare."))
        elif apply:
            self.stdout.write(
                self.style.SUCCESS(f"Riallineati {da_sistemare} receivable.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry-run: {da_sistemare} receivable da riallineare "
                    "(rilancia con --apply)."
                )
            )
