"""
Serializer per l'app billing.

I tre serializer storici (Rent/Utility/Extra) ora si appoggiano al modello
unificato Receivable, esponendo verso il frontend gli stessi nomi di campo
di prima (importo_dovuto / importo_totale / importo) tramite `source=`.
"""
from rest_framework import serializers

from billing._dates import format_mese_anno
from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    Expense,
    ExpenseCategory,
    Receivable,
    Supplier,
    UtilityBill,
    UtilityChargePeriod,
)


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
    period_tot_luce = serializers.DecimalField(
        source="utility_period.tot_luce", max_digits=10, decimal_places=2, read_only=True
    )
    period_tot_gas = serializers.DecimalField(
        source="utility_period.tot_gas", max_digits=10, decimal_places=2, read_only=True
    )
    period_tot_tari = serializers.DecimalField(
        source="utility_period.tot_tari", max_digits=10, decimal_places=2, read_only=True
    )
    period_tot_altro = serializers.DecimalField(
        source="utility_period.tot_altro", max_digits=10, decimal_places=2, read_only=True
    )
    period_giorni_totali = serializers.IntegerField(
        source="utility_period.giorni_totali", read_only=True
    )

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
            "giorni_presenza",
            "period_tot_luce",
            "period_tot_gas",
            "period_tot_tari",
            "period_tot_altro",
            "period_giorni_totali",
        ]
        read_only_fields = [
            "stato_display", "periodo_da", "periodo_a",
            "period_tot_luce", "period_tot_gas", "period_tot_tari",
            "period_tot_altro", "period_giorni_totali",
        ]

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
            "tot_luce",
            "tot_gas",
            "tot_tari",
            "tot_altro",
            "giorni_totali",
            "nota_calcolo",
        ]


class SupplierSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Supplier
        fields = ["id", "nome", "tipo", "tipo_display", "partita_iva", "contatto"]


class UtilityBillSerializer(serializers.ModelSerializer):
    """Serializer di lettura/scrittura per UtilityBill.

    Lato write il fornitore può essere passato come ``supplier`` (id) oppure
    via ``supplier_nome`` (stringa): in quest'ultimo caso viene applicato
    ``Supplier.objects.get_or_create(nome=...)`` con tipo ricavato dal
    ``prodotto`` (luce→energia, gas→gas, acqua→acqua).
    """

    supplier_nome = serializers.CharField(required=False, allow_blank=True)
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
        extra_kwargs = {"supplier": {"required": False}}

    PRODOTTO_TIPO_FORNITORE = {
        UtilityBill.Prodotto.LUCE: Supplier.TipoFornitore.ENERGIA,
        UtilityBill.Prodotto.GAS: Supplier.TipoFornitore.GAS,
        UtilityBill.Prodotto.ACQUA: Supplier.TipoFornitore.ACQUA,
    }

    def validate(self, attrs):
        supplier = attrs.get("supplier")
        nome = attrs.pop("supplier_nome", "") or ""
        nome = nome.strip()
        if supplier is None:
            if not nome:
                raise serializers.ValidationError(
                    {"supplier": "Indicare 'supplier' (id) oppure 'supplier_nome'."}
                )
            tipo = self.PRODOTTO_TIPO_FORNITORE.get(
                attrs.get("prodotto") or UtilityBill.Prodotto.LUCE,
                Supplier.TipoFornitore.ALTRO,
            )
            existing = Supplier.objects.filter(nome__iexact=nome).first()
            attrs["supplier"] = existing or Supplier.objects.create(
                nome=nome, tipo=tipo
            )
        return attrs


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "nome", "codice", "ripartibile_inquilini"]


