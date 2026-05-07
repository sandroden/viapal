"""Wipe dei dati utenze legacy.

Cancella Period + Receivable utenze + UtilityChargeLine + Allocations su utenze
per ripartire da zero col reimport dal foglio di calcolo (importa_utenze_da_xlsx).
Verificato pre-migration: 0 BankTransactionAllocation su Receivable utenze.

Spezzata dalla 0014 (modifiche schema) perche' Postgres non permette ALTER TABLE
nella stessa transazione di un DELETE che ha generato pending trigger events.
"""
from django.db import migrations


def wipe(apps, schema_editor):
    Receivable = apps.get_model('billing', 'Receivable')
    UtilityChargePeriod = apps.get_model('billing', 'UtilityChargePeriod')
    UtilityChargeLine = apps.get_model('billing', 'UtilityChargeLine')
    BankTransactionAllocation = apps.get_model('billing', 'BankTransactionAllocation')

    BankTransactionAllocation.objects.filter(receivable__causale='utenze').delete()
    UtilityChargeLine.objects.all().delete()
    Receivable.objects.filter(causale='utenze').delete()
    UtilityChargePeriod.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0012_alter_utilitychargeline_options_and_more'),
    ]

    operations = [
        migrations.RunPython(wipe, migrations.RunPython.noop),
    ]
