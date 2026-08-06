"""
Modelli per bollette, TARI, periodi e addebiti utenze inquilini.
"""
import builtins
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from core.storages import media_private_storage
from properties.models import OwnerProfile, Property, TimestampedModel

from .expenses import Expense, Supplier


def utility_bill_upload_to(instance: "UtilityBill", filename: str) -> str:
    """Percorso del PDF: bollette/<immobile>/<anno>/<mese>/<filename>.

    Organizzato per immobile e periodo di competenza (periodo_a), in ottica
    multi-immobile. Tollera property/periodo non valorizzati (fallback parziale)."""
    parti = ["bollette"]
    if instance.immobile_id:
        parti.append(slugify(instance.immobile.nome) or "immobile")
    if instance.periodo_a:
        parti.append(str(instance.periodo_a.year))
        parti.append(f"{instance.periodo_a.month:02d}")
    parti.append(filename)
    return "/".join(parti)


class UtilityBill(TimestampedModel):
    """Bolletta di un fornitore (luce, gas, acqua)."""

    class Prodotto(models.TextChoices):
        LUCE = "luce", "Luce (kWh)"
        GAS = "gas", "Gas (m³)"
        ACQUA = "acqua", "Acqua (m³)"

    UNITA_MISURA = {
        Prodotto.LUCE: "kWh",
        Prodotto.GAS: "m³",
        Prodotto.ACQUA: "m³",
    }

    immobile = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="utility_bills",
        verbose_name="immobile",
        help_text="Immobile a cui appartiene la bolletta.",
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="utility_bills",
        verbose_name="fornitore",
    )
    prodotto = models.CharField(
        max_length=10,
        choices=Prodotto.choices,
        default=Prodotto.LUCE,
        verbose_name="prodotto",
    )
    numero_fattura = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="numero fattura",
    )
    data_emissione = models.DateField(
        verbose_name="data emissione",
    )
    periodo_da = models.DateField(
        verbose_name="periodo dal",
    )
    periodo_a = models.DateField(
        verbose_name="periodo al",
    )
    importo_totale = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="importo totale",
    )
    quota_esclusa = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="quota esclusa",
        help_text=(
            "Parte dell'importo NON ripartita sugli inquilini, a carico della "
            "proprietà (es. canone RAI, aumento potenza, allaccio)."
        ),
    )
    motivo_esclusione = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="motivo esclusione",
        help_text="Es. 'Canone RAI', 'Costi di allaccio'.",
    )
    consumo = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="consumo",
        help_text="kWh per la luce, m³ per gas e acqua.",
    )
    file_pdf = models.FileField(
        upload_to=utility_bill_upload_to,
        storage=media_private_storage,
        null=True,
        blank=True,
        verbose_name="file PDF",
    )
    pagata_da_owner = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="bollette_pagate",
        null=True,
        blank=True,
        verbose_name="pagata da proprietario",
    )
    expense = models.OneToOneField(
        Expense,
        on_delete=models.SET_NULL,
        related_name="utility_bill",
        null=True,
        blank=True,
        editable=False,
        verbose_name="spesa collegata",
        help_text="Expense generata automaticamente quando la bolletta ha 'pagata da proprietario' valorizzato.",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "bolletta utenza"
        verbose_name_plural = "bollette utenze"
        ordering = ["-data_emissione"]

    def __str__(self):
        return f"{self.supplier} — {self.periodo_da} / {self.periodo_a} ({self.importo_totale}€)"

    def clean(self):
        super().clean()
        if self.quota_esclusa and self.importo_totale is not None:
            if self.quota_esclusa < 0:
                raise ValidationError(
                    {"quota_esclusa": "La quota esclusa non può essere negativa."}
                )
            if self.quota_esclusa > self.importo_totale:
                raise ValidationError(
                    {"quota_esclusa": "La quota esclusa non può superare l'importo totale."}
                )

    @property
    def importo_ripartibile(self) -> Decimal:
        """Importo da ripartire sugli inquilini: totale meno la quota a carico proprietà."""
        return self.importo_totale - (self.quota_esclusa or Decimal("0"))

    @property
    def unita_misura(self) -> str:
        return self.UNITA_MISURA.get(self.prodotto, "")


class AnnualUtilityCost(TimestampedModel):
    """Costo annuale spalmato (es. TARI) non proveniente da bolletta mensile."""

    class VoceAnnuale(models.TextChoices):
        TARI = "tari", "TARI (tassa rifiuti)"
        ALTRO = "altro", "Altro"

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="annual_utility_costs",
        verbose_name="immobile",
    )
    voce = models.CharField(
        max_length=20,
        choices=VoceAnnuale.choices,
        default=VoceAnnuale.TARI,
        verbose_name="voce",
    )
    anno = models.PositiveSmallIntegerField(
        verbose_name="anno",
    )
    importo_annuale = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="importo annuale",
    )
    valid_from = models.DateField(
        verbose_name="valido dal",
    )
    valid_to = models.DateField(
        null=True,
        blank=True,
        verbose_name="valido fino al",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "costo utenza annuale"
        verbose_name_plural = "costi utenze annuali"
        ordering = ["-anno", "voce"]

    def __str__(self):
        return f"{self.get_voce_display()} {self.anno} — {self.importo_annuale}€"


class PropertyUtilityService(TimestampedModel):
    """Configurazione per immobile: quali utenze esistono e chi le gestisce.

    Una riga per ``(property, voce)``: **l'assenza** della riga significa
    che quella voce non esiste per questa casa (es. un appartamento senza
    TARI a carico proprietà, o una casa a stanze senza acqua separata dal
    contatore condominiale). ``gestione=proprieta`` = la voce concorre alla
    completezza del periodo e (in prospettiva) alla ripartizione;
    ``gestione=inquilino`` = intestata/pagata direttamente dall'inquilino,
    documentata qui ma fuori dal flusso di ripartizione. Nessuna voce è
    obbligatoria: in un appartamento (unità intera) è normale che anche
    luce e gas siano a carico dell'inquilino.
    """

    class Voce(models.TextChoices):
        LUCE = "luce", "Luce"
        GAS = "gas", "Gas"
        ACQUA = "acqua", "Acqua"
        TARI = "tari", "TARI"

    class Gestione(models.TextChoices):
        PROPRIETA = "proprieta", "Gestita dalla proprietà"
        INQUILINO = "inquilino", "A carico dell'inquilino"

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="utility_services",
        verbose_name="immobile",
    )
    voce = models.CharField(
        max_length=20,
        choices=Voce.choices,
        verbose_name="voce",
    )
    gestione = models.CharField(
        max_length=20,
        choices=Gestione.choices,
        default=Gestione.PROPRIETA,
        verbose_name="gestione",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "utenza della casa"
        verbose_name_plural = "utenze della casa"
        ordering = ["property", "voce"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "voce"],
                name="property_utility_service_unique_per_voce",
            ),
        ]

    def __str__(self):
        return f"{self.property} — {self.get_voce_display()} ({self.get_gestione_display()})"


