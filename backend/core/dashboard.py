"""Dashboard custom per django-admin-tools.

Riferita da settings.ADMIN_TOOLS_INDEX_DASHBOARD / ADMIN_TOOLS_APP_INDEX_DASHBOARD.
NB: NON chiamare admin_tools.dashboard.autodiscover() — quella funzione fa
`import imp` rimosso in Python 3.12+. Qui dichiariamo tutto esplicitamente.
"""
from __future__ import annotations

import datetime

from django.urls import reverse
from admin_tools.dashboard import Dashboard, AppIndexDashboard, modules


def _link(title: str, url: str, description: str = "") -> dict:
    return {"title": title, "url": url, "description": description}


class ViapalPagamentiInRitardoModule(modules.LinkList):
    """Receivable in stato IN_RITARDO o INSOLUTO."""

    title = "Pagamenti in ritardo"
    template = "admin_tools/dashboard/modules/link_list.html"
    layout = "stacked"

    def init_with_context(self, context):
        if self._initialized:
            return
        # Import lazy: evita problemi all'import di settings prima di app loading
        from billing.models import Receivable, StatoPagamento

        oggi = datetime.date.today()
        qs = (
            Receivable.objects
            .filter(stato__in=[StatoPagamento.IN_RITARDO, StatoPagamento.INSOLUTO])
            .select_related("assignment__tenant")
            .order_by("scadenza")[:15]
        )
        for r in qs:
            tenant = r.assignment.tenant.nominativo if r.assignment_id else "—"
            giorni = (oggi - r.scadenza).days if r.scadenza else 0
            label = f"{tenant} — {r.get_causale_display()} €{r.importo_dovuto:.2f} (+{giorni}gg)"
            self.children.append(
                _link(
                    label,
                    reverse("admin:billing_receivable_change", args=[r.pk]),
                    description=f"Scaduto il {r.scadenza}",
                )
            )
        if not self.children:
            self.pre_content = "Nessun pagamento in ritardo."
        super().init_with_context(context)


class ViapalConguagliDaInviareModule(modules.LinkList):
    """UtilityChargePeriod in stato BOZZA / senza data_invio."""

    title = "Utenze da inviare"
    template = "admin_tools/dashboard/modules/link_list.html"
    layout = "stacked"

    def init_with_context(self, context):
        if self._initialized:
            return
        from billing.models import UtilityChargePeriod

        qs = (
            UtilityChargePeriod.objects
            .filter(data_invio__isnull=True)
            .order_by("-periodo_da")[:10]
        )
        for p in qs:
            label = (
                f"{p.periodo_da.strftime('%d/%m/%Y')} – "
                f"{p.periodo_a.strftime('%d/%m/%Y')} ({p.get_stato_display()})"
            )
            self.children.append(
                _link(
                    label,
                    reverse("admin:billing_utilitychargeperiod_change", args=[p.pk]),
                )
            )
        if not self.children:
            self.pre_content = "Tutte le utenze sono state inviate."
        super().init_with_context(context)


class ViapalSaldiNegativiModule(modules.LinkList):
    """Inquilini con saldo annuale negativo (dovuto > pagato)."""

    title = "Inquilini con saldo negativo (anno corrente)"
    template = "admin_tools/dashboard/modules/link_list.html"
    layout = "stacked"

    def init_with_context(self, context):
        if self._initialized:
            return
        from decimal import Decimal

        from billing.models import Receivable, StatoPagamento
        from properties.models import TenantProfile

        anno = datetime.date.today().year
        saldi: dict[int, Decimal] = {}
        nominativi: dict[int, str] = {}

        # Tutti i Receivable di tenant attivi nell'anno corrente
        qs = (
            Receivable.objects
            .filter(competenza_da__year=anno)
            .select_related("assignment__tenant")
        )
        for r in qs:
            if not r.assignment_id or not r.assignment.tenant_id:
                continue
            tid = r.assignment.tenant_id
            nominativi[tid] = r.assignment.tenant.nominativo
            saldo = saldi.get(tid, Decimal("0"))
            pagato = r.importo_pagato or Decimal("0") if r.stato == StatoPagamento.PAGATO else Decimal("0")
            saldo += pagato - r.importo_dovuto
            saldi[tid] = saldo

        negativi = sorted(
            ((tid, s) for tid, s in saldi.items() if s < 0),
            key=lambda x: x[1],  # piu' negativi prima
        )
        for tid, s in negativi[:10]:
            label = f"{nominativi[tid]} — saldo €{s:.2f}"
            self.children.append(
                _link(
                    label,
                    reverse("admin:properties_tenantprofile_change", args=[tid]),
                )
            )
        if not self.children:
            self.pre_content = "Tutti gli inquilini sono in pari."
        super().init_with_context(context)


