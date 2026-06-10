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


class GeneraSettlementSerializer(serializers.Serializer):
    """Payload per POST /api/v1/owner-settlements/genera/."""
    anno = serializers.IntegerField(required=False, allow_null=True)
    periodo_da = serializers.DateField(required=False, allow_null=True)
    periodo_a = serializers.DateField(required=False, allow_null=True)
    descrizione = serializers.CharField(required=False, allow_blank=True, default="")
    dry_run = serializers.BooleanField(default=False)
    reset = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if not attrs.get("anno") and not (attrs.get("periodo_da") and attrs.get("periodo_a")):
            raise serializers.ValidationError(
                "Indicare `anno` oppure `periodo_da` + `periodo_a`.",
            )
        return attrs


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


class _ReceivableOrfanoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    tenant = serializers.CharField()
    causale = serializers.CharField()
    importo = serializers.DecimalField(max_digits=12, decimal_places=2)
    data = serializers.DateField()
    motivo = serializers.CharField()


class _ExpenseOrfanaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    descrizione = serializers.CharField()
    categoria = serializers.CharField()
    importo = serializers.DecimalField(max_digits=12, decimal_places=2)
    data = serializers.DateField()
    motivo = serializers.CharField()


class QuadraturaSerializer(serializers.Serializer):
    """Serializer per accounting.services.saldi_live.Quadratura."""
    somma_saldi = serializers.DecimalField(max_digits=12, decimal_places=2)
    quadra = serializers.BooleanField()
    receivable_orfani = _ReceivableOrfanoSerializer(many=True)
    expense_orfane = _ExpenseOrfanaSerializer(many=True)


class PianoRientroVoceSerializer(serializers.Serializer):
    """Un bonifico proposto del piano di rientro: da → a, importo."""
    da = _OwnerMinimalSerializer()
    a = _OwnerMinimalSerializer()
    importo = serializers.DecimalField(max_digits=12, decimal_places=2)
