"""
Modelli relativi all'immobile: stanze, contratto, assegnazioni.
"""
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from ._base import TimestampedModel
from .owner import OwnerBankAccount, OwnerProfile
from .tenant import TenantProfile, valida_dimensione_documento

# Alias del built-in: dentro le classi con un campo FK ``property`` il nome
# ``property`` è shadowato, quindi ``@property`` non è utilizzabile lì.
builtin_property = property


def galleria_upload_to(instance, filename):
    """Percorso di upload delle immagini galleria: ``galleria/<slug immobile>/<filename>``.

    Sottocartella dedicata: le foto galleria sono pubbliche, separate dai
    documenti privati sotto ``MEDIA_ROOT``.
    """
    prop = getattr(instance, "property", None)
    slug = (prop.slug if prop and prop.slug else slugify(getattr(prop, "nome", "")) or "immobile")
    return os.path.join("galleria", slug, filename)


class Property(TimestampedModel):
    """Immobile/abitazione che raggruppa le stanze.

    In ottica multi-immobile: ogni stanza appartiene a una Property, che porta
    il conto di domiciliazione su cui confluiscono le utenze dell'abitazione.
    """

    nome = models.CharField(
        max_length=120,
        verbose_name="nome",
    )
    indirizzo = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="indirizzo",
    )
    bank_account_utenze = models.ForeignKey(
        OwnerBankAccount,
        on_delete=models.PROTECT,
        related_name="properties_utenze",
        null=True,
        blank=True,
        verbose_name="conto domiciliazione utenze",
        help_text="Conto su cui gli inquilini versano le utenze/conguagli di questo immobile.",
    )

    # ── Galleria pubblica (annuncio affitto) ─────────────────────────────
    slug = models.SlugField(
        max_length=140,
        unique=True,
        null=True,
        blank=True,
        verbose_name="slug pubblico",
        help_text="Identificativo per l'URL pubblico della galleria (/g/<slug>). "
        "Se vuoto viene generato dal nome.",
    )
    pubblica = models.BooleanField(
        default=False,
        verbose_name="galleria pubblica",
        help_text="Se attiva, la galleria è raggiungibile pubblicamente senza login.",
    )
    foto_hero = models.ImageField(
        upload_to=galleria_upload_to,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), valida_dimensione_documento],
        null=True,
        blank=True,
        verbose_name="foto principale (hero)",
    )
    foto_planimetria = models.ImageField(
        upload_to=galleria_upload_to,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), valida_dimensione_documento],
        null=True,
        blank=True,
        verbose_name="planimetria",
    )
    foto_mappa = models.ImageField(
        upload_to=galleria_upload_to,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), valida_dimensione_documento],
        null=True,
        blank=True,
        verbose_name="screenshot mappa",
    )
    testi_pubblici = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="testi pubblici",
        help_text="Testi liberi editabili della pagina pubblica (hero, facts, posizione). "
        "Le chiavi mancanti usano i fallback del frontend.",
    )

    class Meta:
        verbose_name = "immobile"
        verbose_name_plural = "immobili"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nome) or "immobile"
            slug = base
            n = 2
            while Property.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Room(TimestampedModel):
    """Stanza affittabile dell'appartamento."""

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="rooms",
        null=True,
        blank=True,
        verbose_name="immobile",
    )
    nome = models.CharField(
        max_length=100,
        verbose_name="nome",
    )
    superficie_mq = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="superficie (mq)",
    )
    foto = models.ImageField(
        upload_to="rooms/",
        null=True,
        blank=True,
        verbose_name="foto",
    )
    ordinamento = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="ordinamento",
    )

    # ── Galleria pubblica (annuncio affitto) ─────────────────────────────
    colore = models.CharField(
        max_length=40,
        blank=True,
        verbose_name="colore identificativo",
        help_text="Colore del pallino/legenda in galleria (es. 'var(--vp-terra)' o '#c96f4a').",
    )
    descrizione = models.TextField(
        blank=True,
        verbose_name="descrizione",
        help_text="Descrizione breve della stanza mostrata nell'annuncio.",
    )
    disponibile = models.BooleanField(
        default=True,
        verbose_name="disponibile (annuncio)",
        help_text="Se disattiva: badge 'Non disponibile' e nessuna foto in galleria.",
    )
    libera_dal = models.DateField(
        null=True,
        blank=True,
        verbose_name="libera dal",
        help_text="Data indicativa da cui la stanza è disponibile (facoltativa).",
    )
    prezzo_mensile = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="prezzo mensile (annuncio)",
        help_text="Prezzo d'annuncio, distinto dal canone effettivo delle assegnazioni.",
    )
    pubblica = models.BooleanField(
        default=True,
        verbose_name="mostra in galleria",
    )

    class Meta:
        verbose_name = "stanza"
        verbose_name_plural = "stanze"
        ordering = ["ordinamento", "nome"]

    def __str__(self):
        return self.nome

    @builtin_property
    def si_libera_a_data(self):
        """La stanza è occupata ora ma con una data di rilascio nota (futura o
        odierna). ``libera_dal`` implica di per sé che ora sia occupata."""
        return bool(self.libera_dal and self.libera_dal >= timezone.localdate())

    @builtin_property
    def mostra_foto_pubbliche(self):
        """Le foto della stanza vanno esposte in galleria: quando è disponibile
        oppure quando si libererà a una data nota (annuncio anticipato).
        'Non disponibile' (senza data) nasconde invece l'interno."""
        return self.disponibile or self.si_libera_a_data


