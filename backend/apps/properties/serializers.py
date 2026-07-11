"""
Serializer per l'app properties.
"""
from rest_framework import serializers

from properties.models import (
    Contract,
    OwnerBankAccount,
    OwnerProfile,
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
        ]


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


class PropertySerializer(serializers.ModelSerializer):
    """Immobile con il ruolo dell'utente corrente."""

    mio_ruolo = serializers.SerializerMethodField()
    n_stanze = serializers.SerializerMethodField()

    class Meta:
        from .models import Property

        model = Property
        fields = [
            "id",
            "nome",
            "indirizzo",
            "bank_account_utenze",
            "owner_anticipa_cessioni",
            "mio_ruolo",
            "n_stanze",
        ]

    def get_mio_ruolo(self, obj):
        from .context import ruolo_su_property

        request = self.context.get("request")
        if request is None:
            return None
        return ruolo_su_property(request.user, obj)

    def get_n_stanze(self, obj):
        return obj.rooms.count()


class PropertyMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    nominativo = serializers.SerializerMethodField()

    class Meta:
        from .models import PropertyMembership

        model = PropertyMembership
        fields = ["id", "user", "username", "email", "nominativo", "ruolo", "invitato_da"]
        read_only_fields = ["id", "username", "email", "nominativo", "invitato_da"]

    def get_nominativo(self, obj):
        profilo = getattr(obj.user, "owner_profile", None)
        if profilo:
            return profilo.nominativo
        return obj.user.get_full_name() or obj.user.username


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
