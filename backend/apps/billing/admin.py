"""
Admin Django per l'app billing.
Gestisce: addebiti inquilini (Receivable, con filtro per causale: affitto/utenze/extra),
fornitori, categorie spese, spese, bollette, utenze e transazioni bancarie.
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from jmb.jadmin import JumboModelAdmin, ModalEditMixin

from .models import (
    AnnualUtilityCost,
    BankTransaction,
    BankTransactionAllocation,
    Expense,
    ExpenseCategory,
    Receivable,
    Supplier,
    TenantCondominioRate,
    UtilityBill,
    UtilityChargeLine,
    UtilityChargePeriod,
)


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------


class ReceivableUtilityInline(admin.TabularInline):
    """Addebiti utenze (Receivable causale=utenze) inline nel UtilityChargePeriod."""

    model = Receivable
    fk_name = "utility_period"
    extra = 0
    fields = ("assignment", "importo_dovuto", "scadenza", "stato")
    readonly_fields = ("assignment", "importo_dovuto", "scadenza", "stato")
    show_change_link = True
    verbose_name = "addebito utenze inquilino"
    verbose_name_plural = "addebiti utenze inquilini"

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(causale=Receivable.Causale.UTENZE)


class UtilityChargeLineInline(admin.TabularInline):
    """Righe di dettaglio (luce/gas/TARI) inline su Receivable utenze."""

    model = UtilityChargeLine
    fk_name = "receivable"
    extra = 0
    fields = ("voce", "importo", "dettaglio")


class BankTransactionAllocationInline(admin.TabularInline):
    """Allocazioni inline su BankTransaction (bonifico → addebiti)."""

    model = BankTransactionAllocation
    extra = 0
    fields = ("receivable", "importo")
    autocomplete_fields = ("receivable",)


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------


@admin.register(Supplier)
class SupplierAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 700
    list_display = (
        "nome", "tipo", "partita_iva",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
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
class ExpenseCategoryAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 600
    list_display = (
        "nome", "codice", "ripartibile_inquilini",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    search_fields = ("nome", "codice")
    ordering = ("nome",)


# ---------------------------------------------------------------------------
# Receivable (addebito unificato: affitto / utenze / extra)
# ---------------------------------------------------------------------------


@admin.register(Receivable)
class ReceivableAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 1000
    list_display = (
        "causale", "assignment", "competenza_da", "competenza_a",
        "importo_dovuto", "scadenza", "stato",
        "incassato_da_owner",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("causale", "stato", "is_aggiustamento")
    search_fields = (
        "descrizione",
        "assignment__tenant__nominativo",
        "assignment__room__nome",
    )
    list_select_related = (
        "assignment__tenant", "assignment__room",
        "incassato_da_owner", "utility_period",
    )
    autocomplete_fields = (
        "assignment", "incassato_da_owner",
        "bank_account_destinazione", "utility_period",
    )
    date_hierarchy = "scadenza"
    ordering = ("-scadenza", "assignment__tenant__nominativo")
    inlines = (UtilityChargeLineInline,)
    advanced_search_fields = (
        ("assignment__tenant__nominativo__icontains:inquilino",
         "assignment__room__nome__icontains:stanza",
         "descrizione__icontains:descrizione"),
        ("causale", "stato", "is_aggiustamento"),
        ("scadenza__range", "scadenza__gte:scadenza ≥", "scadenza__lte:scadenza ≤"),
        ("competenza_da__range", "competenza_da__gte:competenza ≥", "competenza_da__lte:competenza ≤"),
        ("importo_dovuto__gte:dovuto ≥", "importo_dovuto__lte:dovuto ≤"),
        ("data_pagamento__range", "incassato_da_owner:incassato da", "utility_period:periodo utenze"),
    )

    def lookup_allowed(self, lookup, value, request):
        # Whitelist dei lookup attraverso FK profonde usati in advanced_search_fields:
        # Django blocca per default i lookup che attraversano relazioni > 1 livello.
        if lookup in {
            "assignment__tenant__nominativo__icontains",
            "assignment__room__nome__icontains",
        }:
            return True
        return super().lookup_allowed(lookup, value, request)
    fieldsets = (
        ("Addebito", {
            "fields": (
                "assignment", "causale", "descrizione",
                "competenza_da", "competenza_a", "scadenza",
                "is_aggiustamento", "utility_period",
            ),
        }),
        ("Importi e stato", {
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
class BankTransactionAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 900
    list_display = (
        "data", "descrizione_breve", "importo",
        "owner_account", "n_allocations",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("owner_account",)
    search_fields = ("descrizione",)
    list_select_related = ("owner_account__owner",)
    autocomplete_fields = ("owner_account",)
    date_hierarchy = "data"
    ordering = ("-data",)
    inlines = (BankTransactionAllocationInline,)
    advanced_search_fields = (
        ("descrizione__icontains:descrizione", "note__icontains:note"),
        ("data__range", "data__gte:dal", "data__lte:al"),
        ("importo__gte:importo ≥", "importo__lte:importo ≤"),
        ("owner_account:conto",),
    )
    fieldsets = (
        ("Transazione", {
            "fields": ("data", "descrizione", "importo", "owner_account"),
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

    @admin.display(description="Allocazioni")
    def n_allocations(self, obj):
        return obj.allocations.count()


# ---------------------------------------------------------------------------
# Expense
# ---------------------------------------------------------------------------


@admin.register(Expense)
class ExpenseAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 900
    list_display = (
        "data", "category", "supplier", "importo",
        "anticipata_da_owner", "ripartibile_su_inquilini",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("category", "anticipata_da_owner", "ripartibile_su_inquilini")
    search_fields = ("descrizione", "category__nome", "supplier__nome")
    list_select_related = ("category", "supplier", "anticipata_da_owner")
    autocomplete_fields = ("category", "supplier", "anticipata_da_owner", "riferimento_quota_owner")
    date_hierarchy = "data"
    ordering = ("-data",)
    advanced_search_fields = (
        ("descrizione__icontains:descrizione", "category", "supplier"),
        ("data__range", "data__gte:dal", "data__lte:al"),
        ("importo__gte:importo ≥", "importo__lte:importo ≤"),
        ("anticipata_da_owner:anticipata da", "ripartibile_su_inquilini"),
    )
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
# UtilityBill
# ---------------------------------------------------------------------------


@admin.register(UtilityBill)
class UtilityBillAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 900
    list_display = (
        "supplier", "prodotto", "numero_fattura", "periodo_da",
        "periodo_a", "consumo", "importo_totale", "pagata_da_owner",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("prodotto", "supplier")
    search_fields = ("numero_fattura", "supplier__nome")
    list_select_related = ("supplier", "pagata_da_owner")
    autocomplete_fields = ("supplier", "pagata_da_owner")
    date_hierarchy = "periodo_da"
    ordering = ("-data_emissione",)
    advanced_search_fields = (
        ("supplier", "prodotto", "numero_fattura__icontains:numero fattura"),
        ("periodo_da__range", "periodo_da__gte:periodo dal ≥", "periodo_a__lte:periodo al ≤"),
        ("data_emissione__range", "data_emissione__gte:emessa dal", "data_emissione__lte:emessa al"),
        ("importo_totale__gte:importo ≥", "importo_totale__lte:importo ≤", "pagata_da_owner:pagata da"),
    )
    fieldsets = (
        ("Bolletta", {
            "fields": ("supplier", "prodotto", "numero_fattura", "data_emissione"),
        }),
        ("Periodo, consumo e importo", {
            "fields": ("periodo_da", "periodo_a", "consumo", "importo_totale"),
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
class AnnualUtilityCostAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 700
    list_display = (
        "voce", "anno", "importo_annuale", "valid_from", "valid_to",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
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
class UtilityChargePeriodAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 900
    list_display = (
        "periodo_da", "periodo_a",
        "criterio_ripartizione", "stato", "data_invio",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("stato", "criterio_ripartizione")
    search_fields = ("periodo_da", "periodo_a")
    ordering = ("-periodo_da",)
    inlines = (ReceivableUtilityInline,)
    fieldsets = (
        ("Periodo", {
            "fields": ("periodo_da", "periodo_a", "criterio_ripartizione", "stato", "data_invio"),
        }),
        ("Import storico", {
            "fields": ("manual_totals",),
        }),
        ("Note", {
            "fields": ("note",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")
    tabs = (
        (_("Periodo"), {"items": ["Periodo"]}),
        (_("Charges per inquilino"), {"items": [ReceivableUtilityInline]}),
        (_("Import storico"), {"items": ["Import storico"]}),
        (_("Note"), {"items": ["Note"]}),
    )


# ---------------------------------------------------------------------------
# UtilityChargeLine (standalone)
# ---------------------------------------------------------------------------


@admin.register(UtilityChargeLine)
class UtilityChargeLineAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 600
    list_display = (
        "receivable", "voce", "importo",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("voce",)
    list_select_related = ("receivable__assignment__tenant", "receivable__utility_period")
    autocomplete_fields = ("receivable",)
    ordering = ("receivable__utility_period__periodo_da", "voce")
    search_fields = ("receivable__assignment__tenant__nominativo",)
    advanced_search_fields = (
        ("voce", "receivable__assignment__tenant__nominativo__icontains:inquilino"),
        ("receivable__utility_period:periodo utenze",),
        ("receivable__competenza_da__range", "receivable__competenza_da__gte:competenza ≥",
         "receivable__competenza_da__lte:competenza ≤"),
        ("importo__gte:importo ≥", "importo__lte:importo ≤"),
    )

    def lookup_allowed(self, lookup, value, request):
        # Whitelist lookup attraverso FK profonde usati in advanced_search_fields.
        if lookup in {
            "receivable__assignment__tenant__nominativo__icontains",
            "receivable__utility_period",
            "receivable__competenza_da__range",
            "receivable__competenza_da__gte",
            "receivable__competenza_da__lte",
        }:
            return True
        return super().lookup_allowed(lookup, value, request)
    fieldsets = (
        ("Riga", {
            "fields": ("receivable", "voce", "importo", "dettaglio"),
        }),
    )


# ---------------------------------------------------------------------------
# TenantCondominioRate
# ---------------------------------------------------------------------------


@admin.register(TenantCondominioRate)
class TenantCondominioRateAdmin(ModalEditMixin, JumboModelAdmin):
    from .admin_inlines import TenantCondominioRateForm  # noqa: PLC0415
    form = TenantCondominioRateForm
    modal_edit_width = 700
    list_display = (
        "contract", "valid_from", "valid_to", "importo_mensile",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_select_related = ("contract",)
    ordering = ("-valid_from",)
    fieldsets = (
        ("Quota a carico inquilini", {
            "fields": ("contract", "valid_from", "valid_to", "importo_mensile", "note"),
        }),
    )
