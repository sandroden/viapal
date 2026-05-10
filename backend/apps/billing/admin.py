"""
Admin Django per l'app billing.
Gestisce: addebiti inquilini (Receivable, con filtro per causale: affitto/utenze/extra),
fornitori, categorie spese, spese, bollette, utenze e transazioni bancarie.
"""
from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

_ALLOC_SOGLIA = Decimal("1.00")

from jmb.jadmin import JumboActionForm, JumboModelAdmin, ModalEditMixin

from properties.models import OwnerProfile, TenantProfile

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


class ReceivableAllocationsInline(admin.TabularInline):
    """Allocazioni inline (read-only) sul Receivable: quali BankTransaction
    lo coprono, con data, descrizione e importo allocato.

    La modifica/eliminazione si fa dal lato BankTransaction (per coerenza con
    il modello mentale "il bonifico copre N addebiti"). Qui mostriamo solo
    la vista a specchio.
    """

    model = BankTransactionAllocation
    fk_name = "receivable"
    extra = 0
    fields = ("bt_data", "bt_descrizione", "importo")
    readonly_fields = ("bt_data", "bt_descrizione", "importo")
    can_delete = False
    verbose_name = "transazione che paga"
    verbose_name_plural = "transazioni che pagano"

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("bank_transaction__owner_account")

    @admin.display(description="data BT")
    def bt_data(self, obj):
        return obj.bank_transaction.data if obj.bank_transaction_id else "—"

    @admin.display(description="descrizione BT")
    def bt_descrizione(self, obj):
        if not obj.bank_transaction_id:
            return "—"
        bt = obj.bank_transaction
        descr = (bt.descrizione or "")[:120]
        return f"{descr} — {bt.importo}€ ({bt.owner_account.banca})"


