# TODO: migrare a jmb.jadmin (admin-tabs, ajax-inlines, modal-edit) quando il pacchetto sarà disponibile
"""
Admin Django per l'app billing.
Gestisce pagamenti affitto, transazioni bancarie, fornitori,
categorie spese, spese, addebiti extra, bollette e conguagli utenze.
"""
from django.contrib import admin

from .models import (
    AnnualUtilityCost,
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


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------


class UtilityChargeInline(admin.TabularInline):
    """Addebiti utenze per inquilino in linea nel periodo (sola lettura)."""

    model = UtilityCharge
    extra = 0
    fields = ("assignment", "importo_totale", "scadenza", "stato")
    readonly_fields = ("assignment", "importo_totale", "scadenza", "stato")
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


class UtilityChargeLineInline(admin.TabularInline):
    """Righe di dettaglio conguaglio in linea nel conguaglio inquilino."""

    model = UtilityChargeLine
    extra = 0
    fields = ("voce", "importo", "dettaglio")


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "partita_iva")
    list_filter = ("tipo",)
    search_fields = ("nome", "partita_iva")
    ordering = ("nome",)
    fieldsets = (
        ("Anagrafica", {
            "fields": ("nome", "tipo", "partita_iva"),
        }),
        ("Contatto", {
            "fields": ("contatto",),
            "classes": ("collapse",),
        }),
    )


# ---------------------------------------------------------------------------
# ExpenseCategory
# ---------------------------------------------------------------------------


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("nome", "codice", "ripartibile_inquilini")
    search_fields = ("nome", "codice")
    ordering = ("nome",)


# ---------------------------------------------------------------------------
# RentPayment
# ---------------------------------------------------------------------------


