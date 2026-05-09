# TODO: migrare a jmb.jadmin (admin-tabs, ajax-inlines, modal-edit) quando il pacchetto sarà disponibile
"""
Admin Django per l'app accounting.
Gestisce il partitario ufficiale proprietari, chiusure conti,
prestiti bilaterali e regole di trattenuta.
"""
from django.contrib import admin
from django.urls import path

from jmb.jadmin import JumboModelAdmin, ModalEditMixin

from .admin_views import genera_settlement_view
from .models import (
    InterOwnerEntry,
    InterOwnerLoan,
    OwnerLedgerEntry,
    OwnerSettlement,
    WithholdingRule,
)


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------


class InterOwnerEntryInline(admin.TabularInline):
    """Voci bilaterali in linea nel prestito tra proprietari."""

    model = InterOwnerEntry
    extra = 0
    fields = ("data", "importo", "descrizione", "riferimento_expense")
    autocomplete_fields = ("riferimento_expense",)
    ordering = ("-data",)


# ---------------------------------------------------------------------------
# OwnerLedgerEntry
# ---------------------------------------------------------------------------


@admin.register(OwnerLedgerEntry)
class OwnerLedgerEntryAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 800
    list_display = (
        "data", "owner", "tipo", "importo", "descrizione",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("owner", "tipo")
    search_fields = ("descrizione", "owner__nominativo")
    list_select_related = ("owner",)
    autocomplete_fields = ("owner", "riferimento_receivable", "riferimento_expense")
    date_hierarchy = "data"
    ordering = ("-data", "owner__nominativo")
    fieldsets = (
        ("Voce", {
            "fields": ("data", "owner", "tipo", "importo", "descrizione"),
        }),
        ("Riferimenti", {
            "fields": ("riferimento_receivable", "riferimento_expense"),
            "classes": ("collapse",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# OwnerSettlement
# ---------------------------------------------------------------------------


@admin.register(OwnerSettlement)
class OwnerSettlementAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 800
    list_display = (
        "data", "periodo_da", "periodo_a", "descrizione",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    ordering = ("-data",)
    change_list_template = "admin/accounting/ownersettlement/change_list.html"
    fieldsets = (
        ("Periodo", {
            "fields": ("data", "descrizione", "periodo_da", "periodo_a"),
        }),
        ("Snapshot saldi", {
            "fields": ("snapshot",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")

    def get_urls(self):
        custom = [
            path(
                "genera-settlement/",
                self.admin_site.admin_view(genera_settlement_view),
                name="accounting_ownersettlement_genera",
            ),
        ]
        return custom + super().get_urls()


# ---------------------------------------------------------------------------
# InterOwnerLoan
# ---------------------------------------------------------------------------


@admin.register(InterOwnerLoan)
class InterOwnerLoanAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 900
    list_display = (
        "owner_da", "owner_a", "data_apertura", "importo_originale", "chiuso",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("chiuso",)
    search_fields = ("descrizione", "owner_da__nominativo", "owner_a__nominativo")
    list_select_related = ("owner_da", "owner_a")
    autocomplete_fields = ("owner_da", "owner_a")
    ordering = ("-data_apertura",)
    inlines = (InterOwnerEntryInline,)
    fieldsets = (
        ("Prestito", {
            "fields": ("owner_da", "owner_a", "data_apertura", "importo_originale", "chiuso"),
        }),
        ("Descrizione", {
            "fields": ("descrizione",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# InterOwnerEntry
# ---------------------------------------------------------------------------


@admin.register(InterOwnerEntry)
class InterOwnerEntryAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 800
    list_display = (
        "data", "owner_da", "owner_a", "importo", "descrizione",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("owner_da", "owner_a")
    search_fields = ("descrizione", "owner_da__nominativo", "owner_a__nominativo")
    list_select_related = ("owner_da", "owner_a", "riferimento_loan")
    autocomplete_fields = ("owner_da", "owner_a", "riferimento_loan", "riferimento_expense")
    date_hierarchy = "data"
    ordering = ("-data",)
    fieldsets = (
        ("Voce", {
            "fields": ("data", "owner_da", "owner_a", "importo", "descrizione"),
        }),
        ("Riferimenti", {
            "fields": ("riferimento_loan", "riferimento_expense"),
            "classes": ("collapse",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# WithholdingRule
# ---------------------------------------------------------------------------


@admin.register(WithholdingRule)
class WithholdingRuleAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 800
    list_display = (
        "owner_da", "owner_a", "importo_mensile", "attiva", "valid_from", "valid_to",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("attiva",)
    search_fields = ("descrizione", "owner_da__nominativo", "owner_a__nominativo")
    list_select_related = ("owner_da", "owner_a")
    autocomplete_fields = ("owner_da", "owner_a")
    ordering = ("-valid_from",)
    fieldsets = (
        ("Regola", {
            "fields": ("owner_da", "owner_a", "importo_mensile", "descrizione", "attiva"),
        }),
        ("Validità", {
            "fields": ("valid_from", "valid_to"),
        }),
    )
    readonly_fields = ("created_at", "updated_at")