class GalleryArea(TimestampedModel):
    """Ambiente comune dell'immobile nella galleria (cucina, soggiorno, bagni…).

    A differenza di ``Room``, NON è un oggetto d'affitto: non ha assegnazioni,
    canone né disponibilità. È solo un raggruppamento di foto della galleria
    pubblica, con la stessa presentazione delle camere ma senza dati di locazione.
    """

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="gallery_areas",
        verbose_name="immobile",
    )
    nome = models.CharField(
        max_length=100,
        verbose_name="nome",
    )
    colore = models.CharField(
        max_length=40,
        blank=True,
        verbose_name="colore identificativo",
    )
    descrizione = models.TextField(
        blank=True,
        verbose_name="descrizione",
    )
    ordinamento = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="ordinamento",
    )
    pubblica = models.BooleanField(
        default=True,
        verbose_name="mostra in galleria",
    )

    class Meta:
        verbose_name = "ambiente comune"
        verbose_name_plural = "ambienti comuni"
        ordering = ["ordinamento", "nome"]

    def __str__(self):
        return self.nome


class GalleryImage(TimestampedModel):
    """Foto della galleria pubblica.

    Legata all'immobile e a UNO fra: una ``room`` (camera, oggetto d'affitto che
    la foto ritrae) oppure una ``area`` (ambiente comune). Hero, planimetria e
    mappa (singleton) stanno invece direttamente su ``Property``.
    """

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="gallery_images",
        verbose_name="immobile",
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="gallery_images",
        null=True,
        blank=True,
        verbose_name="camera",
        help_text="Camera (oggetto d'affitto) ritratta dalla foto.",
    )
    area = models.ForeignKey(
        GalleryArea,
        on_delete=models.CASCADE,
        related_name="gallery_images",
        null=True,
        blank=True,
        verbose_name="ambiente comune",
        help_text="Ambiente comune (cucina, soggiorno, bagni…) ritratto dalla foto.",
    )
    image = models.ImageField(
        upload_to=galleria_upload_to,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "webp"]),
            valida_dimensione_documento,
        ],
        verbose_name="immagine",
    )
    didascalia = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="didascalia",
    )
    ordinamento = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="ordinamento",
    )
    caricato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gallery_images_caricate",
        verbose_name="caricato da",
    )

    class Meta:
        verbose_name = "foto galleria"
        verbose_name_plural = "foto galleria"
        ordering = ["room__ordinamento", "area__ordinamento", "ordinamento", "id"]

    def __str__(self):
        dove = self.room.nome if self.room_id else (self.area.nome if self.area_id else "immobile")
        return f"Foto {self.property} / {dove}"

    def clean(self):
        super().clean()
        if self.room_id and self.area_id:
            raise ValidationError(
                "Una foto può essere legata a una camera oppure a un ambiente comune, non a entrambi."
            )
        if self.room_id and self.property_id and self.room.property_id != self.property_id:
            raise ValidationError({"room": "La camera non appartiene all'immobile indicato."})
        if self.area_id and self.property_id and self.area.property_id != self.property_id:
            raise ValidationError({"area": "L'ambiente non appartiene all'immobile indicato."})


