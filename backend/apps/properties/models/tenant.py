"""
Modelli relativi agli inquilini.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from ._base import TimestampedModel


class TenantProfile(TimestampedModel):
    """Profilo anagrafico di un inquilino."""

    class FrequenzaConguagli(models.TextChoices):
        MENSILE = "mensile", "Mensile"
        BIMESTRALE = "bimestrale", "Bimestrale"

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
    note_pagamento = models.TextField(
        blank=True,
        verbose_name="note pagamento",
    )

    class Meta:
        verbose_name = "profilo inquilino"
        verbose_name_plural = "profili inquilini"
        ordering = ["nominativo"]

    def __str__(self):
        return self.nominativo
