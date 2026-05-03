"""
Serializer per l'app billing.

I tre serializer storici (Rent/Utility/Extra) ora si appoggiano al modello
unificato Receivable, esponendo verso il frontend gli stessi nomi di campo
di prima (importo_dovuto / importo_totale / importo) tramite `source=`.
"""
from rest_framework import serializers

from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    Expense,
    ExpenseCategory,
    Receivable,
    Supplier,
    UtilityBill,
    UtilityChargeLine,
    UtilityChargePeriod,
)


class UtilityChargeLineSerializer(serializers.ModelSerializer):
    voce_display = serializers.CharField(source="get_voce_display", read_only=True)

    class Meta:
        model = UtilityChargeLine
        fields = ["id", "voce", "voce_display", "importo", "dettaglio"]


class RentPaymentSerializer(serializers.ModelSerializer):
    """Serializer compat per receivable causale=affitto."""

    tenant_nominativo = serializers.CharField(
        source="assignment.tenant.nominativo", read_only=True
    )
    room_nome = serializers.CharField(source="assignment.room.nome", read_only=True)
    stato_display = serializers.CharField(source="get_stato_display", read_only=True)

    class Meta:
        model = Receivable
        fields = [
            "id",
            "assignment",
            "tenant_nominativo",
            "room_nome",
            "competenza_da",
            "competenza_a",
            "importo_dovuto",
            "importo_pagato",
            "data_pagamento",
            "scadenza",
            "stato",
            "stato_display",
            "is_aggiustamento",
            "incassato_da_owner",
            "bank_account_destinazione",
            "note",
        ]
        read_only_fields = ["stato_display"]

    def create(self, validated_data):
        validated_data["causale"] = Receivable.Causale.AFFITTO
        return super().create(validated_data)


class UtilityChargeSerializer(serializers.ModelSerializer):
    """Serializer compat per receivable causale=utenze."""

    tenant_nominativo = serializers.CharField(
        source="assignment.tenant.nominativo", read_only=True
    )
    room_nome = serializers.CharField(source="assignment.room.nome", read_only=True)
    stato_display = serializers.CharField(source="get_stato_display", read_only=True)
    period = serializers.PrimaryKeyRelatedField(
        source="utility_period",
        queryset=UtilityChargePeriod.objects.all(),
    )
    periodo_da = serializers.DateField(source="utility_period.periodo_da", read_only=True)
    periodo_a = serializers.DateField(source="utility_period.periodo_a", read_only=True)
    importo_totale = serializers.DecimalField(
        source="importo_dovuto", max_digits=10, decimal_places=2
    )
    lines = UtilityChargeLineSerializer(source="utility_lines", many=True, read_only=True)

    class Meta:
        model = Receivable
        fields = [
            "id",
            "period",
            "periodo_da",
            "periodo_a",
            "assignment",
            "tenant_nominativo",
            "room_nome",
            "importo_totale",
            "scadenza",
            "stato",
            "stato_display",
            "data_pagamento",
            "importo_pagato",
            "note",
            "lines",
        ]
        read_only_fields = ["stato_display", "periodo_da", "periodo_a", "lines"]

    def create(self, validated_data):
        validated_data["causale"] = Receivable.Causale.UTENZE
        return super().create(validated_data)


class UtilityChargePeriodSerializer(serializers.ModelSerializer):
    stato_display = serializers.CharField(source="get_stato_display", read_only=True)
    criterio_display = serializers.CharField(
        source="get_criterio_ripartizione_display", read_only=True
    )

    class Meta:
        model = UtilityChargePeriod
        fields = [
            "id",
            "periodo_da",
            "periodo_a",
            "criterio_ripartizione",
            "criterio_display",
            "stato",
            "stato_display",
            "data_invio",
            "note",
        ]


class SupplierSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Supplier
        fields = ["id", "nome", "tipo", "tipo_display", "partita_iva", "contatto"]


class UtilityBillSerializer(serializers.ModelSerializer):
    supplier_nome = serializers.CharField(source="supplier.nome", read_only=True)
    pagata_da_nominativo = serializers.CharField(
        source="pagata_da_owner.nominativo", read_only=True
    )

    class Meta:
        model = UtilityBill
        fields = [
            "id",
            "supplier",
            "supplier_nome",
            "prodotto",
            "consumo",
            "numero_fattura",
            "data_emissione",
            "periodo_da",
            "periodo_a",
            "importo_totale",
            "file_pdf",
            "pagata_da_owner",
            "pagata_da_nominativo",
            "note",
        ]


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "nome", "codice", "ripartibile_inquilini"]


class ExpenseSerializer(serializers.ModelSerializer):
    category_nome = serializers.CharField(source="category.nome", read_only=True)
    anticipata_da_nominativo = serializers.CharField(
        source="anticipata_da_owner.nominativo", read_only=True
    )

    class Meta:
        model = Expense
        fields = [
            "id",
            "data",
            "category",
            "category_nome",
            "supplier",
            "importo",
            "descrizione",
            "anticipata_da_owner",
            "anticipata_da_nominativo",
            "ripartibile_su_inquilini",
            "riferimento_quota_owner",
            "allegato",
            "note",
        ]


class ExtraChargeSerializer(serializers.ModelSerializer):
    """Serializer compat per receivable causale=extra."""

    tenant_nominativo = serializers.CharField(
        source="assignment.tenant.nominativo", read_only=True
    )
    stato_display = serializers.CharField(source="get_stato_display", read_only=True)
    data = serializers.DateField(source="competenza_da")
    importo = serializers.DecimalField(
        source="importo_dovuto", max_digits=10, decimal_places=2
    )

    class Meta:
        model = Receivable
        fields = [
            "id",
            "assignment",
            "tenant_nominativo",
            "data",
            "descrizione",
            "importo",
            "scadenza",
            "stato",
            "stato_display",
            "importo_pagato",
            "data_pagamento",
            "note",
        ]
        read_only_fields = ["stato_display"]

    def create(self, validated_data):
        validated_data["causale"] = Receivable.Causale.EXTRA
        return super().create(validated_data)


class BankTransactionAllocationSerializer(serializers.ModelSerializer):
    receivable_descrizione = serializers.SerializerMethodField()
    causale = serializers.CharField(source="receivable.causale", read_only=True)

    class Meta:
        model = BankTransactionAllocation
        fields = ["id", "receivable", "causale", "receivable_descrizione", "importo"]

    def get_receivable_descrizione(self, obj):
        r = obj.receivable
        if r.causale == Receivable.Causale.AFFITTO:
            return f"Affitto {r.competenza_da:%B %Y} — {r.assignment.tenant.nominativo}"
        if r.causale == Receivable.Causale.UTENZE:
            base = r.utility_period.periodo_da if r.utility_period else r.competenza_da
            return f"Utenze {base:%B %Y} — {r.assignment.tenant.nominativo}"
        return f"{r.descrizione or 'Extra'} — {r.assignment.tenant.nominativo}"


class BankTransactionSerializer(serializers.ModelSerializer):
    conto_banca = serializers.CharField(source="owner_account.banca", read_only=True)
    allocations = BankTransactionAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = BankTransaction
        fields = [
            "id",
            "data",
            "descrizione",
            "importo",
            "owner_account",
            "conto_banca",
            "allocations",
            "note",
        ]
