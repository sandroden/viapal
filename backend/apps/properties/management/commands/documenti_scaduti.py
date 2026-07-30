"""Report dei documenti oltre i termini di conservazione dichiarati.

Applica le regole dell'informativa privacy (docs/privacy/
informativa-inquilini.md): contratti di lavoro oltre 12 mesi dal
caricamento; documenti di inquilini usciti da oltre 5 anni. Non cancella
nulla: la rimozione resta un'azione manuale e consapevole (admin o app).
"""
import datetime

from django.core.management.base import BaseCommand
from django.db.models import Max

from properties.models import TenantDocument, TenantProfile


class Command(BaseCommand):
    help = (
        "Elenca i documenti inquilino oltre i termini di conservazione "
        "(contratto di lavoro > 12 mesi; documenti di inquilini usciti da "
        "> 5 anni). Solo report, nessuna cancellazione."
    )

    def handle(self, *args, **options):
        oggi = datetime.date.today()
        segnalati = 0

        limite_lavoro = oggi - datetime.timedelta(days=365)
        contratti_lavoro = TenantDocument.objects.filter(
            tipo=TenantDocument.Tipo.CONTRATTO_LAVORO,
            created_at__date__lt=limite_lavoro,
        ).select_related("tenant")
        if contratti_lavoro:
            self.stdout.write(self.style.WARNING(
                "Contratti di lavoro oltre 12 mesi dal caricamento "
                "(da cancellare secondo informativa):"
            ))
            for doc in contratti_lavoro:
                segnalati += 1
                self.stdout.write(
                    f"  #{doc.pk} {doc.tenant.nominativo} — caricato il "
                    f"{doc.created_at:%d/%m/%Y} — {doc.file.name}"
                )

        limite_usciti = oggi - datetime.timedelta(days=5 * 365)
        usciti = (
            TenantProfile.objects.annotate(fine=Max("assignments__valid_to"))
            .filter(fine__isnull=False, fine__lt=limite_usciti)
            .exclude(assignments__valid_to__isnull=True)
            .filter(documenti__isnull=False)
            .distinct()
        )
        if usciti:
            self.stdout.write(self.style.WARNING(
                "Inquilini usciti da oltre 5 anni con documenti ancora "
                "archiviati:"
            ))
            for tenant in usciti:
                docs = tenant.documenti.all()
                segnalati += docs.count()
                self.stdout.write(
                    f"  {tenant.nominativo} (uscito il {tenant.fine:%d/%m/%Y}): "
                    f"{docs.count()} documenti"
                )

        if segnalati:
            self.stdout.write(self.style.WARNING(f"Totale segnalazioni: {segnalati}"))
        else:
            self.stdout.write(self.style.SUCCESS(
                "Nessun documento oltre i termini di conservazione."
            ))
