# TODO: migrare a jmb.jadmin (admin-tabs, ajax-inlines, modal-edit) quando il pacchetto sarà disponibile
"""
Admin Django per l'app properties.
Gestisce proprietari, quote di proprietà, conti bancari,
stanze, contratto e assegnazioni stanze.
"""
from io import StringIO

from django.contrib import admin, messages
from django.core.management import call_command
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from jmb.jadmin import JumboModelAdmin, ModalEditMixin

from .models import (
    Contract,
    OwnerBankAccount,
    OwnerProfile,
    OwnershipShare,
    Property,
    Room,
    RoomAssignment,
    TenantDocument,
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
    fields = (
        "room", "valid_from", "valid_to", "canone_mensile",
        "bank_account_affitto", "costo_cessione",
    )
    autocomplete_fields = ("room", "bank_account_affitto")
    ordering = ("-valid_from",)
    show_change_link = True


class TenantDocumentInline(admin.TabularInline):
    """Documenti dell'inquilino in linea nel profilo."""

    model = TenantDocument
    extra = 0
    fields = ("tipo", "file", "descrizione", "data_scadenza")
    ordering = ("tipo", "-created_at")


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
        "get_modal_edit_icon", "nominativo", "periodo_occupazione",
        "giorno_pagamento_affitto", "ciclo_fatturazione",
        "deposito_versato", "deposito_da_restituire",
        "get_modal_delete_icon",
    )
    search_fields = ("nominativo", "user__username", "user__email")
    list_filter = ("frequenza_conguagli", "ciclo_fatturazione")
    list_select_related = ("user",)
    inlines = (RoomAssignmentInlineForTenant, TenantDocumentInline)
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
                ("deposito_da_restituire", "data_restituzione_prevista"),
            ),
            "description": (
                "Versando un valore in 'deposito versato' viene creato "
                "automaticamente un Receivable DEPOSITO legato al primo "
                "RoomAssignment del tenant. Valorizzando 'data restituzione "
                "prevista' viene generato un secondo Receivable con importo "
                "negativo (pari a 'deposito da restituire', o al versato se "
                "vuoto) legato all'ultimo RoomAssignment."
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
        ("Documenti", {"items": [TenantDocumentInline]}),
    )
    actions = ["invia_invito", "salda_con_resti_dry_run", "salda_con_resti_apply"]

    @admin.action(description="Invia email di invito")
    def invia_invito(self, request, queryset):
        """Invia a ciascun inquilino selezionato l'email di benvenuto con il
        link per impostare la password (vedi ``accounts.inviti``)."""
        from accounts.inviti import invia_invito_inquilino

        inviati, errori = 0, 0
        for tenant in queryset:
            esito = invia_invito_inquilino(tenant, request=request)
            if esito["esito"] == "inviato":
                inviati += 1
                self.message_user(
                    request,
                    f"Invito inviato a {tenant.nominativo} ({esito['email']}).",
                    level=messages.SUCCESS,
                )
            else:
                errori += 1
                self.message_user(
                    request,
                    f"{tenant.nominativo}: {esito['errore']}",
                    level=messages.ERROR,
                )
        if inviati and not errori:
            self.message_user(
                request, f"{inviati} invito/i inviato/i.", level=messages.INFO
            )

    def _run_salda_con_resti(self, request, queryset, *, apply: bool):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Seleziona un solo inquilino per volta.",
                level=messages.ERROR,
            )
            return
        tenant = queryset.first()
        out = StringIO()
        kwargs = {"tenant": tenant.id, "stdout": out}
        if apply:
            kwargs["apply"] = True
        try:
            call_command("salda_con_resti", **kwargs)
        except Exception as e:  # noqa: BLE001
            self.message_user(
                request, f"Errore: {e}", level=messages.ERROR
            )
            return
        self.message_user(
            request,
            format_html(
                "<pre style='white-space:pre-wrap;margin:0'>{}</pre>",
                out.getvalue(),
            ),
            level=messages.SUCCESS if apply else messages.INFO,
        )

    @admin.action(description="Salda con resti (dry-run)")
    def salda_con_resti_dry_run(self, request, queryset):
        """Mostra il piano di allocations FIFO dei resti bonifici sugli
        scoperti dell'inquilino. Non scrive nel DB."""
        self._run_salda_con_resti(request, queryset, apply=False)

    @admin.action(description="Salda con resti — APPLY (scrive nel DB)")
    def salda_con_resti_apply(self, request, queryset):
        """Esegue le allocations FIFO dei resti bonifici sugli scoperti
        dell'inquilino. Scrive nel DB."""
        self._run_salda_con_resti(request, queryset, apply=True)


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------


@admin.register(Property)
class PropertyAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 700
    list_display = (
        "nome", "indirizzo", "bank_account_utenze",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    search_fields = ("nome", "indirizzo")
    autocomplete_fields = ("bank_account_utenze",)
    fieldsets = (
        ("Immobile", {
            "fields": ("nome", "indirizzo", "bank_account_utenze"),
        }),
    )


@admin.register(Room)
class RoomAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 700
    list_display = (
        "nome", "property", "superficie_mq", "ordinamento",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    search_fields = ("nome",)
    list_filter = ("property",)
    autocomplete_fields = ("property",)
    ordering = ("ordinamento", "nome")
    inlines = (RoomAssignmentInlineForRoom,)
    fieldsets = (
        ("Stanza", {
            "fields": ("property", "nome", "superficie_mq", "ordinamento", "foto"),
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
    autocomplete_fields = ("tenant", "room", "bank_account_affitto")
    ordering = ("-valid_from", "room__nome")
    fieldsets = (
        ("Periodo", {
            "fields": ("room", "tenant", "valid_from", "valid_to"),
        }),
        ("Economico", {
            "fields": ("canone_mensile", "bank_account_affitto"),
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