class ViapalIndexDashboard(Dashboard):
    """Dashboard principale dell'admin (override di /admin/)."""

    title = "Viapal — pannello operativo"
    columns = 2

    def init_with_context(self, context):
        # Moduli operativi (top-level, non in Group: il rendering Group nidificato
        # in dashboard-column ha problemi CSS)
        self.children.append(ViapalPagamentiInRitardoModule())
        self.children.append(ViapalConguagliDaInviareModule())
        self.children.append(ViapalSaldiNegativiModule())

        # AppList — anagrafiche
        self.children.append(
            modules.AppList(
                title="Anagrafiche e immobile",
                models=("properties.*", "accounts.*"),
            )
        )

        # Tabelle "di configurazione" / a basso cambio: spostate fuori dal tab
        # "Pagamenti e bollette" e raggruppate in un tab dedicato.
        CONFIG_MODELS = (
            "billing.models.expenses.ExpenseCategory",
            "billing.models.expenses.Supplier",
            "billing.models.expenses.TenantCondominioRate",
        )

        # Group tabs: pagamenti+bollette (default) | contabilita' fratelli | configurazione.
        # Ordine = primo tab visibile by default.
        self.children.append(
            modules.Group(
                title="Pagamenti e contabilità",
                display="tabs",
                children=[
                    modules.AppList(
                        title="Pagamenti e bollette",
                        models=("billing.*",),
                        exclude=CONFIG_MODELS,
                    ),
                    modules.AppList(
                        title="Contabilità fratelli",
                        models=("accounting.*",),
                    ),
                    modules.AppList(
                        title="Configurazione",
                        models=CONFIG_MODELS,
                    ),
                ],
            )
        )

        # Notifiche separato
        self.children.append(
            modules.AppList(
                title="Notifiche e solleciti",
                models=("notifications.*",),
            )
        )

        # LinkList — strumenti rapidi
        self.children.append(
            modules.LinkList(
                title="Strumenti rapidi",
                children=[
                    _link(
                        "Genera settlement annuale",
                        reverse("admin:accounting_ownersettlement_genera"),
                        "Chiusura conti tra fratelli per anno (cassa virtuale)",
                    ),
                    _link(
                        "Saldi fratelli (frontend)",
                        "/p/saldi-fratelli/",
                        "Saldi live + storico settlement",
                    ),
                    _link(
                        "Quadro annuale (frontend)",
                        "/p/quadro-annuale/",
                        "Vista riepilogo utenze annuale",
                    ),
                    _link(
                        "Ritardi (frontend)",
                        "/p/ritardi/",
                        "Cruscotto pagamenti in ritardo",
                    ),
                    _link(
                        "Repository GitHub",
                        "https://github.com/sandroden/viapal",
                        "Codice sorgente",
                    ),
                ],
            )
        )

        # Recent actions
        self.children.append(
            modules.RecentActions(title="Ultime azioni", limit=10)
        )


class ViapalAppIndexDashboard(AppIndexDashboard):
    """Dashboard delle pagine /admin/<app>/."""

    title = ""

    def __init__(self, app_title, models, **kwargs):
        super().__init__(app_title, models, **kwargs)
        self.title = app_title
        self.children += [
            modules.ModelList(title=app_title, models=self.models),
            modules.RecentActions(
                title="Ultime azioni in questa app",
                include_list=self.get_app_content_types(),
                limit=10,
            ),
        ]

    def init_with_context(self, context):
        return super().init_with_context(context)
