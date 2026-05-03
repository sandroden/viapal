"""
Serializer per l'app accounting.
"""
from rest_framework import serializers

from accounting.models import InterOwnerEntry, OwnerLedgerEntry


class OwnerLedgerEntrySerializer(serializers.ModelSerializer):
    owner_nominativo = serializers.CharField(source="owner.nominativo", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = OwnerLedgerEntry
        fields = [
            "id",
            "owner",
            "owner_nominativo",
            "data",
            "descrizione",
            "importo",
            "tipo",
            "tipo_display",
            "riferimento_receivable",
            "riferimento_expense",
            "note",
        ]


class InterOwnerEntrySerializer(serializers.ModelSerializer):
    owner_da_nominativo = serializers.CharField(source="owner_da.nominativo", read_only=True)
    owner_a_nominativo = serializers.CharField(source="owner_a.nominativo", read_only=True)

    class Meta:
        model = InterOwnerEntry
        fields = [
            "id",
            "owner_da",
            "owner_da_nominativo",
            "owner_a",
            "owner_a_nominativo",
            "data",
            "importo",
            "descrizione",
            "riferimento_loan",
            "riferimento_expense",
            "note",
        ]
