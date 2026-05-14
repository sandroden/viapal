"""
Serializer per l'app properties.
"""
from rest_framework import serializers

from properties.models import Contract, OwnerBankAccount, OwnerProfile, Room, RoomAssignment, TenantProfile


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
            "deposito_restituito",
            "data_restituzione_deposito",
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