@admin.register(RentPayment)
class RentPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "assignment", "competenza_da", "competenza_a",
        "importo_dovuto", "importo_pagato", "stato",
    )
    list_filter = ("stato", "competenza_da", "is_aggiustamento")
    search_fields = (
        "assignment__tenant__nominativo",
        "assignment__room__nome",
    )
    list_select_related = ("assignment__tenant", "assignment__room")
    autocomplete_fields = ("assignment", "incassato_da_owner", "bank_account_destinazione")
    date_hierarchy = "competenza_da"
    ordering = ("-scadenza", "assignment__tenant__nominativo")
    fieldsets = (
        ("Periodo", {
            "fields": ("assignment", "competenza_da", "competenza_a", "scadenza", "is_aggiustamento"),
        }),
        ("Importi", {
            "fields": ("importo_dovuto", "importo_pagato", "stato", "data_pagamento"),
        }),
        ("Riconciliazione bancaria", {
            "fields": ("incassato_da_owner", "bank_account_destinazione", "ricevuta"),
            "classes": ("collapse",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# BankTransaction
# ---------------------------------------------------------------------------


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "data", "descrizione_breve", "importo",
        "owner_account", "riconciliato_con_payment",
    )
    list_filter = ("owner_account",)
    search_fields = ("descrizione",)
    list_select_related = ("owner_account__owner", "riconciliato_con_payment")
    autocomplete_fields = ("owner_account", "riconciliato_con_payment", "riconciliato_con_charge")
    date_hierarchy = "data"
    ordering = ("-data",)
    fieldsets = (
        ("Transazione", {
            "fields": ("data", "descrizione", "importo", "owner_account"),
        }),
        ("Riconciliazione", {
            "fields": ("riconciliato_con_payment", "riconciliato_con_charge"),
            "classes": ("collapse",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Descrizione")
    def descrizione_breve(self, obj):
        return (obj.descrizione[:60] + "…") if len(obj.descrizione) > 60 else obj.descrizione


# ---------------------------------------------------------------------------
# Expense
# ---------------------------------------------------------------------------


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "data", "category", "supplier", "importo",
        "anticipata_da_owner", "ripartibile_su_inquilini",
    )
    list_filter = ("category", "anticipata_da_owner", "ripartibile_su_inquilini")
    search_fields = ("descrizione", "category__nome", "supplier__nome")
    list_select_related = ("category", "supplier", "anticipata_da_owner")
    autocomplete_fields = ("category", "supplier", "anticipata_da_owner", "riferimento_quota_owner")
    date_hierarchy = "data"
    ordering = ("-data",)
    fieldsets = (
        ("Spesa", {
            "fields": ("data", "descrizione", "category", "supplier", "importo", "ripartibile_su_inquilini"),
        }),
        ("Anticipo", {
            "fields": ("anticipata_da_owner", "riferimento_quota_owner"),
        }),
        ("Allegato", {
            "fields": ("allegato",),
            "classes": ("collapse",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# ExtraCharge
# ---------------------------------------------------------------------------


@admin.register(ExtraCharge)
class ExtraChargeAdmin(admin.ModelAdmin):
    list_display = ("assignment", "descrizione", "importo", "scadenza", "stato")
    list_filter = ("stato",)
    search_fields = ("descrizione", "assignment__tenant__nominativo")
    list_select_related = ("assignment__tenant",)
    autocomplete_fields = ("assignment",)
    ordering = ("-scadenza",)
    fieldsets = (
        ("Addebito", {
            "fields": ("assignment", "data", "descrizione", "importo", "scadenza", "stato"),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# UtilityBill
# ---------------------------------------------------------------------------


@admin.register(UtilityBill)
class UtilityBillAdmin(admin.ModelAdmin):
    list_display = (
        "supplier", "numero_fattura", "periodo_da",
        "periodo_a", "importo_totale", "pagata_da_owner",
    )
    list_filter = ("supplier",)
    search_fields = ("numero_fattura", "supplier__nome")
    list_select_related = ("supplier", "pagata_da_owner")
    autocomplete_fields = ("supplier", "pagata_da_owner")
    date_hierarchy = "periodo_da"
    ordering = ("-data_emissione",)
    fieldsets = (
        ("Bolletta", {
            "fields": ("supplier", "numero_fattura", "data_emissione"),
        }),
        ("Periodo e importo", {
            "fields": ("periodo_da", "periodo_a", "importo_totale"),
        }),
        ("Pagamento", {
            "fields": ("pagata_da_owner", "file_pdf"),
            "classes": ("collapse",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# AnnualUtilityCost
# ---------------------------------------------------------------------------


@admin.register(AnnualUtilityCost)
class AnnualUtilityCostAdmin(admin.ModelAdmin):
    list_display = ("voce", "anno", "importo_annuale", "valid_from", "valid_to")
    list_filter = ("voce", "anno")
    ordering = ("-anno", "voce")
    fieldsets = (
        ("Costo annuale", {
            "fields": ("voce", "anno", "importo_annuale"),
        }),
        ("Validità", {
            "fields": ("valid_from", "valid_to"),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# UtilityChargePeriod
# ---------------------------------------------------------------------------


@admin.register(UtilityChargePeriod)
class UtilityChargePeriodAdmin(admin.ModelAdmin):
    list_display = (
        "periodo_da", "periodo_a",
        "criterio_ripartizione", "stato", "data_invio",
    )
    list_filter = ("stato", "criterio_ripartizione")
    search_fields = ("periodo_da", "periodo_a")
    ordering = ("-periodo_da",)
    inlines = (UtilityChargeInline,)
    fieldsets = (
        ("Periodo", {
            "fields": ("periodo_da", "periodo_a", "criterio_ripartizione", "stato", "data_invio"),
        }),
        ("Import storico", {
            "fields": ("manual_totals",),
            "classes": ("collapse",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# UtilityCharge
# ---------------------------------------------------------------------------


@admin.register(UtilityCharge)
class UtilityChargeAdmin(admin.ModelAdmin):
    list_display = (
        "assignment", "period", "importo_totale",
        "scadenza", "stato", "importo_pagato",
    )
    list_filter = ("stato", "period")
    search_fields = (
        "assignment__tenant__nominativo",
        "period__periodo_da",
    )
    list_select_related = ("assignment__tenant", "period")
    autocomplete_fields = ("assignment", "period")
    ordering = ("-period__periodo_da", "assignment__tenant__nominativo")
    inlines = (UtilityChargeLineInline,)
    fieldsets = (
        ("Conguaglio", {
            "fields": ("period", "assignment", "importo_totale", "scadenza", "stato"),
        }),
        ("Pagamento", {
            "fields": ("data_pagamento", "importo_pagato", "ricevuta"),
            "classes": ("collapse",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# UtilityChargeLine (standalone + inline sopra)
# ---------------------------------------------------------------------------


@admin.register(UtilityChargeLine)
class UtilityChargeLineAdmin(admin.ModelAdmin):
    list_display = ("charge", "voce", "importo")
    list_filter = ("voce",)
    list_select_related = ("charge__assignment__tenant", "charge__period")
    autocomplete_fields = ("charge",)
    ordering = ("charge__period__periodo_da", "voce")
    search_fields = ("charge__assignment__tenant__nominativo",)
    fieldsets = (
        ("Riga", {
            "fields": ("charge", "voce", "importo", "dettaglio"),
        }),
    )
