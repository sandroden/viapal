"""
Modelli per stati di pagamento e transazioni bancarie.

Gli addebiti inquilino (affitto, utenze, extra) vivono ora nel modello
unificato Receivable in `receivables.py`.
"""
from decimal import Decimal

from django.db import models
from django.db.models import Sum

from properties.models import OwnerBankAccount, TimestampedModel


class StatoPagamento(models.TextChoices):
    ATTESO = "atteso", "Atteso"
    DICHIARATO = "dichiarato", "Dichiarato (da confermare)"
    PAGATO = "pagato", "Pagato"
    IN_RITARDO = "in_ritardo", "In ritardo"
    INSOLUTO = "insoluto", "Insoluto"


class BankTransactionQuerySet(models.QuerySet):
    """Helper per filtrare le BT per stato di riconciliazione."""

    def annotate_riconciliazione(self):
        return self.annotate(_importo_allocato=Sum("allocations__importo"))

    def non_riconciliate(self):
        """BT con somma allocations < importo (entrate non completamente
        riconciliate). Le uscite (importo ≤ 0) sono escluse: non c'è nulla
        da riconciliare con un Receivable."""
        return self.annotate_riconciliazione().filter(importo__gt=0).filter(
            models.Q(_importo_allocato__isnull=True)
            | models.Q(_importo_allocato__lt=models.F("importo"))
        )

    def riconciliate(self):
        return self.annotate_riconciliazione().filter(
            _importo_allocato=models.F("importo")
        )


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

    objects = BankTransactionQuerySet.as_manager()

    class Meta:
        verbose_name = "transazione bancaria"
        verbose_name_plural = "transazioni bancarie"
        ordering = ["-data"]

    def __str__(self):
        segno = "+" if self.importo >= 0 else ""
        return f"{self.data} — {segno}{self.importo}€ ({self.owner_account.banca})"

    @property
    def importo_allocato(self) -> Decimal:
        """Somma degli importi delle allocations di questa BT."""
        agg = self.allocations.aggregate(tot=Sum("importo"))["tot"]
        return agg or Decimal("0")

    @property
    def is_riconciliato(self) -> bool:
        """``True`` se l'importo della BT è completamente coperto dalle sue
        allocations. Una BT non riconciliata è candidata al matching."""
        if self.importo <= 0:
            return True  # uscite: non riconciliabili con Receivable
        return self.importo_allocato >= self.importo

    @property
    def residuo(self) -> Decimal:
        """Importo del bonifico non ancora attribuito a un Receivable.

        Positivo = soldi del bonifico non legati a nessun addebito (es.
        sopra-pagamento, spese non modellate). Zero = riconciliato pieno.
        Negativo non dovrebbe mai succedere (allocato > importo): se accade
        c'è un'incoerenza nei dati.
        """
        if self.importo <= 0:
            return Decimal("0")
        return self.importo - self.importo_allocato

    @property
    def stato_riconciliazione(self) -> str:
        """Tre livelli: ``"pieno"``, ``"parziale"``, ``"vuoto"``.

        - **pieno**: tutto l'importo della BT è coperto da allocations.
        - **parziale**: almeno un'allocation, ma con residuo > 0
          (sopra-pagamento o spese non modellate).
        - **vuoto**: nessuna allocation.
        """
        if self.importo <= 0:
            return "pieno"
        allocato = self.importo_allocato
        if allocato >= self.importo:
            return "pieno"
        if allocato > 0:
            return "parziale"
        return "vuoto"