class UtilityChargePeriod(TimestampedModel):
    """Periodo utenze (mensile o bimestrale) di un immobile."""

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="utility_periods",
        verbose_name="immobile",
    )

    class CriterioRipartizione(models.TextChoices):
        A_TESTA = "a_testa", "A testa (uguale per tutti)"
        PER_STANZA = "per_stanza", "Per stanza"
        PRO_RATA_GIORNI = "pro_rata_giorni", "Pro-rata giorni di presenza"

    class StatoPeriodo(models.TextChoices):
        BOZZA = "bozza", "Bozza"
        INVIATO = "inviato", "Inviato"

    periodo_da = models.DateField(
        verbose_name="periodo dal",
    )
    periodo_a = models.DateField(
        verbose_name="periodo al",
    )
    criterio_ripartizione = models.CharField(
        max_length=20,
        choices=CriterioRipartizione.choices,
        default=CriterioRipartizione.PRO_RATA_GIORNI,
        verbose_name="criterio ripartizione",
    )
    stato = models.CharField(
        max_length=20,
        choices=StatoPeriodo.choices,
        default=StatoPeriodo.BOZZA,
        verbose_name="stato",
    )
    tot_luce = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="totale luce",
    )
    tot_gas = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="totale gas",
    )
    tot_tari = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="totale TARI",
    )
    tot_altro = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="totale altro",
    )
    giorni_totali = models.PositiveIntegerField(
        default=0,
        verbose_name="giorni-persona totali",
        help_text="Somma dei giorni di presenza di tutti gli inquilini (denominatore della ripartizione).",
    )
    nota_calcolo = models.TextField(
        blank=True,
        verbose_name="nota calcolo",
    )
    utility_bills = models.ManyToManyField(
        UtilityBill,
        blank=True,
        related_name="periods",
        verbose_name="bollette agganciate",
        help_text="Bollette fornitore che concorrono ai totali luce/gas. Popolato a mano.",
    )
    annual_utility_costs = models.ManyToManyField(
        AnnualUtilityCost,
        blank=True,
        related_name="periods",
        verbose_name="costi annuali agganciati",
        help_text="Costi annuali (TARI) che concorrono al totale TARI. Popolato a mano.",
    )
    data_invio = models.DateField(
        null=True,
        blank=True,
        verbose_name="data invio",
    )
    avvisi_inviati_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="avvisi inviati il",
        help_text="Data/ora dell'ultimo invio reale degli avvisi agli inquilini.",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "periodo utenze"
        verbose_name_plural = "periodi utenze"
        ordering = ["-periodo_da"]

    def __str__(self):
        return f"Utenze {self.periodo_da} / {self.periodo_a} ({self.get_stato_display()})"

    # builtins.property: il campo `property` oscura il builtin nel corpo classe
    @builtins.property
    def totale_periodo(self):
        return self.tot_luce + self.tot_gas + self.tot_tari + self.tot_altro
