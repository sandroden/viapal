from django.db import migrations


def fix(apps, schema_editor):
    Receivable = apps.get_model("billing", "Receivable")
    Receivable.objects.filter(
        descrizione="Caparra in natura: materasso (BT 2602)"
    ).update(descrizione="Deposito in natura: materasso")


def unfix(apps, schema_editor):
    Receivable = apps.get_model("billing", "Receivable")
    Receivable.objects.filter(
        descrizione="Deposito in natura: materasso"
    ).update(descrizione="Caparra in natura: materasso (BT 2602)")


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0020_normalizza_descrizioni_deposito'),
    ]

    operations = [
        migrations.RunPython(fix, unfix),
    ]
