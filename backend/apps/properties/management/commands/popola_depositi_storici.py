"""Genera i Receivable di causale DEPOSITO per tenant esistenti il cui
deposito è già stato valorizzato su TenantProfile ma non ha ancora un
Receivable corrispondente.

Idempotente: rilancia in sicurezza, non crea duplicati.
"""
from django.core.management.base import BaseCommand

from properties.models import TenantProfile
from properties.signals import (
    _crea_deposito_restituzione,
    _crea_deposito_versamento,
)


class Command(BaseCommand):
    help = "Genera i Receivable DEPOSITO mancanti per i tenant esistenti."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra solo cosa farebbe, senza salvare.",
        )

    def handle(self, *args, **options):
        from billing.models import Receivable

        before = Receivable.objects.filter(
            causale=Receivable.Causale.DEPOSITO
        ).count()

        for tenant in TenantProfile.objects.all():
            if options["dry_run"]:
                # In dry-run, simuliamo i check senza scrivere.
                self._report_tenant(tenant)
                continue
            _crea_deposito_versamento(tenant)
            _crea_deposito_restituzione(tenant)

        after = Receivable.objects.filter(
            causale=Receivable.Causale.DEPOSITO
        ).count()
        creati = after - before
        prefix = "[DRY-RUN] " if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Receivable DEPOSITO creati: {creati} "
                f"(totale dopo: {after})"
            )
        )

    def _report_tenant(self, tenant: TenantProfile) -> None:
        from billing.models import Receivable

        if tenant.deposito_versato and tenant.deposito_versato > 0:
            esiste = Receivable.objects.filter(
                assignment__tenant=tenant,
                causale=Receivable.Causale.DEPOSITO,
                importo_dovuto__gt=0,
            ).exists()
            primo = tenant.assignments.order_by("valid_from", "id").first()
            if not esiste and primo is not None:
                self.stdout.write(
                    f"  - {tenant}: +{tenant.deposito_versato}€ "
                    f"su assignment {primo.pk}"
                )
        if tenant.deposito_restituito and tenant.deposito_restituito > 0:
            esiste = Receivable.objects.filter(
                assignment__tenant=tenant,
                causale=Receivable.Causale.DEPOSITO,
                importo_dovuto__lt=0,
            ).exists()
            ultimo = tenant.assignments.order_by("-valid_from", "-id").first()
            if not esiste and ultimo is not None:
                self.stdout.write(
                    f"  - {tenant}: -{tenant.deposito_restituito}€ "
                    f"su assignment {ultimo.pk}"
                )
