"""La quota condominio appartiene all'immobile; il contratto è facoltativo.

Backfill: ogni riga esistente prende l'immobile dal proprio contratto (la FK
era obbligatoria, quindi nessuna riga resta senza immobile).
"""
import django.db.models.deletion
from django.db import migrations, models


def popola_property(apps, schema_editor):
    TenantCondominioRate = apps.get_model("billing", "TenantCondominioRate")
    for rata in TenantCondominioRate.objects.select_related("contract").iterator():
        rata.property_id = rata.contract.property_id
        rata.save(update_fields=["property"])


def svuota_property(apps, schema_editor):
    """All'indietro: le quote senza contratto non hanno dove tornare."""
    TenantCondominioRate = apps.get_model("billing", "TenantCondominioRate")
    TenantCondominioRate.objects.filter(contract__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0027_alter_expense_allegato_alter_receivable_ricevuta_and_more"),
        ("properties", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantcondominiorate",
            name="property",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="quote_condominio",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.RunPython(popola_property, svuota_property),
        migrations.AlterField(
            model_name="tenantcondominiorate",
            name="property",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="quote_condominio",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AlterField(
            model_name="tenantcondominiorate",
            name="contract",
            field=models.ForeignKey(
                blank=True,
                help_text="Facoltativo: il contratto in cui la quota è pattuita.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="quote_condominio_inquilini",
                to="properties.contract",
                verbose_name="contratto",
            ),
        ),
    ]
