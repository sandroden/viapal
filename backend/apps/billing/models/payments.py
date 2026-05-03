"""
Modelli per stati di pagamento e transazioni bancarie.

Gli addebiti inquilino (affitto, utenze, extra) vivono ora nel modello
unificato Receivable in `receivables.py`.
"""
from django.db import models

from properties.models import OwnerBankAccount, TimestampedModel


class StatoPagamento(models.TextChoices):
    ATTESO = "atteso", "Atteso"
    DICHIARATO = "dichiarato", "Dichiarato (da confermare)"
    PAGATO = "pagato", "Pagato"
    IN_RITARDO = "in_ritardo", "In ritardo"
    INSOLUTO = "insoluto", "Insoluto"


class BankTransaction(TimestampedModel):
    """Riga di estratto conto bancario importata.

    La riconciliazione con i Receivable (affitto/utenze/extra) avviene tramite
    `BankTransactionAllocation` (M:N) — un bonifico singolo può coprire più
    addebiti e viceversa.
    """

    data = models.DateField(
        verbose_name="data",
    )
    descrizione = models.TextField(
        verbose_name="descrizione",
    )
    importo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="importo",
        help_text="Positivo = entrata, negativo = uscita.",
    )
    owner_account = models.ForeignKey(
        OwnerBankAccount,
        on_delete=models.PROTECT,
        related_name="bank_transactions",
        verbose_name="conto proprietario",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "transazione bancaria"
        verbose_name_plural = "transazioni bancarie"
        ordering = ["-data"]

    def __str__(self):
        segno = "+" if self.importo >= 0 else ""
        return f"{self.data} — {segno}{self.importo}€ ({self.owner_account.banca})"
