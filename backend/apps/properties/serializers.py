"""
Serializer per l'app properties.
"""
from decimal import Decimal

from django.utils.text import slugify
from rest_framework import serializers

from properties.models import (
    Contract,
    GalleryArea,
    GalleryImage,
    OwnerBankAccount,
    OwnerProfile,
    Property,
    PropertyDocument,
    Room,
    RoomAssignment,
    TenantDocument,
    TenantProfile,
)


# Campi di ``AnagraficaPersonaMixin``, condivisi da inquilini e proprietari.
CAMPI_ANAGRAFICA = [
    "cognome",
    "nome",
    "data_nascita",
    "comune_nascita",
    "provincia_nascita",
    "cittadinanza",
    "residenza_via",
    "residenza_comune",
    "residenza_provincia",
    "residenza_cap",
]

# Indirizzo strutturato dell'immobile: una casella per ciascuno nel modulo
# di cessione di fabbricato. ``indirizzo`` resta a parte, come stringa di
# visualizzazione.
CAMPI_INDIRIZZO_STRUTTURATO = [
    "via",
    "civico",
    "cap",
    "comune",
    "provincia",
    "piano",
    "scala",
    "interno",
    "vani",
    "accessori",
    "ingressi",
]

# Estremi del documento d'identità: solo sull'inquilino (li chiede il modulo
# di cessione di fabbricato per il cessionario).
CAMPI_DOCUMENTO_IDENTITA = [
    "documento_tipo",
    "documento_numero",
    "documento_autorita",
    "documento_data_rilascio",
]


def _username_da_nominativo(nominativo: str) -> str:
    """Genera uno username dallo slug del nominativo (es. "Mario Rossi" →
    "mario-rossi"), con suffisso numerico se già occupato."""
    from django.contrib.auth import get_user_model

    base = slugify(nominativo) or "inquilino"
    User = get_user_model()
    username = base
    n = 2
    while User.objects.filter(username=username).exists():
        username = f"{base}{n}"
        n += 1
    return username


class OwnerProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = OwnerProfile
        fields = [
            "id",
            "username",
            "nominativo",
            "codice_fiscale",
            "telefono",
            "note",
            *CAMPI_ANAGRAFICA,
        ]


class OwnerProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer con cui si aggiorna l'anagrafica di un OwnerProfile dal
    frontend (tab Membri). Esclude ``note`` (campo di lavoro admin) e lo
    user collegato; chi può scrivere lo decide la view."""

    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = OwnerProfile
        fields = [
            "id",
            "username",
            "nominativo",
            "codice_fiscale",
            "telefono",
            *CAMPI_ANAGRAFICA,
        ]


class TenantProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    frequenza_conguagli_display = serializers.CharField(
        source="get_frequenza_conguagli_display", read_only=True
    )
    ciclo_fatturazione_display = serializers.CharField(
        source="get_ciclo_fatturazione_display", read_only=True
    )
    saldo = serializers.SerializerMethodField()
    saldo_totale = serializers.SerializerMethodField()
    ha_assignment = serializers.SerializerMethodField()

    class Meta:
        model = TenantProfile
        fields = [
            "id",
            "username",
            "email",
            "nominativo",
            "ha_assignment",
            "codice_fiscale",
            "telefono",
            "email_alt",
            "giorno_pagamento_affitto",
            "frequenza_conguagli",
            "frequenza_conguagli_display",
            "ciclo_fatturazione",
            "ciclo_fatturazione_display",
            "note_pagamento",
            "deposito_versato",
            "data_versamento_deposito",
            "deposito_da_restituire",
            "data_restituzione_prevista",
            "saldo",
            "saldo_totale",
            *CAMPI_ANAGRAFICA,
            *CAMPI_DOCUMENTO_IDENTITA,
        ]

    def get_saldo(self, obj):
        saldi = self.context.get("saldi_anno")
        if saldi is None:
            return None
        return saldi.get(obj.id, 0.0)

    def get_saldo_totale(self, obj):
        saldi = self.context.get("saldi_totali")
        if saldi is None:
            return None
        return saldi.get(obj.id, 0.0)

    def get_ha_assignment(self, obj) -> bool:
        """True se il tenant ha almeno una assegnazione (passata, presente o
        futura). Nella viewset arriva annotato (Exists, niente N+1); il
        fallback copre gli usi del serializer fuori da quel queryset."""
        annotato = getattr(obj, "ha_assignment", None)
        if annotato is not None:
            return bool(annotato)
        return obj.assignments.exists()


class TenantProfileWriteSerializer(serializers.ModelSerializer):
    """Creazione/aggiornamento di un inquilino lato gestione.

    In creazione genera anche lo ``User`` collegato: username dallo slug del
    nominativo (con suffisso numerico se occupato), password inutilizzabile
    (l'accesso si attiva con l'invito), gruppo 'inquilini'. La ``property``
    è assegnata dal server (immobile attivo) e non è esposta in scrittura.
    """

    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(
        source="user.email", required=False, allow_blank=True,
    )
    property = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TenantProfile
        fields = [
            "id",
            "username",
            "email",
            "property",
            "nominativo",
            "codice_fiscale",
            "telefono",
            "email_alt",
            "giorno_pagamento_affitto",
            "frequenza_conguagli",
            "ciclo_fatturazione",
            "note_pagamento",
            "deposito_versato",
            "data_versamento_deposito",
            "deposito_da_restituire",
            "data_restituzione_prevista",
            *CAMPI_ANAGRAFICA,
            *CAMPI_DOCUMENTO_IDENTITA,
        ]

    def validate_nominativo(self, value):
        """Anti-duplicato: blocca la creazione di un secondo profilo con lo
        stesso nominativo (confronto strip+casefold, non fuzzy) sulla stessa
        property. Caso reale: prima-assegnazione fallita → profilo "fantasma"
        invisibile in lista → ri-creazione → doppione. Sull'update il profilo
        stesso è escluso dal confronto (rinominare sé stessi è consentito)."""
        from properties.context import get_request_property

        normalizzato = (value or "").strip().casefold()
        request = self.context.get("request")
        if not normalizzato or request is None:
            return value

        if self.instance is not None:
            prop = self.instance.property
        else:
            prop = get_request_property(request)

        qs = TenantProfile.objects.filter(property=prop)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        for esistente in qs.only("id", "nominativo"):
            if esistente.nominativo.strip().casefold() != normalizzato:
                continue
            senza = "" if esistente.assignments.exists() else ", senza assegnazione"
            raise serializers.ValidationError(
                f'Esiste già un inquilino "{esistente.nominativo}" su questo '
                f"immobile{senza}: riprendilo dalla lista inquilini invece di "
                "crearne un doppione. Se è davvero una persona diversa, usa "
                "un nome leggermente diverso."
            )
        return value

    def create(self, validated_data):
        from django.conf import settings
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group
        from django.db import transaction

        user_data = validated_data.pop("user", {})
        email = (user_data.get("email") or "").strip()
        User = get_user_model()
        with transaction.atomic():
            user = User.objects.create_user(
                username=_username_da_nominativo(validated_data["nominativo"]),
                email=email,
            )
            user.set_unusable_password()
            user.save()
            gruppo, _ = Group.objects.get_or_create(name=settings.ROLE_INQUILINI)
            user.groups.add(gruppo)
            return TenantProfile.objects.create(user=user, **validated_data)

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        email = user_data.get("email")
        if email is not None and email.strip() != instance.user.email:
            instance.user.email = email.strip()
            instance.user.save(update_fields=["email"])
        return super().update(instance, validated_data)


class TenantSelfUpdateSerializer(serializers.ModelSerializer):
    """Serializer ristretto con cui l'inquilino aggiorna i propri dati.

    Espone in sola lettura username/email e in scrittura solo i campi che
    l'inquilino può modificare da solo. I campi sensibili (deposito, giorno
    pagamento, ciclo, ecc.) restano gestiti dai proprietari via admin.
    """

    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = TenantProfile
        fields = [
            "id",
            "username",
            "email",
            "nominativo",
            "telefono",
            "codice_fiscale",
        ]


class TenantDocumentSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    tenant_nominativo = serializers.CharField(source="tenant.nominativo", read_only=True)
    scaduto = serializers.BooleanField(read_only=True)

    class Meta:
        model = TenantDocument
        fields = [
            "id",
            "tenant",
            "tenant_nominativo",
            "tipo",
            "tipo_display",
            "file",
            "descrizione",
            "data_scadenza",
            "scaduto",
            "created_at",
        ]
        # Il tenant è imposto dalla view (per l'inquilino il proprio, per il
        # proprietario quello indicato): mai derivabile dal client per gli
        # inquilini.
        extra_kwargs = {"tenant": {"required": False}}


class PropertyDocumentSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    scaduto = serializers.BooleanField(read_only=True)
    contract_nome = serializers.SerializerMethodField()

    class Meta:
        model = PropertyDocument
        fields = [
            "id",
            "property",
            "contract",
            "contract_nome",
            "tipo",
            "tipo_display",
            "file",
            "descrizione",
            "data_scadenza",
            "scaduto",
            "visibile_inquilini",
            "created_at",
        ]
        # La property è imposta dalla view (l'immobile attivo della richiesta).
        extra_kwargs = {"property": {"required": False, "read_only": True}}

    def get_contract_nome(self, obj) -> str:
        if not obj.contract_id:
            return ""
        return obj.contract.nome or f"Contratto dal {obj.contract.data_decorrenza}"


class RoomSerializer(serializers.ModelSerializer):
    # La property è assegnata dal server (immobile attivo): mai in scrittura.
    property = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Room
        fields = [
            "id",
            "property",
            "nome",
            "superficie_mq",
            "foto",
            "ordinamento",
            # ── Galleria pubblica ──
            "colore",
            "descrizione",
            "disponibile",
            "libera_dal",
            "prezzo_mensile",
            "pubblica",
        ]


class GalleryAreaSerializer(serializers.ModelSerializer):
    """Ambiente comune (cucina, soggiorno, bagni…) — no dati di locazione."""

    class Meta:
        model = GalleryArea
        fields = [
            "id",
            "property",
            "nome",
            "colore",
            "descrizione",
            "ordinamento",
            "pubblica",
        ]


class GalleryImageSerializer(serializers.ModelSerializer):
    """Foto della galleria. ``property``/``room``/``area`` validati dalla view."""

    class Meta:
        model = GalleryImage
        fields = [
            "id",
            "property",
            "room",
            "area",
            "image",
            "didascalia",
            "formato",
            "ordinamento",
            "created_at",
        ]

    def validate(self, attrs):
        prop = attrs.get("property") or getattr(self.instance, "property", None)
        room = attrs.get("room") if "room" in attrs else getattr(self.instance, "room", None)
        area = attrs.get("area") if "area" in attrs else getattr(self.instance, "area", None)
        if room and area:
            raise serializers.ValidationError(
                "Indica una camera oppure un ambiente comune, non entrambi."
            )
        if room and prop and room.property_id != prop.id:
            raise serializers.ValidationError({"room": "La camera non appartiene all'immobile."})
        if area and prop and area.property_id != prop.id:
            raise serializers.ValidationError({"area": "L'ambiente non appartiene all'immobile."})
        return attrs


class PublicGalleryRoomSerializer(serializers.ModelSerializer):
    """Stanza come esposta nella pagina pubblica (sola lettura, senza dati sensibili)."""

    foto = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            "id",
            "nome",
            "superficie_mq",
            "colore",
            "descrizione",
            "disponibile",
            "libera_dal",
            "prezzo_mensile",
            "ordinamento",
            "foto",
        ]

    def get_foto(self, obj):
        # Le foto restano visibili anche a stanza occupata: il frontend le
        # vela e mostra una nota, così il visitatore capisce com'è la casa.
        request = self.context.get("request")
        return [
            {
                "id": img.id,
                "url": request.build_absolute_uri(img.image.url) if request else img.image.url,
                "didascalia": img.didascalia,
                "formato": img.formato,
            }
            for img in obj.gallery_images.all()
        ]


class PublicGalleryAreaSerializer(serializers.ModelSerializer):
    """Ambiente comune come esposto nella pagina pubblica (sola lettura)."""

    foto = serializers.SerializerMethodField()

    class Meta:
        model = GalleryArea
        fields = ["id", "nome", "colore", "descrizione", "ordinamento", "foto"]

    def get_foto(self, obj):
        request = self.context.get("request")
        return [
            {
                "id": img.id,
                "url": request.build_absolute_uri(img.image.url) if request else img.image.url,
                "didascalia": img.didascalia,
                "formato": img.formato,
            }
            for img in obj.gallery_images.all()
        ]


class PublicGallerySerializer(serializers.ModelSerializer):
    """Payload completo e pubblico della galleria di un immobile."""

    rooms = serializers.SerializerMethodField()
    aree = serializers.SerializerMethodField()
    foto_hero = serializers.SerializerMethodField()
    foto_planimetria = serializers.SerializerMethodField()
    foto_mappa = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            "id",
            "nome",
            "slug",
            "indirizzo",
            "tipo_gestione",
            "testi_pubblici",
            "foto_hero",
            "foto_planimetria",
            "foto_mappa",
            "rooms",
            "aree",
        ]

    def _url(self, filefield):
        if not filefield:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(filefield.url) if request else filefield.url

    def get_foto_hero(self, obj):
        return self._url(obj.foto_hero)

    def get_foto_planimetria(self, obj):
        return self._url(obj.foto_planimetria)

    def get_foto_mappa(self, obj):
        return self._url(obj.foto_mappa)

    def get_rooms(self, obj):
        rooms = obj.rooms.filter(pubblica=True).prefetch_related("gallery_images")
        return PublicGalleryRoomSerializer(rooms, many=True, context=self.context).data

    def get_aree(self, obj):
        aree = obj.gallery_areas.filter(pubblica=True).prefetch_related("gallery_images")
        return PublicGalleryAreaSerializer(aree, many=True, context=self.context).data


class RoomAssignmentSerializer(serializers.ModelSerializer):
    tenant_nominativo = serializers.CharField(source="tenant.nominativo", read_only=True)
    room_nome = serializers.CharField(source="room.nome", read_only=True)
    contract_nome = serializers.SerializerMethodField()

    class Meta:
        model = RoomAssignment
        fields = [
            "id",
            "room",
            "room_nome",
            "tenant",
            "tenant_nominativo",
            "contract",
            "contract_nome",
            "valid_from",
            "valid_to",
            "canone_mensile",
            "bank_account_affitto",
            "costo_cessione",
            "data_atto_cessione",
            "subentra_a",
            "note",
        ]

    def get_contract_nome(self, obj) -> str:
        """Etichetta del contratto come la vede l'utente (il nome, o le date
        se il contratto non ne ha uno)."""
        if not obj.contract_id:
            return ""
        return obj.contract.nome or f"Contratto dal {obj.contract.data_decorrenza}"


class CessioneAssignmentSerializer(serializers.Serializer):
    """Input del wizard cessione stanza (POST room-assignments/{id}/cessione).

    Chiude l'assegnazione corrente a ``data_fine`` e ne apre una nuova per
    la stessa stanza dal giorno dopo, con il nuovo inquilino.
    """

    data_fine = serializers.DateField()
    nuovo_tenant = serializers.PrimaryKeyRelatedField(
        queryset=TenantProfile.objects.all()
    )
    canone_mensile = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"),
    )
    costo_cessione = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True,
        min_value=Decimal("0"),
    )
    data_atto_cessione = serializers.DateField(required=False, allow_null=True)


class RataDepositoSerializer(serializers.Serializer):
    importo = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    scadenza = serializers.DateField()


class PrimaAssegnazioneSerializer(serializers.Serializer):
    """Input dell'azione POST room-assignments/prima-assegnazione/: crea in
    un colpo solo il primo RoomAssignment di un inquilino nuovo, con canone,
    ciclo di fatturazione, deposito (eventualmente rateizzato) e quota
    condominio specifica opzionali.
    """

    tenant = serializers.PrimaryKeyRelatedField(queryset=TenantProfile.objects.all())
    # Facoltativo per gli immobili a unità intera: la view risolve l'unica
    # Room della property. Obbligatorio per gli immobili a stanze.
    room = serializers.PrimaryKeyRelatedField(
        queryset=Room.objects.all(), required=False, allow_null=True
    )
    # Facoltativo: se assente si propone il contratto attivo alla data di
    # ingresso. Senza contratto l'inquilino non vede le carte del contratto.
    contract = serializers.PrimaryKeyRelatedField(
        queryset=Contract.objects.all(), required=False, allow_null=True
    )
    valid_from = serializers.DateField()
    canone_mensile = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0")
    )
    ciclo_fatturazione = serializers.ChoiceField(
        choices=TenantProfile.CicloFatturazione.choices
    )
    deposito_totale = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal("0.01"),
    )
    rate_deposito = RataDepositoSerializer(many=True, required=False)
    data_versamento_deposito = serializers.DateField(required=False, allow_null=True)
    quota_condominio_mensile = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal("0"),
    )

    def validate(self, attrs):
        rate = attrs.get("rate_deposito") or []
        deposito_totale = attrs.get("deposito_totale")
        if rate:
            if deposito_totale is None:
                raise serializers.ValidationError(
                    {
                        "deposito_totale": (
                            "Obbligatorio se sono indicate le rate del deposito."
                        )
                    }
                )
            somma = sum((r["importo"] for r in rate), Decimal("0"))
            if somma != deposito_totale:
                raise serializers.ValidationError(
                    "Le rate non sommano al totale del deposito."
                )
            scadenze = [r["scadenza"] for r in rate]
            if scadenze != sorted(scadenze):
                raise serializers.ValidationError(
                    "Le scadenze delle rate devono essere in ordine non decrescente."
                )
        elif deposito_totale is not None:
            scadenza = attrs.get("data_versamento_deposito") or attrs["valid_from"]
            attrs["rate_deposito"] = [
                {"importo": deposito_totale, "scadenza": scadenza}
            ]
        return attrs


class ContractSerializer(serializers.ModelSerializer):
    regime_fiscale_display = serializers.CharField(
        source="get_regime_fiscale_display", read_only=True
    )
    property = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Contract
        fields = [
            "id",
            "property",
            "nome",
            "data_stipula",
            "data_decorrenza",
            "termine",
            "durata_anni",
            "durata_rinnovo_anni",
            "asseverato",
            "regime_fiscale",
            "regime_fiscale_display",
            "default_pagatore_bollette",
            "note",
            "ufficio_registrazione",
            "data_registrazione",
            "numero_registrazione",
            "serie_registrazione",
            "codice_identificativo",
        ]


class DocumentTemplateSerializer(serializers.ModelSerializer):
    codice_display = serializers.CharField(source="get_codice_display", read_only=True)
    property = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        from .models import DocumentTemplate

        model = DocumentTemplate
        fields = [
            "id",
            "property",
            "codice",
            "codice_display",
            "nome",
            "corpo_html",
            "note",
            "updated_at",
        ]


class OwnerBankAccountSerializer(serializers.ModelSerializer):
    # L'owner è sempre il profilo del richiedente (assegnato dal server):
    # nessuno può creare/modificare conti a nome altrui.
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    owner_nominativo = serializers.CharField(source="owner.nominativo", read_only=True)

    class Meta:
        model = OwnerBankAccount
        fields = [
            "id",
            "owner",
            "owner_nominativo",
            "banca",
            "intestatario",
            "iban",
            "attivo",
            "ordinamento",
        ]


class PropertySerializer(serializers.ModelSerializer):
    """Immobile con il ruolo dell'utente corrente.

    Include i campi della galleria pubblica (slug, toggle, foto singleton,
    testi), editabili via PATCH dai membri operativi."""

    mio_ruolo = serializers.SerializerMethodField()
    n_stanze = serializers.SerializerMethodField()

    class Meta:
        from .models import Property

        model = Property
        fields = [
            "id",
            "nome",
            "tipo_gestione",
            "slug",
            "indirizzo",
            "pubblica",
            "foto_hero",
            "foto_planimetria",
            "foto_mappa",
            "testi_pubblici",
            "bank_account_utenze",
            "owner_anticipa_cessioni",
            "owner_firmatario",
            "mio_ruolo",
            "n_stanze",
            *CAMPI_INDIRIZZO_STRUTTURATO,
        ]
        extra_kwargs = {"slug": {"required": False}}

    def get_mio_ruolo(self, obj):
        from .context import ruolo_su_property

        request = self.context.get("request")
        if request is None:
            return None
        return ruolo_su_property(request.user, obj)

    def get_n_stanze(self, obj):
        return obj.rooms.count()

    def validate(self, attrs):
        tipo_gestione = attrs.get(
            "tipo_gestione",
            getattr(self.instance, "tipo_gestione", None),
        )
        from .models import Property

        if (
            self.instance is not None
            and tipo_gestione == Property.TipoGestione.UNITA_INTERA
            and self.instance.rooms.count() > 1
        ):
            raise serializers.ValidationError(
                {
                    "tipo_gestione": (
                        "Impossibile passare a unità intera: l'immobile ha già più "
                        "di una stanza. Ridurre a una sola stanza prima del cambio."
                    )
                }
            )
        return attrs


class PropertyMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    nominativo = serializers.SerializerMethodField()
    # Id dell'OwnerProfile del membro (None se non ne ha): serve al frontend
    # per proporre l'intestatario quando il superuser crea un conto altrui.
    owner_profile = serializers.SerializerMethodField()

    class Meta:
        from .models import PropertyMembership

        model = PropertyMembership
        fields = [
            "id", "user", "username", "email", "nominativo", "owner_profile",
            "ruolo", "invitato_da",
        ]
        read_only_fields = [
            "id", "username", "email", "nominativo", "owner_profile",
            "invitato_da",
        ]

    def get_nominativo(self, obj):
        profilo = getattr(obj.user, "owner_profile", None)
        if profilo:
            return profilo.nominativo
        return obj.user.get_full_name() or obj.user.username

    def get_owner_profile(self, obj):
        profilo = getattr(obj.user, "owner_profile", None)
        return profilo.id if profilo else None


class OwnershipShareSerializer(serializers.ModelSerializer):
    owner_nominativo = serializers.CharField(source="owner.nominativo", read_only=True)

    class Meta:
        from .models import OwnershipShare

        model = OwnershipShare
        fields = [
            "id", "owner", "owner_nominativo", "quota", "valid_from", "valid_to",
        ]


class InvitoMembroSerializer(serializers.Serializer):
    email = serializers.EmailField()
    ruolo = serializers.ChoiceField(choices=[])
    nominativo = serializers.CharField(required=False, allow_blank=True, default="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import PropertyMembership

        self.fields["ruolo"].choices = PropertyMembership.Ruolo.choices


class QuoteReplaceSerializer(serializers.Serializer):
    """Nuovo assetto quote dell'immobile a partire da una data.

    ``quote`` = [{"user": id, "quota": "0.3334"}, ...] — la somma deve fare 1.
    """

    valid_from = serializers.DateField()
    quote = serializers.ListField(
        child=serializers.DictField(), allow_empty=False,
    )
