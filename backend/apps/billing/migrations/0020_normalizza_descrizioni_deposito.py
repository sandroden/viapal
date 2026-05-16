from django.db import migrations


def caparra_to_deposito_descr(apps, schema_editor):
    Receivable = apps.get_model("billing", "Receivable")
    for vecchio, nuovo in (
        ("Caparra (versamento)", "Deposito (versamento)"),
        ("Caparra (restituzione)", "Deposito (restituzione)"),
    ):
        Receivable.objects.filter(descrizione=vecchio).update(descrizione=nuovo)


def deposito_to_caparra_descr(apps, schema_editor):
    Receivable = apps.get_model("billing", "Receivable")
    for nuovo, vecchio in (
        ("Deposito (versamento)", "Caparra (versamento)"),
        ("Deposito (restituzione)", "Caparra (restituzione)"),
    ):
        Receivable.objects.filter(descrizione=nuovo).update(descrizione=vecchio)


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0019_alter_receivable_causale'),
    ]

    operations = [
        migrations.RunPython(
            caparra_to_deposito_descr, deposito_to_caparra_descr
        ),
    ]
