"""
Modelli relativi all'immobile: stanze, contratto, assegnazioni.
"""
import builtins
import datetime
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.text import slugify

from core.storages import media_private_storage

from ._base import TimestampedModel
from .owner import OwnerBankAccount, OwnerProfile
from .tenant import TenantProfile, valida_dimensione_documento


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

    ``tipo_gestione`` distingue l'affitto a stanze (più inquilini, una Room
    ciascuno) dall'affitto a unità intera (un solo pagatore per l'intero
    appartamento). In entrambi i casi la catena Room → RoomAssignment →
    Receivable resta invariata: per le unità intere esiste una sola Room
    implicita (vedi ``properties/signals.py``).
    """

    class TipoGestione(models.TextChoices):
        STANZE = "stanze", "A stanze"
        UNITA_INTERA = "unita_intera", "Unità intera"

    nome = models.CharField(
        max_length=120,
        verbose_name="nome",
    )
    tipo_gestione = models.CharField(
        max_length=20,
        choices=TipoGestione.choices,
        default=TipoGestione.STANZE,
        verbose_name="tipo di gestione",
    )
    indirizzo = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="indirizzo",
        help_text="Testo libero mostrato nelle email e nella galleria pubblica.",
    )
    # ── Indirizzo strutturato ────────────────────────────────────────────
    # La comunicazione di cessione di fabbricato (art. 12 D.L. 59/1978) ha
    # una casella per ciascuno di questi dati: `indirizzo` resta la stringa
    # di visualizzazione e non viene derivato da qui (né viceversa).
    via = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="via/piazza",
    )
    civico = models.CharField(
        max_length=16,
        blank=True,
        verbose_name="numero civico",
    )
    cap = models.CharField(
        max_length=8,
        blank=True,
        verbose_name="CAP",
    )
    comune = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="comune",
    )
    provincia = models.CharField(
        max_length=4,
        blank=True,
        verbose_name="provincia",
    )
    piano = models.CharField(
        max_length=16,
        blank=True,
        verbose_name="piano",
    )
    scala = models.CharField(
        max_length=16,
        blank=True,
        verbose_name="scala",
    )
    interno = models.CharField(
        max_length=16,
        blank=True,
        verbose_name="interno",
    )
    vani = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="vani",
    )
    accessori = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="accessori",
    )
    ingressi = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="ingressi",
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
    owner_anticipa_cessioni = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="properties_anticipo_cessioni",
        null=True,
        blank=True,
        verbose_name="anticipa i costi di cessione",
        help_text=(
            "Proprietario che, per convenzione, anticipa il 50% dei costi "
            "di registrazione/cessione contratto di questo immobile."
        ),
    )
    owner_firmatario = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="properties_firmatario",
        null=True,
        blank=True,
        verbose_name="firma come cedente",
        help_text=(
            "Proprietario che firma la comunicazione di cessione di "
            "fabbricato: il modulo prevede un dichiarante solo. Cosa "
            "diversa da chi anticipa i costi di cessione."
        ),
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

    def clean(self):
        super().clean()
        if (
            self.pk
            and self.tipo_gestione == self.TipoGestione.UNITA_INTERA
            and self.rooms.count() > 1
        ):
            raise ValidationError(
                {
                    "tipo_gestione": (
                        "Impossibile passare a unità intera: l'immobile ha già più "
                        "di una stanza. Ridurre a una sola stanza prima del cambio."
                    )
                }
            )

    def contratto_attivo(self, alla_data=None):
        """Contratto dell'immobile in vigore a ``alla_data`` (default oggi):
        quello con ``data_decorrenza`` più recente non successiva alla data.
        ``None`` se nessun contratto dell'immobile è ancora iniziato a
        quella data.
        """
        if alla_data is None:
            alla_data = datetime.date.today()
        return (
            self.contracts.filter(data_decorrenza__lte=alla_data)
            .select_related("default_pagatore_bollette")
            .order_by("-data_decorrenza")
            .first()
        )

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

    def clean(self):
        super().clean()
        if (
            self.property_id
            and self.property.tipo_gestione == Property.TipoGestione.UNITA_INTERA
            and Room.objects.filter(property_id=self.property_id).exclude(pk=self.pk).exists()
        ):
            raise ValidationError(
                "Un immobile a unità intera può avere una sola stanza (l'appartamento)."
            )


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

    class Formato(models.TextChoices):
        QUADRATO = "quadrato", "Quadrato"
        ORIZZONTALE = "orizzontale", "Orizzontale"
        VERTICALE = "verticale", "Verticale"

    formato = models.CharField(
        max_length=12,
        choices=Formato.choices,
        default=Formato.QUADRATO,
        verbose_name="formato riquadro",
        help_text="Forma del riquadro in galleria: quadrato, orizzontale o verticale.",
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
    """Contratto di locazione di un immobile.

    Storicamente "il contratto unico": oggi ogni immobile ha i propri
    contratti (di norma uno attivo per volta).
    """

    class RegimeFiscale(models.TextChoices):
        CEDOLARE_10 = "cedolare_10", "Cedolare secca 10%"
        CEDOLARE_21 = "cedolare_21", "Cedolare secca 21%"
        IRPEF = "irpef", "IRPEF ordinario"

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="contracts",
        verbose_name="immobile",
    )
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
    durata_rinnovo_anni = models.PositiveSmallIntegerField(
        default=2,
        verbose_name="rinnovo (anni)",
        help_text="Il '+2' della formula 4+2: 0 se il contratto non si rinnova.",
    )
    # ── Registrazione presso l'Agenzia delle Entrate ──────────────────────
    # Estremi citati nelle premesse dell'atto di subentro. Finora esistevano
    # solo dentro il PDF della ricevuta caricata (PropertyDocument tipo
    # 'registrazione_contratto'), quindi non erano riutilizzabili.
    ufficio_registrazione = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="ufficio territoriale di registrazione",
        help_text="Ufficio dell'Agenzia delle Entrate (es. Desio).",
    )
    data_registrazione = models.DateField(
        null=True,
        blank=True,
        verbose_name="data di registrazione",
    )
    numero_registrazione = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="numero di registrazione",
    )
    serie_registrazione = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="serie",
        help_text="Es. 3T.",
    )
    codice_identificativo = models.CharField(
        max_length=40,
        blank=True,
        verbose_name="codice identificativo del contratto",
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
    contract = models.ForeignKey(
        "properties.Contract",
        on_delete=models.SET_NULL,
        related_name="assignments",
        null=True,
        blank=True,
        verbose_name="contratto",
        help_text=(
            "Facoltativo: il contratto di locazione sotto cui sta questa "
            "occupazione. Serve a dire quali carte del contratto competono "
            "all'inquilino: senza contratto indicato, l'inquilino non vede i "
            "documenti collegati a un contratto."
        ),
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
    subentra_a = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="subentri",
        null=True,
        blank=True,
        verbose_name="subentra a",
        help_text=(
            "Assegnazione dell'inquilino uscente a cui questa subentra. "
            "Non si deduce dalle date: fra l'uscita di uno e l'ingresso "
            "dell'altro può passare del tempo, e un atto legale non si "
            "fonda su un'euristica."
        ),
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
        self._valida_stessa_property()
        self._valida_no_overlap()
        self._valida_subentro()
        self._valida_contratto()

    def _valida_contratto(self):
        """Il contratto, se indicato, è dell'immobile della stanza."""
        if not self.contract_id or not self.room_id:
            return
        if self.contract.property_id != self.room.property_id:
            raise ValidationError(
                {"contract": "Il contratto è di un altro immobile."}
            )

    def _valida_subentro(self):
        """L'assegnazione a cui si subentra deve essere un'altra, dello
        stesso immobile, e precedente."""
        if not self.subentra_a_id:
            return
        if self.subentra_a_id == self.pk:
            raise ValidationError(
                {"subentra_a": "Un'assegnazione non può subentrare a se stessa."}
            )
        precedente = self.subentra_a
        if (
            self.room_id
            and precedente.room_id
            and self.room.property_id != precedente.room.property_id
        ):
            raise ValidationError(
                {"subentra_a": "L'assegnazione precedente è di un altro immobile."}
            )
        if self.valid_from and precedente.valid_from >= self.valid_from:
            raise ValidationError(
                {"subentra_a": "L'assegnazione precedente deve iniziare prima di questa."}
            )

    def _valida_stessa_property(self):
        """La stanza e l'inquilino devono appartenere allo stesso immobile."""
        if not self.room_id or not self.tenant_id:
            return
        room_property_id = self.room.property_id
        tenant_property_id = self.tenant.property_id
        if (
            room_property_id
            and tenant_property_id
            and room_property_id != tenant_property_id
        ):
            raise ValidationError(
                "La stanza e l'inquilino appartengono a immobili diversi."
            )

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


