# Multiproprietà — Fase A (billing).
#
# Aggancia a Property i modelli finora globali. Backfill: tutte le righe
# esistenti vengono attribuite all'unico immobile esistente.
import django.db.models.deletion
from django.db import migrations, models

_MODELLI = ("AnnualUtilityCost", "Expense", "ExpenseCategory", "Supplier", "UtilityChargePeriod")


def backfill_property(apps, schema_editor):
    Property = apps.get_model("properties", "Property")
    prop = Property.objects.order_by("pk").first()

    modelli = [apps.get_model("billing", nome) for nome in _MODELLI]
    UtilityBill = apps.get_model("billing", "UtilityBill")

    ha_righe = any(m.objects.exists() for m in modelli) or UtilityBill.objects.exists()
    if not ha_righe:
        return
    if prop is None:
        prop = Property.objects.create(nome="Immobile")

    for modello in modelli:
        modello.objects.filter(property__isnull=True).update(property=prop)
    UtilityBill.objects.filter(immobile__isnull=True).update(immobile=prop)


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0023_utilitybill_immobile_alter_utilitybill_file_pdf"),
        ("properties", "0014_alter_ownershipshare_options_contract_property_and_more"),
    ]

    operations = [
        # --- FK property: prima nullable, poi backfill, poi NOT NULL ------
        migrations.AddField(
            model_name="annualutilitycost",
            name="property",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="annual_utility_costs",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AddField(
            model_name="expense",
            name="property",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="expenses",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AddField(
            model_name="expensecategory",
            name="property",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="expense_categories",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AddField(
            model_name="supplier",
            name="property",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="suppliers",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AddField(
            model_name="utilitychargeperiod",
            name="property",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="utility_periods",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.RunPython(backfill_property, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="annualutilitycost",
            name="property",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="annual_utility_costs",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AlterField(
            model_name="expense",
            name="property",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="expenses",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AlterField(
            model_name="expensecategory",
            name="property",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="expense_categories",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AlterField(
            model_name="supplier",
            name="property",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="suppliers",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AlterField(
            model_name="utilitychargeperiod",
            name="property",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="utility_periods",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AlterField(
            model_name="utilitybill",
            name="immobile",
            field=models.ForeignKey(
                help_text="Immobile a cui appartiene la bolletta.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="utility_bills",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AlterField(
            model_name="expensecategory",
            name="codice",
            field=models.SlugField(verbose_name="codice"),
        ),
        migrations.AddConstraint(
            model_name="expensecategory",
            constraint=models.UniqueConstraint(
                fields=("property", "codice"),
                name="expense_category_codice_unique_per_property",
            ),
        ),
    ]
