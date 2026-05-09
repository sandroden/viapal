"""
Serializer per l'app accounting.
"""
from rest_framework import serializers

from accounting.models import InterOwnerEntry, OwnerLedgerEntry, OwnerSettlement


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
            "riferimento_settlement",
            "bank_transaction",
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
            "riferimento_settlement",
            "bank_transaction",
            "note",
        ]


class MarcaBtInterOwnerSerializer(serializers.Serializer):
    """Payload per POST /api/v1/owner-ledger/bt-inter-owner/."""
    bank_transaction = serializers.IntegerField()
    tipo = serializers.ChoiceField(
        choices=["distribuzione", "incasso_conguaglio", "bilaterale", "aggiustamento"],
    )
    controparte_owner = serializers.IntegerField(required=False, allow_null=True)
    settlement = serializers.IntegerField(required=False, allow_null=True)
    descrizione = serializers.CharField(required=False, allow_blank=True, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")


class OwnerSettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = OwnerSettlement
        fields = [
            "id",
            "data",
            "periodo_da",
            "periodo_a",
            "descrizione",
            "snapshot",
            "note",
        ]


class _OwnerMinimalSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nominativo = serializers.CharField()


class SaldoLiveSerializer(serializers.Serializer):
    """Serializer per accounting.services.saldi_live.SaldoLive."""
    owner = _OwnerMinimalSerializer()
    quota = serializers.DecimalField(max_digits=8, decimal_places=4)
    baseline_settlement = serializers.DecimalField(max_digits=12, decimal_places=2)
    incassi_per_causale = serializers.DictField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2),
    )
    spese_per_categoria = serializers.DictField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2),
    )
    anticipi_pendenti = serializers.DecimalField(max_digits=12, decimal_places=2)
    bt_inter_owner = serializers.DecimalField(max_digits=12, decimal_places=2)
    totale = serializers.DecimalField(max_digits=12, decimal_places=2)
