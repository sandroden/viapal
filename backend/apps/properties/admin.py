# TODO: migrare a jmb.jadmin (admin-tabs, ajax-inlines, modal-edit) quando il pacchetto sarà disponibile
"""
Admin Django per l'app properties.
Gestisce proprietari, quote di proprietà, conti bancari,
stanze, contratto e assegnazioni stanze.
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from jmb.jadmin import JumboModelAdmin

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
    """Assegnazioni stanza in linea nel profilo inquilino (sola lettura)."""

    model = RoomAssignment
    extra = 0
    fields = ("room", "valid_from", "valid_to", "canone_mensile")
    readonly_fields = ("room", "valid_from", "valid_to", "canone_mensile")
    ordering = ("-valid_from",)
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


class RoomAssignmentInlineForRoom(admin.TabularInline):
    """Assegnazioni stanza in linea nella stanza (sola lettura)."""

    model = RoomAssignment
    extra = 0
    fields = ("tenant", "valid_from", "valid_to", "canone_mensile")
    readonly_fields = ("tenant", "valid_from", "valid_to", "canone_mensile")
    ordering = ("-valid_from",)
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# OwnerProfile
# ---------------------------------------------------------------------------


@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):
    list_display = ("nominativo", "codice_fiscale", "telefono", "user")
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
class OwnershipShareAdmin(admin.ModelAdmin):
    list_display = ("owner", "valid_from", "valid_to", "quota")
    list_filter = ("owner",)
    list_select_related = ("owner",)
    search_fields = ("owner__nominativo",)
    autocomplete_fields = ("owner",)
    ordering = ("-valid_from", "owner__nominativo")


# ---------------------------------------------------------------------------
# OwnerBankAccount
# ---------------------------------------------------------------------------


@admin.register(OwnerBankAccount)
class OwnerBankAccountAdmin(admin.ModelAdmin):
    list_display = ("owner", "banca", "iban", "attivo", "ordinamento")
    list_filter = ("attivo", "owner")
    list_select_related = ("owner",)
    search_fields = ("owner__nominativo", "banca", "iban", "intestatario")
    autocomplete_fields = ("owner",)
    ordering = ("owner__nominativo", "ordinamento", "banca")


# ---------------------------------------------------------------------------
# TenantProfile
# ---------------------------------------------------------------------------


@admin.register(TenantProfile)
class TenantProfileAdmin(admin.ModelAdmin):
    list_display = (
        "nominativo", "codice_fiscale", "telefono",
        "giorno_pagamento_affitto", "frequenza_conguagli",
    )
    search_fields = ("nominativo", "codice_fiscale", "user__username", "user__email")
    list_filter = ("frequenza_conguagli",)
    list_select_related = ("user",)
    inlines = (RoomAssignmentInlineForTenant,)
    fieldsets = (
        ("Anagrafica", {
            "fields": ("user", "nominativo", "codice_fiscale", "telefono", "email_alt"),
        }),
        ("Pagamenti", {
            "fields": ("giorno_pagamento_affitto", "frequenza_conguagli", "note_pagamento"),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("nome", "superficie_mq", "ordinamento")
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
class ContractAdmin(JumboModelAdmin):
    # AjaxInline definita in billing per le quote condominiali storicizzate.
    from billing.admin_inlines import TenantCondominioRateAjaxInline  # noqa: PLC0415

    list_display = ("data_stipula", "data_decorrenza", "regime_fiscale", "asseverato", "durata_anni")
    list_filter = ("regime_fiscale", "asseverato")
    ordering = ("-data_decorrenza",)
    fieldsets = (
        ("Anagrafica", {
            "fields": ("data_stipula", "data_decorrenza", "durata_anni"),
        }),
        ("Fiscale", {
            "fields": ("regime_fiscale", "asseverato"),
        }),
        ("Note", {
            "fields": ("note",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")
    tabs = (
        (_("Anagrafica"), {"items": [_("Anagrafica"), _("Fiscale")]}),
        (_("Quote condominio inquilini"), {
            "items": [TenantCondominioRateAjaxInline],
        }),
        (_("Note"), {"items": [_("Note")]}),
    )


# ---------------------------------------------------------------------------
# RoomAssignment
# ---------------------------------------------------------------------------


@admin.register(RoomAssignment)
class RoomAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "tenant", "room", "valid_from", "valid_to",
        "canone_mensile", "deposito_versato",
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
            "fields": ("canone_mensile", "deposito_versato", "deposito_restituito", "data_restituzione_deposito"),
        }),
        ("Cessione", {
            "fields": ("data_atto_cessione",),
            "classes": ("collapse",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")
