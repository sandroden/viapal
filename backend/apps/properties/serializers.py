"""
Serializer per l'app properties.
"""
from rest_framework import serializers

from properties.models import (
    Contract,
    GalleryArea,
    GalleryImage,
    OwnerBankAccount,
    OwnerProfile,
    Property,
    Room,
    RoomAssignment,
    TenantDocument,
    TenantProfile,
)


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

    class Meta:
        model = TenantProfile
        fields = [
            "id",
            "username",
            "email",
            "nominativo",
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


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = [
            "id",
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


class PropertySerializer(serializers.ModelSerializer):
    """Serializer di scrittura/lettura per l'immobile (area proprietario)."""

    class Meta:
        model = Property
        fields = [
            "id",
            "nome",
            "slug",
            "indirizzo",
            "pubblica",
            "foto_hero",
            "foto_planimetria",
            "foto_mappa",
            "testi_pubblici",
        ]
        extra_kwargs = {"slug": {"required": False}}


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
        # Nessuna foto per le stanze non disponibili (da design).
        if not obj.disponibile:
            return []
        request = self.context.get("request")
        return [
            {
                "id": img.id,
                "url": request.build_absolute_uri(img.image.url) if request else img.image.url,
                "didascalia": img.didascalia,
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

    class Meta:
        model = RoomAssignment
        fields = [
            "id",
            "room",
            "room_nome",
            "tenant",
            "tenant_nominativo",
            "valid_from",
            "valid_to",
            "canone_mensile",
            "costo_cessione",
            "data_atto_cessione",
            "note",
        ]


class ContractSerializer(serializers.ModelSerializer):
    regime_fiscale_display = serializers.CharField(
        source="get_regime_fiscale_display", read_only=True
    )

    class Meta:
        model = Contract
        fields = [
            "id",
            "data_stipula",
            "data_decorrenza",
            "durata_anni",
            "asseverato",
            "regime_fiscale",
            "regime_fiscale_display",
            "note",
        ]


class OwnerBankAccountSerializer(serializers.ModelSerializer):
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
