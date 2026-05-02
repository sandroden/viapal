"""
Mixin astratto condiviso da tutti i modelli del progetto.
"""
from django.db import models


class TimestampedModel(models.Model):
    """Mixin astratto: aggiunge created_at e updated_at a ogni modello figlio."""

    created_at = models.DateTimeField(
        verbose_name="creato il",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        verbose_name="aggiornato il",
        auto_now=True,
    )

    class Meta:
        abstract = True
