"""
Partitario ufficiale tra i proprietari (Livello A).
"""
from django.db import models
from django.db.models import Q

from properties.models import TimestampedModel


class OwnerLedgerEntry(TimestampedModel):
    """Voce del partitario ufficiale Viapal per un proprietario."""

    class TipoVoce(models.TextChoices):
        INCASSO_AFFITTO = "incasso_affitto", "Incasso affitto"
        INCASSO_CONGUAGLIO = "incasso_conguaglio", "Incasso conguaglio"
        SPESA = "spesa", "Spesa"
        ANTICIPO = "anticipo", "Anticipo (credito da spese di tasca)"
        DISTRIBUZIONE = "distribuzione", "Distribuzione utili"
        AGGIUSTAMENTO = "aggiustamento", "Aggiustamento"

    owner = models.ForeignKey(
        "properties.OwnerProfile",
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
    riferimento_receivable = models.ForeignKey(
        "billing.Receivable",
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
        null=True,
        blank=True,
        verbose_name="addebito collegato",
    )
    riferimento_expense = models.ForeignKey(
        "billing.Expense",
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
        null=True,
        blank=True,
        verbose_name="spesa collegata",
    )
    riferimento_settlement = models.ForeignKey(
        "accounting.OwnerSettlement",
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
        null=True,
        blank=True,
        verbose_name="settlement collegato",
    )
    bank_transaction = models.ForeignKey(
        "billing.BankTransaction",
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
        null=True,
        blank=True,
        verbose_name="transazione bancaria collegata",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "voce partitario proprietario"
        verbose_name_plural = "voci partitario proprietari"
        ordering = ["-data", "owner__nominativo"]
        constraints = [
            models.UniqueConstraint(
                fields=["riferimento_receivable", "owner", "tipo"],
                condition=Q(riferimento_receivable__isnull=False),
                name="uq_ledger_per_receivable_owner_tipo",
            ),
            models.UniqueConstraint(
                fields=["riferimento_expense", "owner", "tipo"],
                condition=Q(riferimento_expense__isnull=False),
                name="uq_ledger_per_expense_owner_tipo",
            ),
        ]

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
