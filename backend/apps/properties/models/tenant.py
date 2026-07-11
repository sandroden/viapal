"""
Modelli relativi agli inquilini.
"""
import builtins
import os
from decimal import Decimal

from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

from ._base import TimestampedModel


class TenantProfile(TimestampedModel):
    """Profilo anagrafico di un inquilino."""

    class FrequenzaConguagli(models.TextChoices):
        MENSILE = "mensile", "Mensile"
        BIMESTRALE = "bimestrale", "Bimestrale"

    class CicloFatturazione(models.TextChoices):
        SOLARE = "solare", "Mese solare (1-31)"
        INGRESSO = "ingresso", "Dal giorno di ingresso"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tenant_profile",
        verbose_name="utente",
    )
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.PROTECT,
        related_name="tenants",
        verbose_name="immobile",
        help_text=(
            "Immobile in cui l'inquilino affitta: definisce chi può vedere "
            "e gestire questo profilo."
        ),
    )
    nominativo = models.CharField(
        max_length=200,
        verbose_name="nominativo",
    )
    codice_fiscale = models.CharField(
        max_length=16,
        blank=True,
        verbose_name="codice fiscale",
    )
    telefono = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="telefono",
    )
    email_alt = models.EmailField(
        blank=True,
        verbose_name="email alternativa",
    )
    giorno_pagamento_affitto = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        verbose_name="giorno pagamento affitto",
        help_text="Giorno del mese in cui l'inquilino paga (1-28).",
    )
    frequenza_conguagli = models.CharField(
        max_length=20,
        choices=FrequenzaConguagli.choices,
        default=FrequenzaConguagli.MENSILE,
        verbose_name="frequenza conguagli",
    )
    ciclo_fatturazione = models.CharField(
        max_length=20,
        choices=CicloFatturazione.choices,
        default=CicloFatturazione.SOLARE,
        verbose_name="ciclo fatturazione affitto",
        help_text=(
            "Solare: mese di calendario (1-31), con pro-rata su ingresso/uscita "
            "infra-mese. Ingresso: mensilità dal giorno di valid_from al giorno "
            "precedente del mese successivo (es. 9/2-8/3), canone pieno tranne "
            "moncone finale all'uscita."
        ),
    )
    note_pagamento = models.TextField(
        blank=True,
        verbose_name="note pagamento",
    )

    deposito_versato = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="deposito versato",
        help_text="Deposito versato dall'inquilino. Vale per l'intero rapporto, "
        "anche se l'inquilino cambia stanza o contratto.",
    )
    data_versamento_deposito = models.DateField(
        null=True,
        blank=True,
        verbose_name="data versamento deposito",
    )
    deposito_da_restituire = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="deposito da restituire",
        help_text="Importo lordo da rendere all'uscita. Se vuoto si assume "
        "pari al deposito versato; valorizzalo solo se differisce (es. "
        "rimborsi aggiuntivi a favore dell'inquilino).",
    )
    data_restituzione_prevista = models.DateField(
        null=True,
        blank=True,
        verbose_name="data restituzione prevista",
        help_text="Data in cui la restituzione è dovuta. Valorizzandola "
        "viene generato il Receivable DEPOSITO di restituzione (importo "
        "negativo). La restituzione effettiva si deduce dal pagamento di "
        "quel Receivable.",
    )

    class Meta:
        verbose_name = "profilo inquilino"
        verbose_name_plural = "profili inquilini"
        ordering = ["nominativo"]

    def __str__(self):
        return self.nominativo

    # builtins.property: il campo `property` oscura il builtin nel corpo classe
    @builtins.property
    def periodo_occupazione(self):
        """Intervallo coperto dalle assegnazioni stanza dell'inquilino.

        Restituisce la prima data di ingresso e l'ultima data di fine
        occupazione (es. ``01/07/2024 → 31/12/2025``). Se l'ultima
        assegnazione è ancora aperta non viene mostrata alcuna data di
        fine (es. ``01/07/2024 →``). Stringa vuota se non ci sono
        assegnazioni.
        """
        assignments = list(self.assignments.order_by("valid_from"))
        if not assignments:
            return ""
        inizio = assignments[0].valid_from
        if assignments[-1].valid_to is None:
            return f"{inizio:%d/%m/%Y} →"
        fine = max(a.valid_to for a in assignments)
        return f"{inizio:%d/%m/%Y} → {fine:%d/%m/%Y}"


def tenant_document_upload_to(instance, filename):
    """Percorso di upload: ``documenti/<id>-<slug nominativo>/<filename>``."""
    nome = slugify(instance.tenant.nominativo) or "inquilino"
    return os.path.join("documenti", f"{instance.tenant_id}-{nome}", filename)


def valida_dimensione_documento(file):
    """Rifiuta file più grandi di 10 MB."""
    from django.core.exceptions import ValidationError

    limite = 10 * 1024 * 1024
    if file.size and file.size > limite:
        raise ValidationError("Il file non può superare i 10 MB.")


class TenantDocument(TimestampedModel):
    """Documento di un inquilino (carta d'identità, codice fiscale, ecc.).

    Un record corrisponde a un singolo file: per i documenti fronte/retro si
    caricano due record dello stesso ``tipo`` distinguendoli con
    ``descrizione`` (es. "fronte"/"retro").
    """

    class Tipo(models.TextChoices):
        CARTA_IDENTITA = "carta_identita", "Carta d'identità"
        CODICE_FISCALE = "codice_fiscale", "Codice fiscale / Tessera sanitaria"
        PASSAPORTO = "passaporto", "Passaporto"
        PERMESSO_SOGGIORNO = "permesso_soggiorno", "Permesso di soggiorno"
        CONTRATTO_LAVORO = "contratto_lavoro", "Contratto di lavoro"
        ALTRO = "altro", "Altro"

    tenant = models.ForeignKey(
        TenantProfile,
        on_delete=models.CASCADE,
        related_name="documenti",
        verbose_name="inquilino",
    )
    tipo = models.CharField(
        max_length=30,
        choices=Tipo.choices,
        default=Tipo.ALTRO,
        verbose_name="tipo documento",
    )
    file = models.FileField(
        upload_to=tenant_document_upload_to,
        validators=[
            FileExtensionValidator(["pdf", "jpg", "jpeg", "png"]),
            valida_dimensione_documento,
        ],
        verbose_name="file",
        help_text="PDF o immagine (JPG/PNG), massimo 10 MB.",
    )
    descrizione = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="descrizione",
        help_text="Facoltativa: es. 'fronte', 'retro', o dettaglio per 'Altro'.",
    )
    data_scadenza = models.DateField(
        null=True,
        blank=True,
        verbose_name="data di scadenza",
        help_text="Facoltativa: utile per carta d'identità, passaporto, "
        "permesso di soggiorno.",
    )
    caricato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documenti_inquilini_caricati",
        verbose_name="caricato da",
    )

    class Meta:
        verbose_name = "documento inquilino"
        verbose_name_plural = "documenti inquilini"
        ordering = ["tenant__nominativo", "tipo", "-created_at"]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.tenant.nominativo}"

    @property
    def scaduto(self):
        """True se il documento ha una scadenza già passata."""
        if not self.data_scadenza:
            return False
        import datetime

        return self.data_scadenza < datetime.date.today()
