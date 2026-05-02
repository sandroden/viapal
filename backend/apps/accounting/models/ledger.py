"""
Partitario ufficiale tra i proprietari (Livello A).
"""
from django.db import models

from properties.models import OwnerProfile, TimestampedModel


class OwnerLedgerEntry(TimestampedModel):
    """Voce del partitario ufficiale Viapal per un proprietario."""

    class TipoVoce(models.TextChoices):
        INCASSO_AFFITTO = "incasso_affitto", "Incasso affitto"
        INCASSO_CONGUAGLIO = "incasso_conguaglio", "Incasso conguaglio"
        SPESA = "spesa", "Spesa"
        DISTRIBUZIONE = "distribuzione", "Distribuzione utili"
        AGGIUSTAMENTO = "aggiustamento", "Aggiustamento"

    owner = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="ledger_entries",
        verbose_name="proprietario",
    )
    data = models.DateField(
        verbose_name="data",
    )
    descrizione = models.CharField(
        max_length=300,
        verbose_name="descrizione",
    )
    importo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="importo",
        help_text="Positivo = credito, negativo = debito.",
    )
    tipo = models.CharField(
        max_length=30,
        choices=TipoVoce.choices,
        verbose_name="tipo voce",
    )
    riferimento_payment = models.ForeignKey(
        "billing.RentPayment",
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
        null=True,
        blank=True,
        verbose_name="pagamento affitto collegato",
    )
    riferimento_charge = models.ForeignKey(
        "billing.UtilityCharge",
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
        null=True,
        blank=True,
        verbose_name="conguaglio collegato",
    )
    riferimento_expense = models.ForeignKey(
        "billing.Expense",
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
        null=True,
        blank=True,
        verbose_name="spesa collegata",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "voce partitario proprietario"
        verbose_name_plural = "voci partitario proprietari"
        ordering = ["-data", "owner__nominativo"]

    def __str__(self):
        segno = "+" if self.importo >= 0 else ""
        return f"{self.owner} — {self.data} {segno}{self.importo}€ ({self.get_tipo_display()})"


class OwnerSettlement(TimestampedModel):
    """Chiusura periodica dei conti tra i proprietari."""

    data = models.DateField(
        verbose_name="data",
    )
    periodo_da = models.DateField(
        verbose_name="periodo dal",
    )
    periodo_a = models.DateField(
        verbose_name="periodo al",
    )
    descrizione = models.CharField(
        max_length=300,
        verbose_name="descrizione",
    )
    snapshot = models.JSONField(
        verbose_name="snapshot saldi",
        help_text="Saldi per proprietario al momento della chiusura: {owner_id: saldo}",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "chiusura conti"
        verbose_name_plural = "chiusure conti"
        ordering = ["-data"]

    def __str__(self):
        return f"Chiusura {self.periodo_da} / {self.periodo_a} — {self.data}"
