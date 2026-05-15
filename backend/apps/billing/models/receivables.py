"""
Modello unificato addebiti-inquilino (Receivable) e tabella di allocazione M:N
con BankTransaction.

Sostituisce RentPayment, UtilityCharge ed ExtraCharge — accorpando lo stesso
"piano del dovuto" sotto un unico modello con campo `causale`.
"""
from django.db import models

from properties.models import OwnerBankAccount, OwnerProfile, RoomAssignment, TimestampedModel

from .payments import StatoPagamento


class Receivable(TimestampedModel):
    """Importo dovuto da un inquilino — affitto, utenze o addebito extra."""

    class Causale(models.TextChoices):
        AFFITTO = "affitto", "Affitto"
        UTENZE = "utenze", "Utenze"
        EXTRA = "extra", "Extra"
        CAPARRA = "caparra", "Caparra"
        REGISTRAZIONE = "registrazione", "Registrazione contratto"

    assignment = models.ForeignKey(
        RoomAssignment,
        on_delete=models.PROTECT,
        related_name="receivables",
        verbose_name="assegnazione",
    )
    causale = models.CharField(
        max_length=15,
        choices=Causale.choices,
        verbose_name="causale",
    )
    descrizione = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="descrizione",
        help_text="Valorizzata per causale=extra; opzionale altrove.",
    )

    competenza_da = models.DateField(
        verbose_name="competenza dal",
    )
    competenza_a = models.DateField(
        null=True,
        blank=True,
        verbose_name="competenza al",
        help_text="Nullo per causale=extra (addebito puntuale).",
    )
    scadenza = models.DateField(
        verbose_name="scadenza",
    )

    importo_dovuto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="importo dovuto",
        help_text="Per causale=extra può essere negativo (rimborso/accredito).",
    )
    stato = models.CharField(
        max_length=20,
        choices=StatoPagamento.choices,
        default=StatoPagamento.ATTESO,
        verbose_name="stato",
    )
    importo_pagato = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="importo pagato",
    )
    data_pagamento = models.DateField(
        null=True,
        blank=True,
        verbose_name="data pagamento",
    )

    incassato_da_owner = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="incassi",
        null=True,
        blank=True,
        verbose_name="incassato da proprietario",
    )
    bank_account_destinazione = models.ForeignKey(
        OwnerBankAccount,
        on_delete=models.PROTECT,
        related_name="receivables",
        null=True,
        blank=True,
        verbose_name="conto destinazione",
    )
    ricevuta = models.FileField(
        upload_to="ricevute/",
        null=True,
        blank=True,
        verbose_name="ricevuta",
    )

    is_aggiustamento = models.BooleanField(
        default=False,
        verbose_name="è aggiustamento",
        help_text="Pro-rata di ingresso/uscita (rilevante per causale=affitto).",
    )
    utility_period = models.ForeignKey(
        "billing.UtilityChargePeriod",
        on_delete=models.PROTECT,
        related_name="receivables",
        null=True,
        blank=True,
        verbose_name="periodo utenze",
        help_text="Valorizzato per causale=utenze.",
    )
    giorni_presenza = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="giorni di presenza",
        help_text="Numeratore della ripartizione utenze (giorni nel periodo).",
    )

    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "addebito inquilino"
        verbose_name_plural = "addebiti inquilini"
        ordering = ["-scadenza", "assignment__tenant__nominativo"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "competenza_da", "competenza_a"],
                condition=models.Q(causale="affitto"),
                name="receivable_affitto_unique",
            ),
            models.UniqueConstraint(
                fields=["utility_period", "assignment"],
                condition=models.Q(causale="utenze"),
                name="receivable_utenze_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["causale", "stato"]),
            models.Index(fields=["assignment", "causale"]),
        ]

    _MESI_ABBR = (
        "", "Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
        "Lug", "Ago", "Set", "Ott", "Nov", "Dic",
    )

    def __str__(self):
        if self.descrizione:
            etichetta = self.descrizione
        else:
            etichetta = self.get_causale_display()
            # Per affitto/utenze, aggiungi il periodo di competenza
            if self.competenza_da:
                m = self._MESI_ABBR[self.competenza_da.month]
                y = self.competenza_da.year
                etichetta = f"{etichetta} {m} {y}"
        return (
            f"{self.assignment.tenant} — {etichetta} "
            f"({self.importo_dovuto}€) [{self.stato}]"
        )


class BankTransactionAllocation(TimestampedModel):
    """Allocazione M:N tra una BankTransaction e i Receivable che essa copre.

    Permette di associare un singolo bonifico a più addebiti (es. affitto +
    utenze pagati con un unico versamento) e viceversa un addebito coperto
    da più movimenti (acconto + saldo).
    """

    bank_transaction = models.ForeignKey(
        "billing.BankTransaction",
        on_delete=models.CASCADE,
        related_name="allocations",
        verbose_name="transazione",
    )
    receivable = models.ForeignKey(
        Receivable,
        on_delete=models.PROTECT,
        related_name="allocations",
        verbose_name="addebito",
    )
    importo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="importo allocato",
        help_text="Quota della transazione imputata a questo addebito.",
    )

    class Meta:
        verbose_name = "allocazione transazione"
        verbose_name_plural = "allocazioni transazioni"
        constraints = [
            models.UniqueConstraint(
                fields=["bank_transaction", "receivable"],
                name="allocation_unique_pair",
            ),
        ]

    def __str__(self):
        return f"{self.bank_transaction} → {self.receivable} ({self.importo}€)"
