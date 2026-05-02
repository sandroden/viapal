"""
Serializer per l'app billing.
"""
from rest_framework import serializers

from billing.models import (
    BankTransaction,
    Expense,
    ExpenseCategory,
    ExtraCharge,
    RentPayment,
    Supplier,
    UtilityBill,
    UtilityCharge,
    UtilityChargeLine,
    UtilityChargePeriod,
)


class RentPaymentSerializer(serializers.ModelSerializer):
    tenant_nominativo = serializers.CharField(
        source="assignment.tenant.nominativo", read_only=True
    )
    room_nome = serializers.CharField(source="assignment.room.nome", read_only=True)
    stato_display = serializers.CharField(source="get_stato_display", read_only=True)

    class Meta:
        model = RentPayment
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


class UtilityChargeLineSerializer(serializers.ModelSerializer):
    voce_display = serializers.CharField(source="get_voce_display", read_only=True)

    class Meta:
        model = UtilityChargeLine
        fields = ["id", "voce", "voce_display", "importo", "dettaglio"]


class UtilityChargeSerializer(serializers.ModelSerializer):
    tenant_nominativo = serializers.CharField(
        source="assignment.tenant.nominativo", read_only=True
    )
    room_nome = serializers.CharField(source="assignment.room.nome", read_only=True)
    stato_display = serializers.CharField(source="get_stato_display", read_only=True)
    periodo_da = serializers.DateField(source="period.periodo_da", read_only=True)
    periodo_a = serializers.DateField(source="period.periodo_a", read_only=True)
    lines = UtilityChargeLineSerializer(many=True, read_only=True)

    class Meta:
        model = UtilityCharge
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
    tenant_nominativo = serializers.CharField(
        source="assignment.tenant.nominativo", read_only=True
    )
    stato_display = serializers.CharField(source="get_stato_display", read_only=True)

    class Meta:
        model = ExtraCharge
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
            "note",
        ]
        read_only_fields = ["stato_display"]


class BankTransactionSerializer(serializers.ModelSerializer):
    conto_banca = serializers.CharField(source="owner_account.banca", read_only=True)

    class Meta:
        model = BankTransaction
        fields = [
            "id",
            "data",
            "descrizione",
            "importo",
            "owner_account",
            "conto_banca",
            "riconciliato_con_payment",
            "riconciliato_con_charge",
            "note",
        ]
