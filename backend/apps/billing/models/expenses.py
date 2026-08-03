"""
Modelli per fornitori, categorie di spesa e spese dell'immobile.
"""
from django.core.exceptions import ValidationError
from django.db import models

from core.storages import media_private_storage
from properties.models import Contract, OwnerProfile, Property, TimestampedModel


class Supplier(TimestampedModel):
    """Fornitore di servizi (luce, gas, acqua, condominio, ecc.)."""

    class TipoFornitore(models.TextChoices):
        ENERGIA = "energia", "Energia elettrica"
        GAS = "gas", "Gas"
        ACQUA = "acqua", "Acqua"
        CONDOMINIO = "condominio", "Condominio"
        ALTRO = "altro", "Altro"

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="suppliers",
        verbose_name="immobile",
    )
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

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="expense_categories",
        verbose_name="immobile",
    )
    nome = models.CharField(
        max_length=100,
        verbose_name="nome",
    )
    codice = models.SlugField(
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
        constraints = [
            models.UniqueConstraint(
                fields=["property", "codice"],
                name="expense_category_codice_unique_per_property",
            ),
        ]

    def __str__(self):
        return self.nome


class Expense(TimestampedModel):
    """Spesa relativa all'immobile (IMU, manutenzione, assicurazione, ecc.)."""

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="expenses",
        verbose_name="immobile",
    )
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
    is_straordinaria = models.BooleanField(
        default=False,
        verbose_name="straordinaria",
        help_text="Spese straordinarie (es. rifacimento bagno) vengono raggruppate "
                  "separatamente al settlement annuale.",
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
        storage=media_private_storage,
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
    Quota mensile delle spese condominiali a carico degli inquilini, di norma
    fissata dal contratto e aggiornata dopo ogni consuntivo
    dell'amministratore.

    La quota appartiene all'**immobile**: il contratto è solo il documento in
    cui è scritta, e può mancare (immobile appena creato, accordo verbale)
    senza per questo impedire di addebitarla.

    Storicizzata per immobile e, opzionalmente, per inquilino: la riga con
    ``tenant`` vuoto è la quota base dell'immobile, quella con ``tenant``
    valorizzato è un'eccezione per il singolo inquilino (es. tetto ridotto
    per i nuovi ingressi) e prevale sulla base. Ogni record vale dalla data
    valid_from fino a valid_to (incluso), o indefinitamente se valid_to nullo.
    """

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="quote_condominio",
        verbose_name="immobile",
    )
    contract = models.ForeignKey(
        Contract,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quote_condominio_inquilini",
        verbose_name="contratto",
        help_text="Facoltativo: il contratto in cui la quota è pattuita.",
    )
    tenant = models.ForeignKey(
        "properties.TenantProfile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="quote_condominio",
        verbose_name="inquilino",
        help_text=(
            "Vuoto = quota base dell'immobile; valorizzato = eccezione "
            "valida solo per questo inquilino."
        ),
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
        verbose_name = "quota spese condominiali"
        verbose_name_plural = "quote spese condominiali"
        ordering = ["-valid_from"]

    def clean(self):
        super().clean()
        if (
            self.contract_id
            and self.property_id
            and self.contract.property_id != self.property_id
        ):
            raise ValidationError(
                {"contract": "Il contratto è di un altro immobile."}
            )

    def save(self, *args, **kwargs):
        # L'immobile si deduce dal contratto quando non è indicato: tiene in
        # piedi i chiamanti storici, nati quando la quota pendeva dal
        # contratto.
        if self.property_id is None and self.contract_id:
            self.property_id = self.contract.property_id
        super().save(*args, **kwargs)

    def __str__(self):
        base = f"{self.importo_mensile}€/mese dal {self.valid_from}"
        if self.tenant_id:
            return f"{base} ({self.tenant})"
        return base
