# TODO: migrare a jmb.jadmin (admin-tabs, ajax-inlines, modal-edit) quando il pacchetto sarà disponibile
"""
Admin Django per l'app properties.
Gestisce proprietari, quote di proprietà, conti bancari,
stanze, contratto e assegnazioni stanze.
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from jmb.jadmin import JumboModelAdmin, ModalEditMixin

from .models import (
    Contract,
    OwnerBankAccount,
    OwnerProfile,
    OwnershipShare,
    Room,
    RoomAssignment,
    TenantProfile,
)


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------


class OwnershipShareInline(admin.TabularInline):
    """Quote di proprietà in linea nel profilo del proprietario."""

    model = OwnershipShare
    extra = 0
    fields = ("valid_from", "valid_to", "quota")
    ordering = ("-valid_from",)


class OwnerBankAccountInline(admin.TabularInline):
    """Conti bancari in linea nel profilo del proprietario."""

    model = OwnerBankAccount
    extra = 0
    fields = ("banca", "intestatario", "iban", "attivo", "ordinamento")
    ordering = ("ordinamento", "banca")


class RoomAssignmentInlineForTenant(admin.TabularInline):
    """Assegnazioni stanza in linea nel profilo inquilino."""

    model = RoomAssignment
    extra = 0
    fields = ("room", "valid_from", "valid_to", "canone_mensile", "costo_cessione")
    autocomplete_fields = ("room",)
    ordering = ("-valid_from",)
    show_change_link = True


class RoomAssignmentInlineForRoom(admin.TabularInline):
    """Assegnazioni stanza in linea nella stanza."""

    model = RoomAssignment
    extra = 0
    fields = ("tenant", "valid_from", "valid_to", "canone_mensile")
    autocomplete_fields = ("tenant",)
    ordering = ("-valid_from",)
    show_change_link = True


# ---------------------------------------------------------------------------
# OwnerProfile
# ---------------------------------------------------------------------------


@admin.register(OwnerProfile)
class OwnerProfileAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 900
    list_display = (
        "nominativo", "codice_fiscale", "telefono", "user",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    search_fields = ("nominativo", "codice_fiscale", "user__username", "user__email")
    list_select_related = ("user",)
    inlines = (OwnershipShareInline, OwnerBankAccountInline)
    fieldsets = (
        ("Anagrafica", {
            "fields": ("user", "nominativo", "codice_fiscale", "telefono"),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# OwnershipShare
# ---------------------------------------------------------------------------


@admin.register(OwnershipShare)
class OwnershipShareAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 700
    list_display = (
        "owner", "valid_from", "valid_to", "quota",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("owner",)
    list_select_related = ("owner",)
    search_fields = ("owner__nominativo",)
    autocomplete_fields = ("owner",)
    ordering = ("-valid_from", "owner__nominativo")


# ---------------------------------------------------------------------------
# OwnerBankAccount
# ---------------------------------------------------------------------------


@admin.register(OwnerBankAccount)
class OwnerBankAccountAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 800
    list_display = (
        "owner", "banca", "iban", "attivo", "ordinamento",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("attivo", "owner")
    list_select_related = ("owner",)
    search_fields = ("owner__nominativo", "banca", "iban", "intestatario")
    autocomplete_fields = ("owner",)
    ordering = ("owner__nominativo", "ordinamento", "banca")


# ---------------------------------------------------------------------------
# TenantProfile
# ---------------------------------------------------------------------------


@admin.register(TenantProfile)
class TenantProfileAdmin(ModalEditMixin, JumboModelAdmin):
    # 1100 (era 900): l'inline assegnazioni ha una colonna in più (costo cessione).
    modal_edit_width = 1100
    list_display = (
        "get_modal_edit_icon", "nominativo", "codice_fiscale",
        "giorno_pagamento_affitto", "ciclo_fatturazione",
        "deposito_versato", "deposito_restituito",
        "get_modal_delete_icon",
    )
    search_fields = ("nominativo", "codice_fiscale", "user__username", "user__email")
    list_filter = ("frequenza_conguagli", "ciclo_fatturazione")
    list_select_related = ("user",)
    inlines = (RoomAssignmentInlineForTenant,)
    fieldsets = (
        ("Anagrafica", {
            "fields": ("user", "nominativo", "codice_fiscale", "telefono", "email_alt"),
        }),
        ("Pagamenti", {
            "fields": (
                ("giorno_pagamento_affitto", "frequenza_conguagli"),
                "ciclo_fatturazione",
                "note_pagamento",
            ),
        }),
        ("Deposito", {
            "fields": (
                ("deposito_versato", "data_versamento_deposito"),
                ("deposito_restituito", "data_restituzione_deposito"),
            ),
            "description": (
                "Versando un valore in 'deposito versato' viene creato "
                "automaticamente un Receivable DEPOSITO legato al primo "
                "RoomAssignment del tenant. La restituzione (anche solo "
                "contabile, per saldare l'ultima rata) genera un secondo "
                "Receivable con importo negativo legato all'ultimo "
                "RoomAssignment."
            ),
        }),
    )
    readonly_fields = ("created_at", "updated_at")
    tabs = (
        ("Anagrafica", {"items": ["Anagrafica"]}),
        ("Pagamenti e deposito", {
            "items": ["Pagamenti", "Deposito"],
            "active": True,
        }),
        ("Assegnazione stanze", {"items": [RoomAssignmentInlineForTenant]}),
    )


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------


@admin.register(Room)
class RoomAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 700
    list_display = (
        "nome", "superficie_mq", "ordinamento",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    search_fields = ("nome",)
    ordering = ("ordinamento", "nome")
    inlines = (RoomAssignmentInlineForRoom,)
    fieldsets = (
        ("Stanza", {
            "fields": ("nome", "superficie_mq", "ordinamento", "foto"),
        }),
    )


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


@admin.register(Contract)
class ContractAdmin(ModalEditMixin, JumboModelAdmin):
    # AjaxInline definita in billing per le quote condominiali storicizzate.
    from billing.admin_inlines import TenantCondominioRateAjaxInline  # noqa: PLC0415

    modal_edit_width = 900
    list_display = (
        "nome", "data_decorrenza", "termine",
        "regime_fiscale", "asseverato", "durata_anni",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("regime_fiscale", "asseverato")
    search_fields = ("nome",)
    ordering = ("-data_decorrenza",)
    fieldsets = (
        ("Anagrafica", {
            "fields": ("nome", "data_stipula", "data_decorrenza", "durata_anni", "termine"),
        }),
        ("Fiscale", {
            "fields": ("regime_fiscale", "asseverato"),
        }),
        ("Convenzioni di pagamento", {
            "fields": ("default_pagatore_bollette",),
        }),
        ("Note", {
            "fields": ("note",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")
    tabs = (
        (_("Anagrafica"), {"items": [_("Anagrafica"), _("Fiscale"), _("Convenzioni di pagamento")]}),
        (_("Quote condominio inquilini"), {
            "items": [TenantCondominioRateAjaxInline],
        }),
        (_("Note"), {"items": [_("Note")]}),
    )


# ---------------------------------------------------------------------------
# RoomAssignment
# ---------------------------------------------------------------------------


@admin.register(RoomAssignment)
class RoomAssignmentAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 1200
    list_display = (
        "tenant", "room", "valid_from", "valid_to",
        "canone_mensile",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = (
        ("valid_to", admin.EmptyFieldListFilter),
    )
    search_fields = (
        "tenant__nominativo", "room__nome",
    )
    list_select_related = ("tenant", "room")
    autocomplete_fields = ("tenant", "room")
    ordering = ("-valid_from", "room__nome")
    fieldsets = (
        ("Periodo", {
            "fields": ("room", "tenant", "valid_from", "valid_to"),
        }),
        ("Economico", {
            "fields": ("canone_mensile",),
        }),
        ("Cessione", {
            "fields": ("costo_cessione", "data_atto_cessione"),
            "classes": ("collapse",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")