class Contract(TimestampedModel):
    """Il contratto unico di locazione (un solo record attivo)."""

    class RegimeFiscale(models.TextChoices):
        CEDOLARE_10 = "cedolare_10", "Cedolare secca 10%"
        CEDOLARE_21 = "cedolare_21", "Cedolare secca 21%"
        IRPEF = "irpef", "IRPEF ordinario"

    nome = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="nome",
        help_text="Nome identificativo (es. 'Contratto 2023', 'Contratto 2025').",
    )
    data_stipula = models.DateField(
        verbose_name="data stipula",
    )
    data_decorrenza = models.DateField(
        verbose_name="data decorrenza",
    )
    termine = models.DateField(
        null=True,
        blank=True,
        verbose_name="termine",
        help_text=(
            "Data effettiva di chiusura del contratto (uscita anticipata). "
            "Diversa dalla scadenza naturale = data_decorrenza + durata_anni."
        ),
    )
    durata_anni = models.PositiveSmallIntegerField(
        verbose_name="durata (anni)",
    )
    asseverato = models.BooleanField(
        default=False,
        verbose_name="asseverato",
    )
    regime_fiscale = models.CharField(
        max_length=20,
        choices=RegimeFiscale.choices,
        default=RegimeFiscale.CEDOLARE_10,
        verbose_name="regime fiscale",
    )
    default_pagatore_bollette = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="contratti_pagatore_bollette",
        null=True,
        blank=True,
        verbose_name="paga le bollette utenze",
        help_text=(
            "Proprietario che, per convenzione, anticipa il pagamento "
            "delle bollette luce/gas verso i fornitori."
        ),
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "contratto"
        verbose_name_plural = "contratti"
        ordering = ["-data_decorrenza"]

    def __str__(self):
        if self.nome:
            return self.nome
        return f"Contratto dal {self.data_decorrenza} ({self.get_regime_fiscale_display()})"


class RoomAssignment(TimestampedModel):
    """Periodo di occupazione di una stanza da parte di un inquilino."""

    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="assignments",
        verbose_name="stanza",
    )
    tenant = models.ForeignKey(
        TenantProfile,
        on_delete=models.PROTECT,
        related_name="assignments",
        verbose_name="inquilino",
    )
    valid_from = models.DateField(
        verbose_name="inizio occupazione",
    )
    valid_to = models.DateField(
        null=True,
        blank=True,
        verbose_name="fine occupazione",
    )
    canone_mensile = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="canone mensile",
    )
    bank_account_affitto = models.ForeignKey(
        OwnerBankAccount,
        on_delete=models.PROTECT,
        related_name="assignments_affitto",
        null=True,
        blank=True,
        verbose_name="conto incasso affitto",
        help_text=(
            "Override: conto su cui versare l'affitto di questa assegnazione. "
            "Se vuoto, si usa il conto della proprietà."
        ),
    )
    costo_cessione = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="costo cessione (totale)",
        help_text=(
            "Costo TOTALE della registrazione/cessione del contratto. Se "
            "valorizzato, alla data di inizio occupazione genera: il 50% come "
            "addebito all'inquilino entrante (Receivable 'registrazione') e il "
            "50% come spesa proprietari ripartita pro-quota. Lasciare vuoto "
            "per il contratto collettivo (nessun addebito)."
        ),
    )
    data_atto_cessione = models.DateField(
        null=True,
        blank=True,
        verbose_name="data atto cessione",
        help_text="Valorizzato se l'occupazione è iniziata con una cessione registrata.",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "assegnazione stanza"
        verbose_name_plural = "assegnazioni stanze"
        ordering = ["-valid_from", "room__nome"]
        constraints = [
            # Non è possibile avere two assignments sovrapposti per la stessa stanza.
            # Il vincolo viene anche verificato in clean() per messaggi d'errore chiari.
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=models.F("valid_from")),
                name="room_assignment_valid_to_after_valid_from",
            )
        ]

    def __str__(self):
        to = f" → {self.valid_to}" if self.valid_to else " → in corso"
        return f"{self.room} / {self.tenant} ({self.valid_from}{to})"

    def clean(self):
        super().clean()
        if self.valid_to and self.valid_to <= self.valid_from:
            raise ValidationError(
                {"valid_to": "La data di fine occupazione deve essere successiva alla data di inizio."}
            )
        self._valida_no_overlap()

    def _valida_no_overlap(self):
        """Verifica che non ci siano assegnazioni sovrapposte per la stessa stanza."""
        if not self.room_id or not self.valid_from:
            return

        qs = RoomAssignment.objects.filter(room=self.room_id).exclude(pk=self.pk)

        # Un'assegnazione esistente si sovrappone se:
        # inizia prima della fine di questa E finisce dopo l'inizio di questa
        for assignment in qs:
            a_from = assignment.valid_from
            a_to = assignment.valid_to  # None = ancora aperta

            # questa inizia prima della fine dell'esistente?
            this_to = self.valid_to

            # overlap: not (this_to <= a_from or a_to <= this_from)
            # ovvero: this_from < a_to AND a_from < this_to
            # con None = infinito
            this_ends_after_a_starts = True  # this_from < a_to (a_to None = inf)
            if a_to is not None and self.valid_from >= a_to:
                this_ends_after_a_starts = False

            a_starts_before_this_ends = True  # a_from < this_to (this_to None = inf)
            if this_to is not None and a_from >= this_to:
                a_starts_before_this_ends = False

            if this_ends_after_a_starts and a_starts_before_this_ends:
                raise ValidationError(
                    f"Sovrapposizione con l'assegnazione esistente: {assignment} "
                    f"(dal {a_from} al {a_to or 'in corso'})."
                )
