"""
Admin Django per l'app properties.
Gestisce proprietari, quote di proprietà, conti bancari,
stanze, contratto e assegnazioni stanze.
"""
from io import StringIO

from django.contrib import admin, messages
from django.core.management import call_command
from django.utils import timezone
from django.utils.html import format_html

from jmb.jadmin import AjaxInline, ConstrainedModelForm, JumboModelAdmin, ModalEditMixin, register_inline

from .models import (
    Contract,
    DocumentShare,
    DocumentTemplate,
    GalleryArea,
    GalleryImage,
    OwnerBankAccount,
    OwnerProfile,
    OwnershipShare,
    Property,
    PropertyDocument,
    PropertyMembership,
    Room,
    RoomAssignment,
    ShareItem,
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


# RoomAssignment ha due contesti padre (tenant e room). jmb.jadmin ammette
# una sola AjaxInline per modello (il registry è chiave per classe): non è
# possibile registrarne due con fk_name diverso per lo stesso model. Il lato
# inquilino (elenco più consultato: storico stanze/canoni/cessioni di un
# tenant) diventa AjaxInline; il lato stanza resta TabularInline classico
# (vedi RoomAssignmentInlineForRoom più sotto) — stesso limite per
# GalleryImage (room XOR area), lasciato TabularInline su entrambi i lati.
class RoomAssignmentAjaxInlineForTenant(AjaxInline):
    """Assegnazioni stanza dell'inquilino, in tab (modal add/edit)."""

    model = RoomAssignment
    fk_name = "tenant"
    width = 1100
    list_display = (
        "room", "valid_from", "valid_to", "canone_mensile",
        "bank_account_affitto", "costo_cessione",
        "get_edit_icon_iframe", "get_delete_icon_iframe",
    )


register_inline(RoomAssignmentAjaxInlineForTenant)


class TenantDocumentForm(ConstrainedModelForm):
    class Meta:
        model = TenantDocument
        fields = "__all__"

    hidden_fields = ("tenant",)


class TenantDocumentAjaxInline(AjaxInline):
    """Documenti dell'inquilino, in tab (modal add/edit dei file).

    ``file_link`` è definito sul ``TenantDocumentAdmin`` sotto, non qui:
    ``ChildrenChangeList`` risolve le colonne di ``list_display`` sul
    ModelAdmin *registrato* per il modello figlio, non sull'istanza
    ``AjaxInline`` (altrimenti ``get_ordering_field`` cerca 'file_link' come
    campo del modello e va in ``FieldDoesNotExist``).
    """

    model = TenantDocument
    fk_name = "tenant"
    width = 700
    list_display = (
        "tipo", "descrizione", "data_scadenza", "generato", "file_link",
        "get_edit_icon_iframe", "get_delete_icon_iframe",
    )


register_inline(TenantDocumentAjaxInline)


@admin.register(TenantDocument)
class TenantDocumentAdmin(ModalEditMixin, JumboModelAdmin):
    form = TenantDocumentForm
    modal_edit_width = 700
    list_display = (
        "tenant", "tipo", "descrizione", "data_scadenza", "generato",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("tipo", "generato")
    list_select_related = ("tenant",)
    search_fields = ("tenant__nominativo", "descrizione")
    autocomplete_fields = ("tenant",)
    fieldsets = (
        ("Documento", {
            "fields": (
                "tenant", "tipo", "file", "descrizione", "data_scadenza",
            ),
        }),
    )
    readonly_fields = ("created_at", "updated_at", "generato", "caricato_da")

    @admin.display(description="file")
    def file_link(self, obj):
        if obj.file:
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">apri</a>', obj.file.url
            )
        return "—"


class PropertyDocumentForm(ConstrainedModelForm):
    class Meta:
        model = PropertyDocument
        fields = "__all__"

    hidden_fields = ("property",)


class PropertyDocumentAjaxInline(AjaxInline):
    """Documenti dell'immobile, in tab (modal add/edit dei file).

    ``file_link`` sta sul ``PropertyDocumentAdmin`` sotto, stesso motivo
    spiegato su ``TenantDocumentAjaxInline``.
    """

    model = PropertyDocument
    fk_name = "property"
    width = 700
    # ``contract`` in colonna: senza, un documento agganciato a un contratto
    # e uno generale sono indistinguibili in elenco, ed è esattamente lo
    # scambio che genera i doppioni.
    list_display = (
        "tipo", "descrizione", "contract", "data_scadenza", "visibile_inquilini",
        "file_link", "get_edit_icon_iframe", "get_delete_icon_iframe",
    )


register_inline(PropertyDocumentAjaxInline)


@admin.register(PropertyDocument)
class PropertyDocumentAdmin(ModalEditMixin, JumboModelAdmin):
    form = PropertyDocumentForm
    modal_edit_width = 700
    list_display = (
        "property", "tipo", "descrizione", "contract", "data_scadenza",
        "visibile_inquilini", "copia_di", "esponibile",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("tipo", "visibile_inquilini", "esponibile", "property")
    list_select_related = ("property",)
    search_fields = ("property__nome", "descrizione")
    autocomplete_fields = ("property",)
    # Non raw_id: i contratti sono pochi e con l'id nudo il campo sembra non
    # esserci. Un select con il nome del contratto si usa.
    fieldsets = (
        ("Documento", {
            "fields": (
                "property", "contract", "tipo", "file", "descrizione",
                "data_scadenza", "visibile_inquilini",
            ),
        }),
        ("Link di lettura", {
            "fields": ("copia_di", "esponibile"),
            "description": (
                "Una copia oscurata è la versione senza dati personali di un "
                "originale: sta fuori dagli elenchi ufficiali e serve solo "
                "ai link mandati a chi non ha un account."
            ),
        }),
    )
    readonly_fields = ("created_at", "updated_at", "caricato_da")

    @admin.display(description="file")
    def file_link(self, obj):
        if obj.file:
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">apri</a>', obj.file.url
            )
        return "—"


class RoomAssignmentInlineForRoom(admin.TabularInline):
    """Assegnazioni stanza in linea nella stanza."""

    model = RoomAssignment
    extra = 0
    fields = ("tenant", "valid_from", "valid_to", "canone_mensile")
    autocomplete_fields = ("tenant",)
    ordering = ("-valid_from",)
    show_change_link = True


class GalleryImageInlineForRoom(admin.TabularInline):
    """Foto galleria in linea nella stanza."""

    model = GalleryImage
    fk_name = "room"
    extra = 0
    fields = ("image", "didascalia", "ordinamento")
    ordering = ("ordinamento", "id")


class GalleryImageInlineForArea(admin.TabularInline):
    """Foto in linea nell'ambiente comune."""

    model = GalleryImage
    fk_name = "area"
    extra = 0
    fields = ("image", "didascalia", "ordinamento")
    ordering = ("ordinamento", "id")


class GalleryAreaInlineForProperty(admin.TabularInline):
    """Ambienti comuni in linea nell'immobile."""

    model = GalleryArea
    extra = 0
    fields = ("nome", "colore", "ordinamento", "pubblica")
    ordering = ("ordinamento", "nome")
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
        ("Nascita e residenza", {
            "fields": (
                ("cognome", "nome"),
                ("data_nascita", "comune_nascita", "provincia_nascita"),
                "cittadinanza",
                "residenza_via",
                ("residenza_comune", "residenza_provincia", "residenza_cap"),
            ),
            "description": (
                "Compaiono nell'atto di subentro (tutti i comproprietari) e, "
                "per il firmatario, nella comunicazione di cessione di fabbricato."
            ),
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
        "property", "owner", "valid_from", "valid_to", "quota",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("property", "owner")
    list_select_related = ("property", "owner")
    search_fields = ("owner__nominativo", "property__nome")
    autocomplete_fields = ("property", "owner")
    ordering = ("property__nome", "-valid_from", "owner__nominativo")


# ---------------------------------------------------------------------------
# OwnerBankAccount
# ---------------------------------------------------------------------------


@admin.register(OwnerBankAccount)
class OwnerBankAccountAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 800
    list_display = (
        "owner", "banca", "iban", "attivo", "immobili", "ordinamento",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("attivo", "owner", "properties")
    list_select_related = ("owner",)
    search_fields = ("owner__nominativo", "banca", "iban", "intestatario")
    autocomplete_fields = ("owner",)
    # Niente `filter_horizontal` su `properties`: nella modal di
    # `ModalEditMixin` il form arriva via AJAX a DOMContentLoaded già passato,
    # SelectFilter non si inizializza e il campo degrada a multi-select — che
    # comparirebbe a due facce a seconda di come si apre la scheda. Il
    # multi-select nativo è coerente ovunque e con pochi immobili basta.
    ordering = ("owner__nominativo", "ordinamento", "banca")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("properties")

    @admin.display(description="immobili")
    def immobili(self, obj):
        return ", ".join(p.nome for p in obj.properties.all()) or "—"


# ---------------------------------------------------------------------------
# TenantProfile
# ---------------------------------------------------------------------------


class TenantAttivoFilter(admin.SimpleListFilter):
    """Inquilini con una ``RoomAssignment`` in corso **oggi**.

    Delega a ``TenantProfileQuerySet.attivi()``/``.usciti()`` (vedi
    ``properties.models.tenant.assegnazione_in_corso_q``): è il selettore
    condiviso fra API, admin e comandi, con ``valid_to`` **escluso**
    (``valid_to__gt``) — la stessa regola di ``billing.calc.posizione``, da
    cui discende il badge "ex inquilino". Non duplicare la query qui: se la
    regola cambia, cambia in un posto solo.
    """

    title = "attivo oggi"
    parameter_name = "attivo"

    def lookups(self, request, model_admin):
        return (("si", "Attivi"), ("no", "Non attivi"))

    def queryset(self, request, queryset):
        oggi = timezone.localdate()
        if self.value() == "si":
            return queryset.attivi(oggi)
        if self.value() == "no":
            return queryset.usciti(oggi)
        return queryset


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
    list_filter = ("frequenza_conguagli", "ciclo_fatturazione", TenantAttivoFilter)
    list_select_related = ("user", "property")
    advanced_search_fields = (
        ("nominativo__icontains", "codice_fiscale__icontains", "telefono__icontains"),
        ("property", "ciclo_fatturazione", "frequenza_conguagli"),
        ("giorno_pagamento_affitto__gte:giorno pagamento ≥",
         "giorno_pagamento_affitto__lte:giorno pagamento ≤"),
        ("deposito_versato__gte:deposito ≥", "deposito_versato__lte:deposito ≤",
         "data_versamento_deposito__range:versamento tra"),
        ("data_restituzione_prevista__isnull:senza restituzione prevista",
         "data_restituzione_prevista__range:restituzione tra"),
        ("documento_tipo",),
    )
    advanced_search_autocomplete_fields = ("property",)
    fieldsets = (
        ("Anagrafica", {
            "fields": ("user", "nominativo", "codice_fiscale", "telefono", "email_alt"),
        }),
        ("Nascita e residenza", {
            "fields": (
                ("cognome", "nome"),
                ("data_nascita", "comune_nascita", "provincia_nascita"),
                "cittadinanza",
                "residenza_via",
                ("residenza_comune", "residenza_provincia", "residenza_cap"),
            ),
            "description": (
                "Servono ai documenti generati (atto di subentro, cessione di "
                "fabbricato). 'Cognome' e 'nome' stanno accanto a 'nominativo', "
                "che resta il campo usato ovunque nell'applicazione."
            ),
        }),
        ("Documento identita", {
            "fields": (
                ("documento_tipo", "documento_numero"),
                ("documento_autorita", "documento_data_rilascio"),
            ),
            "description": (
                "Estremi richiesti dalla comunicazione di cessione di "
                "fabbricato (art. 12 D.L. 59/1978) per il cessionario."
            ),
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
        # Attenzione: le chiavi qui devono coincidere alla lettera con i titoli
        # dei fieldset e non essere traducibili, altrimenti jmb.jadmin solleva
        # MissingFieldsetException.
        ("Anagrafica", {
            "items": ["Anagrafica", "Nascita e residenza", "Documento identita"],
        }),
        ("Pagamenti e deposito", {
            "items": ["Pagamenti", "Deposito"],
            "active": True,
        }),
        ("Assegnazione stanze", {"items": [RoomAssignmentAjaxInlineForTenant]}),
        ("Documenti", {"items": [TenantDocumentAjaxInline]}),
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


class PropertyMembershipInline(admin.TabularInline):
    model = PropertyMembership
    fk_name = "property"
    extra = 0
    fields = ("user", "ruolo", "invitato_da")
    autocomplete_fields = ("user", "invitato_da")


@admin.register(Property)
class PropertyAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 800
    list_display = (
        "nome", "indirizzo", "pubblica", "slug", "bank_account_utenze",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("pubblica",)
    search_fields = ("nome", "indirizzo", "slug")
    prepopulated_fields = {"slug": ("nome",)}
    autocomplete_fields = (
        "bank_account_utenze", "owner_anticipa_cessioni", "owner_firmatario",
    )
    inlines = (
        PropertyMembershipInline,
        GalleryAreaInlineForProperty,
    )
    fieldsets = (
        ("Immobile", {
            "fields": (
                "nome", "tipo_gestione", "indirizzo", "bank_account_utenze",
                "owner_anticipa_cessioni", "owner_firmatario",
            ),
        }),
        ("Indirizzo strutturato", {
            "fields": (
                ("via", "civico"),
                ("cap", "comune", "provincia"),
                ("piano", "scala", "interno"),
                ("vani", "accessori", "ingressi"),
            ),
            "description": (
                "Una casella per ciascun dato richiesto dalla comunicazione di "
                "cessione di fabbricato. Il campo 'indirizzo' qui sopra resta la "
                "stringa mostrata nelle email e nella galleria: i due non si "
                "aggiornano a vicenda."
            ),
        }),
        ("Galleria pubblica", {
            "fields": (
                ("pubblica", "slug"),
                ("foto_hero", "foto_planimetria", "foto_mappa"),
                "testi_pubblici",
            ),
            "description": (
                "Se 'pubblica' è attiva, la galleria è raggiungibile senza login "
                "su /g/&lt;slug&gt;. 'testi pubblici' è un JSON con hero/facts/posizione."
            ),
        }),
    )
    tabs = (
        ("Immobile", {"items": ["Immobile", "Indirizzo strutturato"]}),
        ("Membri", {"items": [PropertyMembershipInline]}),
        ("Ambienti comuni", {"items": [GalleryAreaInlineForProperty]}),
        ("Documenti", {"items": [PropertyDocumentAjaxInline]}),
        ("Galleria pubblica", {"items": ["Galleria pubblica"]}),
    )


@admin.register(PropertyMembership)
class PropertyMembershipAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 700
    list_display = (
        "property", "user", "ruolo", "invitato_da",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("property", "ruolo")
    list_select_related = ("property", "user", "invitato_da")
    search_fields = ("property__nome", "user__username", "user__email")
    autocomplete_fields = ("property", "user", "invitato_da")


@admin.register(Room)
class RoomAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 800
    list_display = (
        "nome", "property", "superficie_mq", "prezzo_mensile",
        "disponibile", "pubblica", "ordinamento",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    search_fields = ("nome",)
    list_filter = ("property", "disponibile", "pubblica")
    autocomplete_fields = ("property",)
    ordering = ("ordinamento", "nome")
    # GalleryImage e RoomAssignment restano TabularInline classici (vedi nota
    # sopra su RoomAssignmentAjaxInlineForTenant): entrambi hanno un secondo
    # contesto padre che occupa già l'unica AjaxInline ammessa per modello.
    inlines = (GalleryImageInlineForRoom, RoomAssignmentInlineForRoom)
    fieldsets = (
        ("Stanza", {
            "fields": ("property", "nome", "superficie_mq", "ordinamento", "foto"),
        }),
        ("Galleria pubblica", {
            "fields": (
                ("pubblica", "disponibile"),
                ("prezzo_mensile", "libera_dal"),
                "colore",
                "descrizione",
            ),
        }),
    )
    tabs = (
        ("Stanza", {"items": ["Stanza"]}),
        ("Galleria pubblica", {"items": ["Galleria pubblica"]}),
        ("Foto", {"items": [GalleryImageInlineForRoom]}),
        ("Assegnazioni", {"items": [RoomAssignmentInlineForRoom]}),
    )


@admin.register(GalleryArea)
class GalleryAreaAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 800
    list_display = (
        "nome", "property", "ordinamento", "pubblica",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("property", "pubblica")
    search_fields = ("nome",)
    autocomplete_fields = ("property",)
    ordering = ("property", "ordinamento", "nome")
    inlines = (GalleryImageInlineForArea,)
    fieldsets = (
        ("Ambiente comune", {
            "fields": ("property", "nome", "colore", "ordinamento", "pubblica", "descrizione"),
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
            "fields": (
                "nome", "data_stipula", "data_decorrenza",
                ("durata_anni", "durata_rinnovo_anni"), "termine",
            ),
        }),
        ("Registrazione", {
            "fields": (
                ("ufficio_registrazione", "data_registrazione"),
                ("numero_registrazione", "serie_registrazione"),
                "codice_identificativo",
            ),
            "description": (
                "Estremi citati nelle premesse dell'atto di subentro. Finora "
                "esistevano solo dentro la ricevuta di registrazione caricata."
            ),
        }),
        ("Fiscale", {
            "fields": ("regime_fiscale", "asseverato"),
        }),
        ("Convenzioni di pagamento", {
            "fields": ("default_pagatore_bollette",),
        }),
        ("Note interne", {
            "fields": ("note",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")
    tabs = (
        # Chiavi non traducibili (stringhe semplici): jmb.jadmin confronta
        # gettext(nome_fieldset) col nome scritto in items, e "Note" da solo
        # collide con una entry del catalogo di traduzione django (→ "Nota"),
        # sollevando MissingFieldsetException — da qui "Note interne".
        ("Anagrafica", {
            "items": [
                "Anagrafica", "Registrazione", "Fiscale",
                "Convenzioni di pagamento",
            ],
        }),
        ("Quote condominio inquilini", {
            "items": [TenantCondominioRateAjaxInline],
        }),
        ("Note interne", {"items": ["Note interne"]}),
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
    advanced_search_fields = (
        ("tenant", "room",
         "room__property__nome__icontains:immobile"),
        ("valid_from__gte:dal", "valid_from__lte:al",
         "valid_to__isnull:occupazione chiusa"),
        ("valid_to__gte:fine dal", "valid_to__lte:fine al"),
        ("canone_mensile__gte:canone min", "canone_mensile__lte:canone max"),
        ("costo_cessione__isnull:senza costo cessione",
         "data_atto_cessione__gte:atto dal", "data_atto_cessione__lte:atto al"),
    )
    advanced_search_autocomplete_fields = ("tenant", "room")
    list_select_related = ("tenant", "room")
    autocomplete_fields = ("tenant", "room", "bank_account_affitto", "subentra_a")
    raw_id_fields = ("contract",)
    ordering = ("-valid_from", "room__nome")

    def get_form(self, request, obj=None, **kwargs):
        """Changelist/change_form standalone: form invariato. Aperto invece
        dall'AjaxInline del tenant (querystring ``?tenant=<pk>``, vedi
        ``RoomAssignmentAjaxInlineForTenant``): nasconde quel campo, già
        impostato dal parent — pattern "ConstrainedModelForm + get_form()
        dinamico" della skill jmb-jadmin, che preserva gli altri widget
        (autocomplete room/bank_account_affitto/subentra_a) costruiti da
        ``super().get_form()``.
        """
        base_form = super().get_form(request, obj, **kwargs)
        hidden_fields = [key for key in request.GET if not key.startswith("_")]
        if not hidden_fields:
            return base_form
        return type(
            "RoomAssignmentAjaxForm",
            (ConstrainedModelForm, base_form),
            {"hidden_fields": tuple(hidden_fields)},
        )
    fieldsets = (
        ("Periodo", {
            "fields": ("room", "tenant", "valid_from", "valid_to"),
        }),
        ("Economico", {
            "fields": ("canone_mensile", "bank_account_affitto"),
        }),
        ("Cessione", {
            "fields": ("costo_cessione", "data_atto_cessione", "subentra_a"),
            "classes": ("collapse",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# DocumentTemplate
# ---------------------------------------------------------------------------


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 1100
    list_display = (
        "property", "codice", "nome",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("codice",)
    list_select_related = ("property",)
    search_fields = ("nome", "property__nome")
    fieldsets = (
        ("Modello", {
            "fields": ("property", "codice", "nome"),
        }),
        ("Corpo", {
            "fields": ("corpo_html",),
            "description": (
                "Documento HTML completo, CSS incluso. I segnaposto "
                "{{chiave}} vengono sostituiti alla generazione: l'elenco "
                "di quelli disponibili è nella pagina 'Modelli documenti' "
                "dell'immobile."
            ),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# Link di lettura
# ---------------------------------------------------------------------------


class ShareItemInline(admin.TabularInline):
    """Voci del pacchetto. ``corpo_html`` non c'è: è cache del markdown,
    rigenerata a ogni salvataggio."""

    model = ShareItem
    extra = 0
    fields = ("ordine", "titolo", "documento", "corpo_md")
    ordering = ("ordine", "id")


@admin.register(DocumentShare)
class DocumentShareAdmin(admin.ModelAdmin):
    """Il link si compone dal frontend; qui si guarda e si revoca."""

    list_display = (
        "destinatario", "property", "attivo", "visite", "ultima_visita",
        "created_at",
    )
    list_filter = ("attivo", "property")
    search_fields = ("destinatario", "token")
    readonly_fields = ("token", "visite", "ultima_visita", "created_at", "updated_at")
    autocomplete_fields = ("property",)
    inlines = [ShareItemInline]
