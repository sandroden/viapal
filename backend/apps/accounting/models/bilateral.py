"""
Partitario bilaterale tra coppie di proprietari (Livello B).
Gestisce prestiti personali, trattenute e voci bilaterali.
"""
from django.db import models

from properties.models import OwnerProfile, TimestampedModel


class InterOwnerLoan(TimestampedModel):
    """Prestito personale tra due proprietari (es. Sandro a Fabio)."""

    owner_da = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="prestiti_dati",
        verbose_name="proprietario prestante",
    )
    owner_a = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="prestiti_ricevuti",
        verbose_name="proprietario debitore",
    )
    data_apertura = models.DateField(
        verbose_name="data apertura",
    )
    importo_originale = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="importo originale",
    )
    descrizione = models.CharField(
        max_length=300,
        verbose_name="descrizione",
    )
    chiuso = models.BooleanField(
        default=False,
        verbose_name="chiuso",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "prestito tra proprietari"
        verbose_name_plural = "prestiti tra proprietari"
        ordering = ["-data_apertura"]

    def __str__(self):
        stato = "chiuso" if self.chiuso else "aperto"
        return f"{self.owner_da} → {self.owner_a} — {self.importo_originale}€ ({stato})"


class InterOwnerEntry(TimestampedModel):
    """Voce del partitario bilaterale tra due proprietari."""

    owner_da = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="voci_bilaterali_date",
        verbose_name="proprietario pagante",
    )
    owner_a = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="voci_bilaterali_ricevute",
        verbose_name="proprietario beneficiario",
    )
    data = models.DateField(
        verbose_name="data",
    )
    importo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="importo",
        help_text="Positivo = owner_a deve a owner_da. Negativo = contrario.",
    )
    descrizione = models.CharField(
        max_length=300,
        verbose_name="descrizione",
    )
    riferimento_loan = models.ForeignKey(
        InterOwnerLoan,
        on_delete=models.SET_NULL,
        related_name="entries",
        null=True,
        blank=True,
        verbose_name="prestito collegato",
    )
    riferimento_expense = models.ForeignKey(
        "billing.Expense",
        on_delete=models.SET_NULL,
        related_name="inter_owner_entries",
        null=True,
        blank=True,
        verbose_name="spesa collegata",
    )
    bank_transaction = models.ForeignKey(
        "billing.BankTransaction",
        on_delete=models.SET_NULL,
        related_name="inter_owner_entries",
        null=True,
        blank=True,
        verbose_name="transazione bancaria collegata",
    )
    riferimento_settlement = models.ForeignKey(
        "accounting.OwnerSettlement",
        on_delete=models.SET_NULL,
        related_name="inter_owner_entries",
        null=True,
        blank=True,
        verbose_name="settlement di competenza",
        help_text=(
            "Settlement a cui questo movimento bilaterale è logicamente "
            "associato (utile quando la BT è di un anno successivo)."
        ),
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "voce bilaterale tra proprietari"
        verbose_name_plural = "voci bilaterali tra proprietari"
        ordering = ["-data"]

    def __str__(self):
        segno = "+" if self.importo >= 0 else ""
        return f"{self.owner_da} → {self.owner_a} — {segno}{self.importo}€ ({self.data})"


class WithholdingRule(TimestampedModel):
    """Regola di trattenuta automatica su distribuzioni tra proprietari."""

    owner_da = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="trattenute_applicate",
        verbose_name="chi distribuisce (trattiene)",
    )
    owner_a = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="trattenute_subite",
        verbose_name="chi riceve (subisce la trattenuta)",
    )
    importo_mensile = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="importo mensile",
        help_text="Importo trattenuto ogni mese sulla distribuzione.",
    )
    descrizione = models.CharField(
        max_length=300,
        verbose_name="descrizione",
    )
    attiva = models.BooleanField(
        default=True,
        verbose_name="attiva",
    )
    valid_from = models.DateField(
        verbose_name="valida dal",
    )
    valid_to = models.DateField(
        null=True,
        blank=True,
        verbose_name="valida fino al",
    )

    class Meta:
        verbose_name = "regola trattenuta"
        verbose_name_plural = "regole trattenute"
        ordering = ["-valid_from"]

    def __str__(self):
        stato = "attiva" if self.attiva else "inattiva"
        return (
            f"{self.owner_da} trattiene {self.importo_mensile}€/mese da distribuzione a "
            f"{self.owner_a} ({stato})"
        )