class ExpenseSerializer(serializers.ModelSerializer):
    category_nome = serializers.CharField(source="category.nome", read_only=True)
    anticipata_da_nominativo = serializers.CharField(
        source="anticipata_da_owner.nominativo", read_only=True
    )
    bolletta_id = serializers.IntegerField(
        source="utility_bill.id", read_only=True, allow_null=True,
    )
    bolletta_numero = serializers.CharField(
        source="utility_bill.numero_fattura", read_only=True, allow_null=True,
    )
    bolletta_prodotto = serializers.CharField(
        source="utility_bill.prodotto", read_only=True, allow_null=True,
    )
    bolletta_consumo = serializers.DecimalField(
        source="utility_bill.consumo",
        max_digits=10, decimal_places=3,
        read_only=True, allow_null=True,
    )
    file_pdf = serializers.SerializerMethodField()

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
            "bolletta_id",
            "bolletta_numero",
            "bolletta_prodotto",
            "bolletta_consumo",
            "file_pdf",
        ]

    def get_file_pdf(self, obj):
        bolletta = getattr(obj, "utility_bill", None)
        if not bolletta or not bolletta.file_pdf:
            return None
        # URL relativo (/media/...) → il frontend lo carica nella sua origine
        # via proxy, stesso-origin per l'iframe (no X-Frame-Options issue).
        return bolletta.file_pdf.url


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
            return f"Affitto {format_mese_anno(r.competenza_da)} — {r.assignment.tenant.nominativo}"
        if r.causale == Receivable.Causale.UTENZE:
            base = r.utility_period.periodo_da if r.utility_period else r.competenza_da
            return f"Utenze {format_mese_anno(base)} — {r.assignment.tenant.nominativo}"
        return f"{r.descrizione or 'Extra'} — {r.assignment.tenant.nominativo}"


class BankTransactionSerializer(serializers.ModelSerializer):
    conto_banca = serializers.CharField(source="owner_account.banca", read_only=True)
    allocations = BankTransactionAllocationSerializer(many=True, read_only=True)
    importo_allocato = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    residuo = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    stato_riconciliazione = serializers.CharField(read_only=True)
    is_inter_owner = serializers.SerializerMethodField()

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
            "importo_allocato",
            "residuo",
            "stato_riconciliazione",
            "is_inter_owner",
            "note",
        ]

    def get_is_inter_owner(self, obj) -> bool:
        return obj.ledger_entries.exists() or obj.inter_owner_entries.exists()


class ReceivableForReconcileSerializer(serializers.ModelSerializer):
    """Serializer compatto per la pagina di riconciliazione frontend.

    Espone i campi minimi per identificare il Receivable nella colonna a destra
    e calcolare residuo da abbinare. Non sostituisce i serializer per causale.
    """

    descrizione_estesa = serializers.SerializerMethodField()
    tenant_id = serializers.IntegerField(
        source="assignment.tenant.id", read_only=True
    )
    tenant_nominativo = serializers.CharField(
        source="assignment.tenant.nominativo", read_only=True
    )
    importo_allocato = serializers.SerializerMethodField()
    residuo = serializers.SerializerMethodField()
    stato_display = serializers.CharField(source="get_stato_display", read_only=True)
    allocations = serializers.SerializerMethodField()

    class Meta:
        model = Receivable
        fields = [
            "id",
            "causale",
            "descrizione_estesa",
            "assignment",
            "tenant_id",
            "tenant_nominativo",
            "scadenza",
            "competenza_da",
            "competenza_a",
            "importo_dovuto",
            "importo_allocato",
            "residuo",
            "stato",
            "stato_display",
            "allocations",
        ]

    def get_allocations(self, r: Receivable) -> list[dict]:
        return [
            {
                "id": a.pk,
                "bank_transaction": a.bank_transaction_id,
                "bt_data": a.bank_transaction.data,
                "bt_descrizione": (a.bank_transaction.descrizione or "")[:200],
                "bt_importo": a.bank_transaction.importo,
                "importo": a.importo,
            }
            for a in r.allocations.all()
        ]

    def get_descrizione_estesa(self, r: Receivable) -> str:
        # Mantiene allineata l'etichetta con dashboard_views._descrizione_receivable.
        if r.causale == Receivable.Causale.AFFITTO:
            return f"Affitto {format_mese_anno(r.competenza_da)}"
        if r.causale == Receivable.Causale.UTENZE:
            base = r.utility_period.periodo_da if r.utility_period else r.competenza_da
            return f"Utenze {format_mese_anno(base)}"
        return r.descrizione or "Addebito extra"

    def get_importo_allocato(self, r: Receivable):
        # Se la queryset è già annotata con _alloc, riusala per non rifare la SUM.
        cached = getattr(r, "_alloc", None)
        if cached is not None:
            return cached
        from django.db.models import Sum
        agg = r.allocations.aggregate(tot=Sum("importo"))["tot"]
        return agg or 0

    def get_residuo(self, r: Receivable):
        allocato = self.get_importo_allocato(r) or 0
        return r.importo_dovuto - allocato
