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
    """Helper per filtrare le BT per stato di riconciliazione.

    Segno-aware: una BT è riconciliata quando ``Sum(allocations.importo)``
    copre ``importo`` con il segno corretto. Per le entrate (>0) significa
    ``alloc >= importo``; per le uscite (<0) — bonifici di restituzione
    caparra — significa ``alloc <= importo`` (entrambi negativi).
    """

    def annotate_riconciliazione(self):
        return self.annotate(_importo_allocato=Sum("allocations__importo"))

    def non_riconciliate(self):
        """BT non ancora completamente coperte da allocations.

        Include entrate (importo>0) con allocato<importo e uscite (importo<0)
        con allocato>importo (cioè: meno negativo del dovuto). Esclude le BT
        con importo nullo: non c'è nulla da riconciliare.
        """
        qs = self.annotate_riconciliazione().exclude(importo=0)
        return qs.filter(
            models.Q(_importo_allocato__isnull=True)
            | models.Q(importo__gt=0, _importo_allocato__lt=models.F("importo"))
            | models.Q(importo__lt=0, _importo_allocato__gt=models.F("importo"))
        )

    def riconciliate(self):
        """BT con allocazione che copre l'importo (segno-aware)."""
        qs = self.annotate_riconciliazione()
        return qs.filter(
            models.Q(importo__gt=0, _importo_allocato__gte=models.F("importo"))
            | models.Q(importo__lt=0, _importo_allocato__lte=models.F("importo"))
            | models.Q(importo=0)
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
        allocations (segno-aware). BT con ``importo == 0`` sono trattate come
        riconciliate (nulla da abbinare)."""
        if self.importo == 0:
            return True
        if self.importo > 0:
            return self.importo_allocato >= self.importo
        # Uscita: allocato e importo sono entrambi negativi (o allocato è
        # ancora 0 se non riconciliata).
        return self.importo_allocato <= self.importo

    @property
    def residuo(self) -> Decimal:
        """Importo del bonifico non ancora attribuito a un Receivable.

        Conserva il segno della BT: per entrate è positivo (soldi non
        ancora abbinati a un addebito), per uscite è negativo (uscita non
        ancora abbinata a un Receivable di restituzione). Zero = riconciliato
        pieno.
        """
        if self.importo == 0:
            return Decimal("0")
        return self.importo - self.importo_allocato

    @property
    def stato_riconciliazione(self) -> str:
        """Tre livelli: ``"pieno"``, ``"parziale"``, ``"vuoto"``.

        - **pieno**: tutto l'importo della BT è coperto da allocations
          (entrate o uscite, segno-aware).
        - **parziale**: almeno un'allocation, ma con residuo non nullo.
        - **vuoto**: nessuna allocation.
        """
        if self.importo == 0:
            return "pieno"
        allocato = self.importo_allocato
        if allocato == 0:
            return "vuoto"
        if self.importo > 0:
            return "pieno" if allocato >= self.importo else "parziale"
        return "pieno" if allocato <= self.importo else "parziale"