class BankTransactionAllocationInline(admin.TabularInline):
    """Allocazioni inline su BankTransaction (bonifico → addebiti).

    Aggiungere una riga qui collega il bonifico a un Receivable **esistente**
    (per questo i pulsanti +/edit/delete/view accanto all'autocomplete sono
    nascosti: in questo contesto non si crea un nuovo addebito).

    Il signal `_on_alloc_saved` aggiorna automaticamente
    `Receivable.stato`/`data_pagamento`/`importo_pagato`:

      - `importo` allocato ≥ `importo_dovuto` ⇒ `stato=pagato`
      - `importo` allocato > 0 ma < dovuto ⇒ resta `atteso` (parziale)
    """

    model = BankTransactionAllocation
    extra = 1
    fields = ("receivable", "importo", "info_alloc")
    readonly_fields = ("info_alloc",)
    autocomplete_fields = ("receivable",)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        field = formset.form.base_fields.get("receivable")
        if field is not None:
            widget = field.widget
            for flag in (
                "can_add_related",
                "can_change_related",
                "can_delete_related",
                "can_view_related",
            ):
                if hasattr(widget, flag):
                    setattr(widget, flag, False)
        return formset

    @admin.display(description="Stato")
    def info_alloc(self, obj):
        if not obj or not obj.pk or not obj.receivable_id:
            return "—"
        r = obj.receivable
        dovuto = r.importo_dovuto
        if obj.importo + _ALLOC_SOGLIA >= dovuto:
            return f"completo ({obj.importo}/{dovuto}€)"
        return f"parziale ({obj.importo}/{dovuto}€, mancano {dovuto - obj.importo}€)"


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

    def get_urls(self):
        from django.urls import path

        from .admin_views import genera_receivables_affitto_view
        return [
            path(
                "genera-affitto/",
                self.admin_site.admin_view(genera_receivables_affitto_view),
                name="billing_receivable_genera_affitto",
            ),
        ] + super().get_urls()
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
        "causale",
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
    inlines = (ReceivableAllocationsInline,)
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

    _MESI_PREFIX = {
        "gen": 1, "gennaio": 1,
        "feb": 2, "febbraio": 2,
        "mar": 3, "marzo": 3,
        "apr": 4, "aprile": 4,
        "mag": 5, "maggio": 5,
        "giu": 6, "giugno": 6,
        "lug": 7, "luglio": 7,
        "ago": 8, "agosto": 8,
        "set": 9, "settembre": 9,
        "ott": 10, "ottobre": 10,
        "nov": 11, "novembre": 11,
        "dic": 12, "dicembre": 12,
    }

    def get_search_results(self, request, queryset, search_term):
        """Filtra l'autocomplete a seconda del campo che lo richiama.

        Estensioni rispetto al search Django standard:

        - le parole che corrispondono a mesi italiani (``gen``, ``feb``,
          ``gennaio``...) vengono interpretate come filtro
          ``competenza_da__month=N`` invece che come testo: scrivere
          "eshani gen" trova gli addebiti di Eshani con competenza in
          gennaio (la repr è "...Utenze Gen 2026" ma "Gen" non è in
          nessun campo testuale del DB).
        - quando l'autocomplete arriva dall'inline
          ``BankTransactionAllocation.receivable`` (riconciliazione
          manuale di un bonifico), restringiamo ai Receivable in stato
          ATTESO: gli addebiti già pagati non vanno (ri)abbinati.
        """
        bits = search_term.split()
        text_bits = []
        for bit in bits:
            month = self._MESI_PREFIX.get(bit.lower())
            if month is not None:
                queryset = queryset.filter(competenza_da__month=month)
            else:
                text_bits.append(bit)
        text_search = " ".join(text_bits)

        queryset, may_have_duplicates = super().get_search_results(
            request, queryset, text_search
        )
        if (
            request.GET.get("model_name") == "banktransactionallocation"
            and request.GET.get("field_name") == "receivable"
        ):
            from billing.models.payments import StatoPagamento

            queryset = queryset.filter(stato=StatoPagamento.ATTESO)
        return queryset, may_have_duplicates
    fieldsets = (
        ("Addebito", {
            "fields": (
                "assignment", "causale", "descrizione",
                "competenza_da", "competenza_a", "scadenza",
                "is_aggiustamento", "utility_period", "giorni_presenza",
            ),
        }),
        ("Importi e stato", {
            "fields": ("importo_dovuto", "importo_pagato", "stato", "data_pagamento"),
        }),
        ("Calcolo utenze", {
            "fields": ("dettaglio_calcolo",),
            "classes": ("collapse",),
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
    readonly_fields = ("created_at", "updated_at", "dettaglio_calcolo")

    @admin.display(description="Dettaglio calcolo")
    def dettaglio_calcolo(self, obj):
        from decimal import ROUND_HALF_UP, Decimal

        from django.urls import reverse
        from django.utils.html import format_html, format_html_join

        if not obj or not obj.pk:
            return "—"
        if obj.causale != Receivable.Causale.UTENZE or not obj.utility_period_id:
            return "—"

        period = obj.utility_period
        tot = period.totale_periodo
        giorni_tot = period.giorni_totali or 0
        giorni_pers = obj.giorni_presenza or 0

        if giorni_tot > 0:
            quota_calc = (tot * Decimal(giorni_pers) / Decimal(giorni_tot)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            quota_calc = Decimal("0.00")
        diff = (obj.importo_dovuto - quota_calc) if obj.importo_dovuto is not None else None

        bills_html = ""
        bills = list(period.utility_bills.select_related("supplier").all())
        if bills:
            bill_url = lambda b: reverse("admin:billing_utilitybill_change", args=[b.pk])
            bills_html = format_html(
                "<div style='margin-top:8px'><b>Bollette agganciate:</b><ul style='margin:4px 0'>{}</ul></div>",
                format_html_join(
                    "",
                    "<li>{} — em. {} — {}€ ({})  <a href='{}'>↗</a></li>",
                    (
                        (b.supplier, b.data_emissione, b.importo_totale, b.get_prodotto_display(), bill_url(b))
                        for b in bills
                    ),
                ),
            )

        annual_html = ""
        annual = list(period.annual_utility_costs.all())
        if annual:
            annual_url = lambda a: reverse("admin:billing_annualutilitycost_change", args=[a.pk])
            annual_html = format_html(
                "<div style='margin-top:8px'><b>Costi annuali agganciati:</b><ul style='margin:4px 0'>{}</ul></div>",
                format_html_join(
                    "",
                    "<li>{} {} — annuale {}€  <a href='{}'>↗</a></li>",
                    (
                        (a.get_voce_display(), a.anno, a.importo_annuale, annual_url(a))
                        for a in annual
                    ),
                ),
            )

        diff_html = (
            format_html("<div>Diff arrotondamento: <b>{}€</b></div>", diff)
            if diff is not None and abs(diff) > Decimal("0.005")
            else ""
        )

        return format_html(
            "<div style='font-family:monospace;line-height:1.6'>"
            "<div><b>Periodo:</b> {} → {}</div>"
            "<div>&nbsp;&nbsp;Luce&nbsp;{}€&nbsp;&nbsp;&nbsp;Gas&nbsp;{}€&nbsp;&nbsp;&nbsp;TARI&nbsp;{}€&nbsp;&nbsp;&nbsp;Altro&nbsp;{}€</div>"
            "<div>&nbsp;&nbsp;<b>Tot&nbsp;&nbsp;{}€</b></div>"
            "<div style='margin-top:8px'>Quota: {} / {} giorni × {}€ = <b>{}€</b></div>"
            "<div>Pubblicato (foglio): <b>{}€</b></div>"
            "{}"
            "{}{}"
            "</div>",
            period.periodo_da, period.periodo_a,
            period.tot_luce, period.tot_gas, period.tot_tari, period.tot_altro,
            tot,
            giorni_pers, giorni_tot, tot, quota_calc,
            obj.importo_dovuto if obj.importo_dovuto is not None else "—",
            diff_html,
            bills_html, annual_html,
        )


# ---------------------------------------------------------------------------
# BankTransaction
# ---------------------------------------------------------------------------


@admin.register(BankTransaction)
class BankTransactionAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 1000

    list_display = (
        "data", "descrizione_breve", "importo",
        "owner_account", "n_allocations", "residuo_display",
        "stato_riconciliazione_icon",
        "get_edit_icon", "get_modal_edit_icon", "get_modal_delete_icon",
    )

    def get_list_display_links(self, request, list_display):
        # Override il default di JumboModelAdmin (solo `get_edit_icon`):
        # rendiamo cliccabili sia la data sia l'icona matita full-page.
        return ("data", "get_edit_icon")
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

    @admin.display(description="Residuo")
    def residuo_display(self, obj):
        r = obj.residuo
        if r <= 0:
            return ""
        return format_html(
            '<span style="color:#b35900;">{} €</span>', f"{float(r):.2f}"
        )

    @admin.display(description="Riconciliata")
    def stato_riconciliazione_icon(self, obj):
        stato = obj.stato_riconciliazione
        if stato == "pieno":
            return mark_safe(
                '<span title="Riconciliata pienamente" '
                'style="color:#2e7d32;font-size:1.1em;">✓</span>'
            )
        if stato == "parziale":
            return mark_safe(
                '<span title="Allocazione parziale (residuo non assegnato)" '
                'style="color:#ed6c02;font-size:1.1em;">⚠</span>'
            )
        return mark_safe(
            '<span title="Nessuna allocazione" '
            'style="color:#c62828;font-size:1.1em;">✗</span>'
        )


# ---------------------------------------------------------------------------
# Expense
# ---------------------------------------------------------------------------


@admin.register(Expense)
class ExpenseAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 900
    list_display = (
        "data", "category", "supplier", "importo",
        "anticipata_da_owner", "ripartibile_su_inquilini",
        "bolletta_pdf_link",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("category", "anticipata_da_owner", "ripartibile_su_inquilini")
    search_fields = ("descrizione", "category__nome", "supplier__nome")
    list_select_related = (
        "category", "supplier", "anticipata_da_owner", "utility_bill",
    )
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
            "fields": (
                "data", "descrizione", "category", "supplier", "importo",
                "ripartibile_su_inquilini", "bolletta_pdf_link",
            ),
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
    readonly_fields = ("bolletta_pdf_link", "created_at", "updated_at")

    @admin.display(description="PDF bolletta")
    def bolletta_pdf_link(self, obj):
        bolletta = getattr(obj, "utility_bill", None)
        if not bolletta or not bolletta.file_pdf:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">📄 {}</a>',
            bolletta.file_pdf.url,
            bolletta.numero_fattura or "apri PDF",
        )


# ---------------------------------------------------------------------------
# UtilityBill
# ---------------------------------------------------------------------------


@admin.action(description="Sincronizza Expense dalle bollette selezionate")
def sincronizza_expense_da_bollette(modeladmin, request, queryset):
    from billing.signals import sincronizza_expense_da_bolletta

    creati = aggiornati = rimossi = 0
    for bill in queryset.select_related("supplier", "pagata_da_owner", "expense"):
        prima = bill.expense_id
        sincronizza_expense_da_bolletta(bill)
        bill.refresh_from_db(fields=["expense"])
        dopo = bill.expense_id
        if prima is None and dopo is not None:
            creati += 1
        elif prima is not None and dopo is None:
            rimossi += 1
        elif prima is not None and dopo is not None:
            aggiornati += 1

    messages.success(
        request,
        f"Sincronizzazione completata: {creati} create, "
        f"{aggiornati} aggiornate, {rimossi} rimosse.",
    )


class UtilityBillActionForm(JumboActionForm):
    pagata_da = forms.ModelChoiceField(
        queryset=OwnerProfile.objects.all(),
        required=False,
        label="Pagata da proprietario",
    )
    fields_map = {
        "export_action": ["output_type"],
        "imposta_pagata_da_owner": ["pagata_da:required"],
    }


@admin.action(description="Imposta 'pagata da' e crea le Expense")
def imposta_pagata_da_owner(modeladmin, request, queryset):
    form = modeladmin.get_action_form_instance(request)
    if not form.is_valid():
        messages.error(request, "Selezionare un proprietario.")
        return
    owner = form.cleaned_data["pagata_da"]
    aggiornate = queryset.update(pagata_da_owner=owner)
    # `update()` non triggera post_save: forziamo la sincronizzazione.
    from billing.signals import sincronizza_expense_da_bolletta

    creati = 0
    for bill in queryset.select_related("supplier", "pagata_da_owner", "expense"):
        prima = bill.expense_id
        sincronizza_expense_da_bolletta(bill)
        bill.refresh_from_db(fields=["expense"])
        if prima is None and bill.expense_id is not None:
            creati += 1
    messages.success(
        request,
        f"{aggiornate} bollette assegnate a {owner.nominativo}; {creati} Expense create.",
    )


@admin.register(UtilityBill)
class UtilityBillAdmin(ModalEditMixin, JumboModelAdmin):
    modal_edit_width = 900
    list_display = (
        "supplier", "prodotto", "periodo_da", "periodo_a",
        "importo_totale", "pagata_da_owner", "consumo", "pdf_link",
        "get_modal_edit_icon", "get_modal_delete_icon",
    )
    list_filter = ("prodotto", "supplier", "pagata_da_owner")
    search_fields = ("numero_fattura", "supplier__nome")
    list_select_related = ("supplier", "pagata_da_owner", "expense")

    @admin.display(description="PDF")
    def pdf_link(self, obj):
        if obj.file_pdf:
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">📄</a>',
                obj.file_pdf.url,
            )
        return "—"
    autocomplete_fields = ("supplier", "pagata_da_owner")
    date_hierarchy = "periodo_da"
    ordering = ("-data_emissione",)
    action_form = UtilityBillActionForm
    actions = (imposta_pagata_da_owner, sincronizza_expense_da_bollette)
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
            "fields": ("pagata_da_owner", "expense", "file_pdf"),
            "classes": ("collapse",),
        }),
        ("Note", {
            "fields": ("note",),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("expense", "created_at", "updated_at")


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


@admin.action(description="Rigenera Receivable utenze")
def rigenera_receivables_utenze(modeladmin, request, queryset):
    from billing.calc.utility import calcola_conguaglio_periodo

    form = modeladmin.get_action_form_instance(request)
    if form.is_valid():
        dry_run = bool(form.cleaned_data.get("dry_run"))
        tenant = form.cleaned_data.get("tenant")
    else:
        dry_run = False
        tenant = None
    tenant_id = tenant.pk if tenant else None
    tag = "[DRY-RUN] " if dry_run else ""

    tot_persistiti = 0
    tot_skippati = 0
    skippati_dettaglio: list[str] = []
    errori: list[str] = []

    for period in queryset:
        label = f"{period.periodo_da} → {period.periodo_a} (id={period.pk})"
        try:
            risultato = calcola_conguaglio_periodo(
                period.pk, persist=not dry_run, tenant_id=tenant_id,
            )
        except Exception as e:
            errori.append(f"{label}: {e}")
            continue

        if dry_run:
            quote = risultato["quote"]
            if not quote:
                messages.info(
                    request,
                    f"{tag}{label}: nessuna quota per "
                    + (f"{tenant.nominativo}" if tenant else "i tenant attivi")
                    + " (verifica che ci siano bollette luce/gas nel periodo).",
                )
                continue
            messages.info(
                request,
                f"{tag}{label}: tot {risultato['totale_periodo']}€, "
                f"giorni-persona {risultato['sum_giorni_presenza']}",
            )
            for q in quote:
                dettaglio = ", ".join(
                    f"{v} {q['dettaglio'].get(v, 0)}€"
                    for v in ("luce", "gas", "tari", "altro")
                    if q["dettaglio"].get(v)
                )
                messages.info(
                    request,
                    f"    • {q['tenant_nominativo']}: "
                    f"{q['giorni_presenza']}gg → {q['quota']}€"
                    + (f" ({dettaglio})" if dettaglio else ""),
                )
            continue

        skippati = risultato.get("skippati_per_allocation", [])
        n_persistiti = len(risultato["quote"]) - len(skippati)
        tot_persistiti += n_persistiti
        tot_skippati += len(skippati)
        for s in skippati:
            skippati_dettaglio.append(
                f"{label} — {s['tenant_nominativo']}: "
                f"esistente {s['importo_esistente']}€, calcolato {s['importo_calcolato']}€"
            )

    if errori:
        for msg in errori:
            messages.error(request, msg)

    if not dry_run and (tot_persistiti or tot_skippati):
        messages.success(
            request,
            f"Rigenerazione completata: {tot_persistiti} Receivable utenze persistiti su "
            f"{queryset.count()} periodi"
            + (f" (solo inquilino {tenant.nominativo})" if tenant else "")
            + ".",
        )
    if skippati_dettaglio:
        messages.warning(
            request,
            f"{tot_skippati} Receivable NON aggiornati perché già allocati a "
            "transazioni bancarie (correggere via rettifica manuale):",
        )
        for d in skippati_dettaglio:
            messages.warning(request, f"    {d}")


def _mesi_in_periodo(periodo_da, periodo_a):
    """Itera (anno, mese) coperti almeno parzialmente dal periodo."""
    anno, mese = periodo_da.year, periodo_da.month
    while (anno, mese) <= (periodo_a.year, periodo_a.month):
        yield anno, mese
        if mese == 12:
            anno, mese = anno + 1, 1
        else:
            mese += 1


@admin.action(description="Rigenera Receivable affitto")
def rigenera_receivables_affitto(modeladmin, request, queryset):
    from billing.calc.rent import genera_pagamenti_mese

    form = modeladmin.get_action_form_instance(request)
    if form.is_valid():
        force = bool(form.cleaned_data.get("force"))
        dry_run = bool(form.cleaned_data.get("dry_run"))
        tenant = form.cleaned_data.get("tenant")
    else:
        force = dry_run = False
        tenant = None
    tenant_id = tenant.pk if tenant else None
    tag = "[DRY-RUN] " if dry_run else ""

    tot_creati = 0
    tot_aggiornati = 0
    tot_skippati = 0
    skippati_alloc_dettaglio: list[str] = []
    errori: list[str] = []
    mesi_processati: set[tuple[int, int]] = set()
    sim_per_azione: dict[str, int] = {}  # solo dry-run: contatore per azione_prevista

    for period in queryset:
        for anno, mese in _mesi_in_periodo(period.periodo_da, period.periodo_a):
            chiave = (anno, mese)
            if chiave in mesi_processati:
                continue  # stesso mese può essere coperto da più periodi selezionati
            mesi_processati.add(chiave)
            try:
                ris = genera_pagamenti_mese(
                    anno, mese, force=force, persist=not dry_run, tenant_id=tenant_id,
                )
            except Exception as e:
                errori.append(f"{anno}/{mese:02d}: {e}")
                continue
            if dry_run:
                for s in ris.get("simulazione", []):
                    sim_per_azione[s["azione_prevista"]] = sim_per_azione.get(s["azione_prevista"], 0) + 1
                    flag = " [aggiust.]" if s["is_aggiustamento"] else ""
                    messages.info(
                        request,
                        f"{tag}{anno}/{mese:02d} — {s['tenant_nominativo']}: "
                        f"{s['azione_prevista']} → {s['importo_dovuto']}€"
                        f" (scad. {s['scadenza']}, comp. {s['competenza_da']}→{s['competenza_a']}){flag}",
                    )
                continue
            tot_creati += ris["creati"]
            tot_aggiornati += ris["aggiornati"]
            tot_skippati += ris["skippati"]
            for s in ris.get("skippati_per_allocation", []):
                skippati_alloc_dettaglio.append(
                    f"{anno}/{mese:02d} — {s['tenant_nominativo']}: "
                    f"esistente {s['importo_esistente']}€, calcolato {s['importo_calcolato']}€"
                )

    for msg in errori:
        messages.error(request, msg)
    if dry_run:
        if sim_per_azione:
            riassunto = ", ".join(f"{a}: {n}" for a, n in sorted(sim_per_azione.items()))
            messages.info(
                request,
                f"{tag}Simulazione su {len(mesi_processati)} mesi — {riassunto}"
                + (f" (solo {tenant.nominativo})" if tenant else "")
                + (" [FORCE]" if force else ""),
            )
        else:
            messages.info(
                request,
                f"{tag}Nessun assignment attivo "
                + (f"per {tenant.nominativo} " if tenant else "")
                + f"sui {len(mesi_processati)} mesi selezionati.",
            )
        return
    if tot_creati or tot_aggiornati or tot_skippati:
        messages.success(
            request,
            f"Rigenerazione affitti su {len(mesi_processati)} mesi: "
            f"{tot_creati} creati, {tot_aggiornati} aggiornati, {tot_skippati} skippati"
            + (f" (solo {tenant.nominativo})" if tenant else "")
            + (" [FORCE]" if force else "")
            + ".",
        )
    if skippati_alloc_dettaglio:
        messages.warning(
            request,
            f"{len(skippati_alloc_dettaglio)} Receivable NON aggiornati perché già allocati "
            "a transazioni bancarie:",
        )
        for d in skippati_alloc_dettaglio:
            messages.warning(request, f"    {d}")


class UtilityChargePeriodActionForm(JumboActionForm):
    """Action form: campi extra visibili in base all'azione selezionata.

    - ``force``: rigenerazione affitto, sovrascrive esistenti.
    - ``dry_run``: simulazione (entrambe le actions): mostra il risultato
      senza scrivere nel DB.
    - ``tenant``: limita l'azione a un solo inquilino (debug).

    Il template ``jmb.jadmin/admin/actions.html`` aggiunge automaticamente
    classi CSS che la JS ``jmb.extra_action_fields_init`` usa per mostrare/
    nascondere i campi extra in base all'azione selezionata.
    """

    force = forms.BooleanField(
        required=False,
        label="Sovrascrivi esistenti",
        help_text="Se attivo, ricalcola anche i Receivable già presenti "
        "(la guardia allocations protegge comunque quelli riconciliati).",
    )
    dry_run = forms.BooleanField(
        required=False,
        label="Solo simulazione (dry-run)",
        help_text="Mostra cosa verrebbe scritto, senza toccare il DB.",
    )
    tenant = forms.ModelChoiceField(
        queryset=TenantProfile.objects.all(),
        required=False,
        label="Solo inquilino",
        help_text="Se valorizzato, limita l'azione a questo inquilino (debug).",
    )
    fields_map = {
        "export_action": ["output_type"],
        "rigenera_receivables_utenze": ["dry_run", "tenant"],
        "rigenera_receivables_affitto": ["force", "dry_run", "tenant"],
    }


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
    action_form = UtilityChargePeriodActionForm
    actions = (rigenera_receivables_utenze, rigenera_receivables_affitto)
    filter_horizontal = ("utility_bills", "annual_utility_costs")
    advanced_search_fields = (
        ("note__icontains:note", "nota_calcolo__icontains:nota calcolo"),
        ("stato", "criterio_ripartizione"),
        ("periodo_da__range", "periodo_da__gte:periodo dal ≥", "periodo_a__lte:periodo al ≤"),
        ("data_invio__range", "data_invio__gte:inviato dal", "data_invio__lte:inviato al"),
        ("giorni_totali__gte:giorni ≥", "giorni_totali__lte:giorni ≤"),
    )
    fieldsets = (
        ("Periodo", {
            "fields": ("periodo_da", "periodo_a", "criterio_ripartizione", "stato", "data_invio"),
        }),
        ("Totali (verità contabile)", {
            "fields": (
                "tot_luce", "tot_gas", "tot_tari", "tot_altro",
                "giorni_totali", "nota_calcolo",
            ),
        }),
        ("Bollette agganciate", {
            "fields": ("utility_bills", "annual_utility_costs"),
            "classes": ("collapse",),
        }),
        ("Note interne", {
            "fields": ("note",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")
    tabs = (
        ("Periodo", {"items": ["Periodo"]}),
        ("Totali", {"items": ["Totali (verità contabile)"]}),
        ("Charges per inquilino", {"items": [ReceivableUtilityInline]}),
        ("Bollette agganciate", {"items": ["Bollette agganciate"]}),
        ("Note interne", {"items": ["Note interne"]}),
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
