"""
Modelli relativi agli inquilini.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from ._base import TimestampedModel


class TenantProfile(TimestampedModel):
    """Profilo anagrafico di un inquilino."""

    class FrequenzaConguagli(models.TextChoices):
        MENSILE = "mensile", "Mensile"
        BIMESTRALE = "bimestrale", "Bimestrale"

    class CicloFatturazione(models.TextChoices):
        SOLARE = "solare", "Mese solare (1-31)"
        INGRESSO = "ingresso", "Dal giorno di ingresso"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tenant_profile",
        verbose_name="utente",
    )
    nominativo = models.CharField(
        max_length=200,
        verbose_name="nominativo",
    )
    codice_fiscale = models.CharField(
        max_length=16,
        blank=True,
        verbose_name="codice fiscale",
    )
    telefono = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="telefono",
    )
    email_alt = models.EmailField(
        blank=True,
        verbose_name="email alternativa",
    )
    giorno_pagamento_affitto = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        verbose_name="giorno pagamento affitto",
        help_text="Giorno del mese in cui l'inquilino paga (1-28).",
    )
    frequenza_conguagli = models.CharField(
        max_length=20,
        choices=FrequenzaConguagli.choices,
        default=FrequenzaConguagli.MENSILE,
        verbose_name="frequenza conguagli",
    )
    ciclo_fatturazione = models.CharField(
        max_length=20,
        choices=CicloFatturazione.choices,
        default=CicloFatturazione.SOLARE,
        verbose_name="ciclo fatturazione affitto",
        help_text=(
            "Solare: mese di calendario (1-31), con pro-rata su ingresso/uscita "
            "infra-mese. Ingresso: mensilità dal giorno di valid_from al giorno "
            "precedente del mese successivo (es. 9/2-8/3), canone pieno tranne "
            "moncone finale all'uscita."
        ),
    )
    note_pagamento = models.TextField(
        blank=True,
        verbose_name="note pagamento",
    )

    deposito_versato = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="deposito versato",
        help_text="Deposito versato dall'inquilino. Vale per l'intero rapporto, "
        "anche se l'inquilino cambia stanza o contratto.",
    )
    data_versamento_deposito = models.DateField(
        null=True,
        blank=True,
        verbose_name="data versamento deposito",
    )
    deposito_da_restituire = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="deposito da restituire",
        help_text="Importo lordo da rendere all'uscita. Se vuoto si assume "
        "pari al deposito versato; valorizzalo solo se differisce (es. "
        "rimborsi aggiuntivi a favore dell'inquilino).",
    )
    data_restituzione_prevista = models.DateField(
        null=True,
        blank=True,
        verbose_name="data restituzione prevista",
        help_text="Data in cui la restituzione è dovuta. Valorizzandola "
        "viene generato il Receivable DEPOSITO di restituzione (importo "
        "negativo). La restituzione effettiva si deduce dal pagamento di "
        "quel Receivable.",
    )

    class Meta:
        verbose_name = "profilo inquilino"
        verbose_name_plural = "profili inquilini"
        ordering = ["nominativo"]

    def __str__(self):
        return self.nominativo
