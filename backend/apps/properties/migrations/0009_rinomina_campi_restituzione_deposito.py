from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0008_roomassignment_costo_cessione'),
    ]

    operations = [
        migrations.RenameField(
            model_name='tenantprofile',
            old_name='deposito_restituito',
            new_name='deposito_da_restituire',
        ),
        migrations.RenameField(
            model_name='tenantprofile',
            old_name='data_restituzione_deposito',
            new_name='data_restituzione_prevista',
        ),
        migrations.AlterField(
            model_name='tenantprofile',
            name='deposito_da_restituire',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Importo lordo da rendere all'uscita. Se vuoto si "
                "assume pari al deposito versato; valorizzalo solo se "
                "differisce (es. rimborsi aggiuntivi a favore dell'inquilino).",
                max_digits=10,
                null=True,
                verbose_name='deposito da restituire',
            ),
        ),
        migrations.AlterField(
            model_name='tenantprofile',
            name='data_restituzione_prevista',
            field=models.DateField(
                blank=True,
                help_text='Data in cui la restituzione è dovuta. '
                'Valorizzandola viene generato il Receivable DEPOSITO di '
                'restituzione (importo negativo). La restituzione effettiva '
                'si deduce dal pagamento di quel Receivable.',
                null=True,
                verbose_name='data restituzione prevista',
            ),
        ),
    ]
