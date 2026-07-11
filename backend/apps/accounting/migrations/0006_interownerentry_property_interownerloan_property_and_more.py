# Multiproprietà — Fase A (accounting).
#
# Aggancia a Property partitario ufficiale, chiusure e partitario
# bilaterale. Backfill sull'unico immobile esistente.
import django.db.models.deletion
from django.db import migrations, models

_CAMPI = (
    ("InterOwnerEntry", "inter_owner_entries"),
    ("InterOwnerLoan", "inter_owner_loans"),
    ("OwnerLedgerEntry", "owner_ledger_entries"),
    ("OwnerSettlement", "owner_settlements"),
    ("WithholdingRule", "withholding_rules"),
)


def backfill_property(apps, schema_editor):
    Property = apps.get_model("properties", "Property")
    prop = Property.objects.order_by("pk").first()

    modelli = [apps.get_model("accounting", nome) for nome, _ in _CAMPI]
    if not any(m.objects.exists() for m in modelli):
        return
    if prop is None:
        prop = Property.objects.create(nome="Immobile")
    for modello in modelli:
        modello.objects.filter(property__isnull=True).update(property=prop)


def _fk(related_name):
    return models.ForeignKey(
        on_delete=django.db.models.deletion.PROTECT,
        related_name=related_name,
        to="properties.property",
        verbose_name="immobile",
    )


def _fk_nullable(related_name):
    return models.ForeignKey(
        null=True,
        on_delete=django.db.models.deletion.PROTECT,
        related_name=related_name,
        to="properties.property",
        verbose_name="immobile",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0005_interownerentry_riferimento_settlement"),
        ("properties", "0014_alter_ownershipshare_options_contract_property_and_more"),
    ]

    operations = (
        [
            migrations.AddField(
                model_name=nome.lower(),
                name="property",
                field=_fk_nullable(related_name),
            )
            for nome, related_name in _CAMPI
        ]
        + [migrations.RunPython(backfill_property, migrations.RunPython.noop)]
        + [
            migrations.AlterField(
                model_name=nome.lower(),
                name="property",
                field=_fk(related_name),
            )
            for nome, related_name in _CAMPI
        ]
    )
