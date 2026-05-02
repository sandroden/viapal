"""
Modelli per fornitori, categorie di spesa e spese dell'immobile.
"""
from django.db import models

from properties.models import Contract, OwnerProfile, TimestampedModel


class Supplier(TimestampedModel):
    """Fornitore di servizi (luce, gas, acqua, condominio, ecc.)."""

    class TipoFornitore(models.TextChoices):
        ENERGIA = "energia", "Energia elettrica"
        GAS = "gas", "Gas"
        ACQUA = "acqua", "Acqua"
        CONDOMINIO = "condominio", "Condominio"
        ALTRO = "altro", "Altro"

    nome = models.CharField(
        max_length=200,
        verbose_name="nome",
    )
    tipo = models.CharField(
        max_length=20,
        choices=TipoFornitore.choices,
        default=TipoFornitore.ALTRO,
        verbose_name="tipo",
    )
    partita_iva = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="partita IVA",
    )
    contatto = models.TextField(
        blank=True,
        verbose_name="contatto",
    )

    class Meta:
        verbose_name = "fornitore"
        verbose_name_plural = "fornitori"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"


class ExpenseCategory(TimestampedModel):
    """Categoria di spesa per l'immobile."""

    nome = models.CharField(
        max_length=100,
        verbose_name="nome",
    )
    codice = models.SlugField(
        unique=True,
        verbose_name="codice",
    )
    ripartibile_inquilini = models.BooleanField(
        default=False,
        verbose_name="ripartibile tra inquilini",
    )

    class Meta:
        verbose_name = "categoria spesa"
        verbose_name_plural = "categorie spese"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Expense(TimestampedModel):
    """Spesa relativa all'immobile (IMU, manutenzione, assicurazione, ecc.)."""

    data = models.DateField(
        verbose_name="data",
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name="expenses",
        verbose_name="categoria",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="expenses",
        null=True,
        blank=True,
        verbose_name="fornitore",
    )
    importo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="importo",
    )
    descrizione = models.CharField(
        max_length=300,
        verbose_name="descrizione",
    )
    anticipata_da_owner = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="spese_anticipate",
        verbose_name="anticipata da proprietario",
    )
    ripartibile_su_inquilini = models.BooleanField(
        default=False,
        verbose_name="ripartibile su inquilini",
    )
    riferimento_quota_owner = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="spese_per_quota",
        null=True,
        blank=True,
        verbose_name="riferimento quota proprietario",
        help_text="Es. Bruna paga IMU di Fabio: questo campo vale Fabio.",
    )
    allegato = models.FileField(
        upload_to="spese/",
        null=True,
        blank=True,
        verbose_name="allegato",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "spesa"
        verbose_name_plural = "spese"
        ordering = ["-data"]

    def __str__(self):
        return f"{self.data} — {self.descrizione} ({self.importo}€)"


class TenantCondominioRate(TimestampedModel):
    """
    Quota mensile delle spese condominiali a carico degli inquilini, definita
    dal contratto e aggiornata dopo ogni consuntivo dell'amministratore.

    Storicizzato per contratto: ogni record vale dalla data valid_from fino
    a valid_to (incluso), o indefinitamente se valid_to nullo.
    """

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="quote_condominio_inquilini",
        verbose_name="contratto",
    )
    valid_from = models.DateField(verbose_name="valido dal")
    valid_to = models.DateField(
        null=True,
        blank=True,
        verbose_name="valido fino al",
        help_text="Lasciare vuoto se la quota e' tuttora in vigore.",
    )
    importo_mensile = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="importo mensile (€)",
    )
    note = models.TextField(blank=True, verbose_name="note")

    class Meta:
        verbose_name = "quota condominiale inquilini"
        verbose_name_plural = "quote condominiali inquilini"
        ordering = ["-valid_from"]

    def __str__(self):
        return f"{self.importo_mensile}€/mese dal {self.valid_from}"
