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

    class Meta:
        model = TenantProfile
        fields = [
            "id",
            "username",
            "nominativo",
            "codice_fiscale",
            "telefono",
            "email_alt",
            "giorno_pagamento_affitto",
            "frequenza_conguagli",
            "note_pagamento",
        ]


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
            "deposito_versato",
            "deposito_restituito",
            "data_restituzione_deposito",
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
