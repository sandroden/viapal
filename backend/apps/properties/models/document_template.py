"""
Modelli dei documenti generati, uno per immobile.

Il testo di un atto di subentro o di una comunicazione di cessione di
fabbricato non è codice: cambia da proprietà a proprietà (clausole, articoli
richiamati, intestazioni) e chi lo cambia è il proprietario, non chi
sviluppa. Sta quindi in tabella, come ``MessageTemplate`` fa per le email,
e nel repository resta solo un esempio da adattare.

Il corpo è un documento HTML completo — ``<style>`` incluso — con
segnaposto ``{{chiave}}`` sostituiti alla generazione. Non è un template
Django: la sostituzione è una ``str.replace`` (vedi
``properties.documenti.base``), così un HTML caricato da un utente non può
eseguire nulla.
"""
from django.db import models

from ._base import TimestampedModel


class DocumentTemplate(TimestampedModel):
    """Modello di un documento generabile, specifico di un immobile."""

    class Codice(models.TextChoices):
        ATTO_SUBENTRO_LOCAZIONE = (
            "atto_subentro_locazione",
            "Atto di subentro nel contratto",
        )
        CESSIONE_FABBRICATO = (
            "cessione_fabbricato",
            "Comunicazione di cessione di fabbricato",
        )

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="document_templates",
        verbose_name="immobile",
    )
    codice = models.CharField(
        max_length=40,
        choices=Codice.choices,
        verbose_name="documento",
    )
    nome = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="nome",
        help_text="Etichetta libera, es. 'Atto di subentro 2026'.",
    )
    corpo_html = models.TextField(
        verbose_name="corpo (HTML)",
        help_text=(
            "Documento HTML completo, CSS incluso, con segnaposto "
            "{{chiave}}. L'elenco dei segnaposto disponibili è quello del "
            "documento scelto."
        ),
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "modello documento"
        verbose_name_plural = "modelli documento"
        ordering = ["property", "codice"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "codice"],
                name="document_template_codice_unique_per_property",
            ),
        ]

    def __str__(self):
        return self.nome or self.get_codice_display()
