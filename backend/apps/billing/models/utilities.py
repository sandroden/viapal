"""
Modelli per bollette, TARI, periodi e addebiti utenze inquilini.
"""
from django.db import models

from properties.models import OwnerProfile, TimestampedModel

from .expenses import Supplier


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
    consumo = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="consumo",
        help_text="kWh per la luce, m³ per gas e acqua.",
    )
    file_pdf = models.FileField(
        upload_to="bollette/",
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

    @property
    def unita_misura(self) -> str:
        return self.UNITA_MISURA.get(self.prodotto, "")


class AnnualUtilityCost(TimestampedModel):
    """Costo annuale spalmato (es. TARI) non proveniente da bolletta mensile."""

    class VoceAnnuale(models.TextChoices):
        TARI = "tari", "TARI (tassa rifiuti)"
        ALTRO = "altro", "Altro"

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


class UtilityChargePeriod(TimestampedModel):
    """Periodo utenze (mensile o bimestrale)."""

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
    manual_totals = models.JSONField(
        null=True,
        blank=True,
        verbose_name="totali manuali",
        help_text="JSON per import storico: {inquilino_id: importo_totale}",
    )
    data_invio = models.DateField(
        null=True,
        blank=True,
        verbose_name="data invio",
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


class UtilityChargeLine(TimestampedModel):
    """Riga di dettaglio di un addebito utenze (luce, gas, TARI, altro)."""

    class VoceConguaglio(models.TextChoices):
        LUCE = "luce", "Luce"
        GAS = "gas", "Gas"
        TARI = "tari", "TARI"
        ALTRO = "altro", "Altro"

    receivable = models.ForeignKey(
        "billing.Receivable",
        on_delete=models.CASCADE,
        related_name="utility_lines",
        verbose_name="addebito",
    )
    voce = models.CharField(
        max_length=20,
        choices=VoceConguaglio.choices,
        verbose_name="voce",
    )
    importo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="importo",
    )
    dettaglio = models.TextField(
        blank=True,
        verbose_name="dettaglio",
        help_text="Testo esplicativo per la PWA inquilino (es. 'quota pro-rata 15 giorni su 30').",
    )

    class Meta:
        verbose_name = "riga utenze"
        verbose_name_plural = "righe utenze"
        ordering = ["voce"]

    def __str__(self):
        return f"{self.receivable} — {self.get_voce_display()} {self.importo}€"