def property_document_upload_to(instance, filename):
    """Percorso di upload: ``documenti-proprieta/<slug immobile>/<filename>``."""
    prop = instance.property
    slug = (prop.slug if prop and prop.slug else slugify(getattr(prop, "nome", ""))) or "immobile"
    return os.path.join("documenti-proprieta", slug, filename)


class PropertyDocument(TimestampedModel):
    """Documento dell'immobile (contratto, side letter, regolamento, ecc.).

    Come per i documenti inquilino, un record corrisponde a un singolo file:
    più allegati dello stesso ``tipo`` si distinguono con ``descrizione``.
    """

    class Tipo(models.TextChoices):
        CONTRATTO = "contratto", "Contratto di locazione"
        SIDE_LETTER = "side_letter", "Side letter"
        REGISTRAZIONE_CONTRATTO = "registrazione_contratto", "Registrazione contratto"
        REGOLAMENTO_CONDOMINIALE = "regolamento_condominiale", "Regolamento condominiale"
        REGOLE_CONVIVENZA = "regole_convivenza", "Regole di convivenza"
        FAC_SIMILE = "fac_simile", "Fac-simile"
        ALTRO = "altro", "Altro"

    #: Tipi che *sono* la carta di un contratto: senza il contratto sono un
    #: dato malformato, non una scelta. Una side letter senza ``contract``
    #: finisce fra i documenti generali della casa e la vedono gli inquilini
    #: di tutti i contratti — l'opposto di cosa è una side letter.
    #: Gli altri tipi (regolamento, regole di convivenza) valgono per la casa
    #: e il collegamento resta facoltativo.
    TIPI_CONTRATTUALI = frozenset(
        {Tipo.CONTRATTO, Tipo.SIDE_LETTER, Tipo.REGISTRAZIONE_CONTRATTO}
    )

    #: Documento generato apposta per essere letto da fuori: non nomina
    #: nessuno, quindi non ha bisogno di essere oscurato. Sta accanto alle
    #: copie oscurate e non fra le carte della casa.
    TIPI_ESPONIBILI_PER_NATURA = frozenset({Tipo.FAC_SIMILE})

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="documenti",
        verbose_name="immobile",
    )
    contract = models.ForeignKey(
        "properties.Contract",
        on_delete=models.SET_NULL,
        related_name="documenti",
        null=True,
        blank=True,
        verbose_name="contratto",
        help_text=(
            "Facoltativo: il contratto a cui il documento appartiene "
            "(firmato, side letter, ricevuta di registrazione). Se "
            "valorizzato e il documento è visibile agli inquilini, lo vedono "
            "solo quelli la cui occupazione sta sotto questo contratto."
        ),
    )
    tipo = models.CharField(
        max_length=30,
        choices=Tipo.choices,
        default=Tipo.ALTRO,
        verbose_name="tipo documento",
    )
    file = models.FileField(
        upload_to=property_document_upload_to,
        storage=media_private_storage,
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
        help_text="Facoltativa: dettaglio del documento (es. anno, versione).",
    )
    data_scadenza = models.DateField(
        null=True,
        blank=True,
        verbose_name="data di scadenza",
        help_text="Facoltativa: es. scadenza registrazione da rinnovare.",
    )
    visibile_inquilini = models.BooleanField(
        default=False,
        verbose_name="visibile agli inquilini",
        help_text=(
            "Se attivo, gli inquilini dell'immobile vedono e scaricano il "
            "documento nella loro area (es. contratto, regolamento condominiale)."
        ),
    )
    copia_di = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="copie_lettura",
        verbose_name="copia oscurata di",
        help_text=(
            "Versione priva dei dati personali di terzi, da mandare a chi "
            "deve ancora firmare. Non compare fra i documenti ufficiali."
        ),
    )
    esponibile = models.BooleanField(
        default=False,
        verbose_name="esponibile in un link di lettura",
        help_text=(
            "Se attivo, il documento può essere messo in un link di lettura "
            "mandato a chi non ha un account. Una copia oscurata nasce già "
            "spuntata; toglierla svuota i link già mandati."
        ),
    )
    caricato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documenti_proprieta_caricati",
        verbose_name="caricato da",
    )

    class Meta:
        verbose_name = "documento immobile"
        verbose_name_plural = "documenti immobile"
        ordering = ["property__nome", "tipo", "-created_at"]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.property.nome}"

    @classmethod
    def valida_ambito(cls, tipo, contract_id):
        """Messaggio d'errore se il tipo vuole un contratto e non ce l'ha.

        Condivisa fra ``clean()`` (admin) e il serializer DRF: la regola sta
        scritta in un posto solo.
        """
        if tipo in cls.TIPI_CONTRATTUALI and not contract_id:
            etichetta = cls.Tipo(tipo).label
            return (
                f"«{etichetta}» è la carta di un contratto: indica quale. "
                "Senza contratto finirebbe fra i documenti generali della "
                "casa, visibile agli inquilini di ogni contratto."
            )
        return None

    @classmethod
    def valida_copia(cls, originale, property_id, pk=None):
        """Messaggio d'errore se ``copia_di`` non è un originale valido.

        Un livello solo: la copia oscurata è copia di un documento
        ufficiale, mai di un'altra copia. Come ``valida_ambito``, sta qui
        perché la usano sia ``clean()`` (admin) sia il serializer DRF.
        """
        if originale is None:
            return None
        if pk is not None and originale.pk == pk:
            return "Un documento non può essere copia di sé stesso."
        if property_id and originale.property_id != property_id:
            return "L'originale è di un altro immobile."
        if originale.copia_di_id:
            return (
                "Quel documento è già una copia oscurata: si oscura "
                "l'originale."
            )
        return None

    def clean(self):
        super().clean()
        if self.contract_id and self.property_id:
            if self.contract.property_id != self.property_id:
                raise ValidationError(
                    {"contract": "Il contratto è di un altro immobile."}
                )
        errore = self.valida_ambito(self.tipo, self.contract_id)
        if errore:
            raise ValidationError({"contract": errore})
        errore = self.valida_copia(
            self.copia_di if self.copia_di_id else None, self.property_id, self.pk
        )
        if errore:
            raise ValidationError({"copia_di": errore})

    # builtins.property: il campo `property` oscura il builtin nel corpo classe
    @builtins.property
    def scaduto(self):
        """True se il documento ha una scadenza già passata."""
        if not self.data_scadenza:
            return False
        return self.data_scadenza < datetime.date.today()

    @builtins.property
    def titolo(self):
        """Come si chiama il documento quando lo si mostra da solo."""
        return self.descrizione or self.get_tipo_display()
