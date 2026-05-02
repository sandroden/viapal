"""
Modelli per pagamenti affitti, transazioni bancarie e addebiti extra.
"""
from django.db import models

from properties.models import OwnerBankAccount, OwnerProfile, RoomAssignment, TimestampedModel


class StatoPagamento(models.TextChoices):
    ATTESO = "atteso", "Atteso"
    DICHIARATO = "dichiarato", "Dichiarato (da confermare)"
    PAGATO = "pagato", "Pagato"
    IN_RITARDO = "in_ritardo", "In ritardo"
    INSOLUTO = "insoluto", "Insoluto"


class RentPayment(TimestampedModel):
    """Rata di affitto mensile per un'assegnazione stanza."""

    assignment = models.ForeignKey(
        RoomAssignment,
        on_delete=models.PROTECT,
        related_name="rent_payments",
        verbose_name="assegnazione",
    )
    competenza_da = models.DateField(
        verbose_name="competenza dal",
    )
    competenza_a = models.DateField(
        verbose_name="competenza al",
    )
    importo_dovuto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="importo dovuto",
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
    scadenza = models.DateField(
        verbose_name="scadenza",
    )
    stato = models.CharField(
        max_length=20,
        choices=StatoPagamento.choices,
        default=StatoPagamento.ATTESO,
        verbose_name="stato",
    )
    is_aggiustamento = models.BooleanField(
        default=False,
        verbose_name="è aggiustamento",
        help_text="Pagamento pro-rata per ingresso/uscita a metà mese.",
    )
    incassato_da_owner = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="incassi_affitto",
        null=True,
        blank=True,
        verbose_name="incassato da proprietario",
    )
    bank_account_destinazione = models.ForeignKey(
        OwnerBankAccount,
        on_delete=models.PROTECT,
        related_name="rent_payments",
        null=True,
        blank=True,
        verbose_name="conto destinazione",
    )
    ricevuta = models.FileField(
        upload_to="ricevute/affitti/",
        null=True,
        blank=True,
        verbose_name="ricevuta",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "pagamento affitto"
        verbose_name_plural = "pagamenti affitto"
        ordering = ["-scadenza", "assignment__tenant__nominativo"]

    def __str__(self):
        return (
            f"{self.assignment.tenant} — {self.competenza_da.strftime('%Y/%m')} "
            f"({self.get_stato_display()})"
        )


class ExtraCharge(TimestampedModel):
    """Addebito o accredito extra (una-tantum) per un inquilino."""

    assignment = models.ForeignKey(
        RoomAssignment,
        on_delete=models.PROTECT,
        related_name="extra_charges",
        verbose_name="assegnazione",
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
        help_text="Positivo per addebito, negativo per accredito/rimborso.",
    )
    scadenza = models.DateField(
        verbose_name="scadenza",
    )
    stato = models.CharField(
        max_length=20,
        choices=StatoPagamento.choices,
        default=StatoPagamento.ATTESO,
        verbose_name="stato",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "addebito extra"
        verbose_name_plural = "addebiti extra"
        ordering = ["-scadenza"]

    def __str__(self):
        segno = "+" if self.importo >= 0 else ""
        return f"{self.assignment.tenant} — {self.descrizione} ({segno}{self.importo}€)"


class BankTransaction(TimestampedModel):
    """Riga di estratto conto bancario importata."""

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
    riconciliato_con_payment = models.ForeignKey(
        RentPayment,
        on_delete=models.SET_NULL,
        related_name="bank_transactions",
        null=True,
        blank=True,
        verbose_name="riconciliato con pagamento affitto",
    )
    # La FK a UtilityCharge viene aggiunta come stringa per evitare import circolare
    riconciliato_con_charge = models.ForeignKey(
        "billing.UtilityCharge",
        on_delete=models.SET_NULL,
        related_name="bank_transactions",
        null=True,
        blank=True,
        verbose_name="riconciliato con conguaglio",
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
