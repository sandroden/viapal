# Multiproprietà — Fase A (notifications).
#
# Template messaggi e regole solleciti diventano per-immobile.
# Backfill sull'unico immobile esistente.
import django.db.models.deletion
from django.db import migrations, models


def backfill_property(apps, schema_editor):
    Property = apps.get_model("properties", "Property")
    prop = Property.objects.order_by("pk").first()

    MessageTemplate = apps.get_model("notifications", "MessageTemplate")
    ReminderRule = apps.get_model("notifications", "ReminderRule")

    if not (MessageTemplate.objects.exists() or ReminderRule.objects.exists()):
        return
    if prop is None:
        prop = Property.objects.create(nome="Immobile")

    MessageTemplate.objects.filter(property__isnull=True).update(property=prop)
    ReminderRule.objects.filter(property__isnull=True).update(property=prop)


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0002_alter_reminderrule_applicabile_a"),
        ("properties", "0014_alter_ownershipshare_options_contract_property_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="messagetemplate",
            name="property",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="message_templates",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AddField(
            model_name="reminderrule",
            name="property",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reminder_rules",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.RunPython(backfill_property, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="messagetemplate",
            name="property",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="message_templates",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AlterField(
            model_name="reminderrule",
            name="property",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reminder_rules",
                to="properties.property",
                verbose_name="immobile",
            ),
        ),
        migrations.AlterField(
            model_name="messagetemplate",
            name="codice",
            field=models.SlugField(
                help_text="Identificativo del template (es. 'affitto_promemoria_pre'), univoco per immobile.",
                verbose_name="codice",
            ),
        ),
        migrations.AddConstraint(
            model_name="messagetemplate",
            constraint=models.UniqueConstraint(
                fields=("property", "codice"),
                name="message_template_codice_unique_per_property",
            ),
        ),
    ]
