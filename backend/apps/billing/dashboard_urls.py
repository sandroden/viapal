"""
URL per gli endpoint custom dashboard.
"""
from django.urls import path

from billing.dashboard_views import (
    BilancioOwnerDettaglioView,
    ConguagliaPrevisionaleView,
    ContoEconomicoView,
    DashboardInquilinoView,
    DashboardProprietarioView,
    PrevisionaleUtenzeView,
    QuadroAnnualeView,
    RendicontoView,
    TenantSituazioneView,
)

urlpatterns = [
    path("dashboard/inquilino/", DashboardInquilinoView.as_view(), name="dashboard-inquilino"),
    path("dashboard/proprietario/", DashboardProprietarioView.as_view(), name="dashboard-proprietario"),
    path(
        "dashboard/conto-economico/",
        ContoEconomicoView.as_view(),
        name="dashboard-conto-economico",
    ),
    path(
        "dashboard/proprietario/<int:owner_id>/dettaglio-bilancio/",
        BilancioOwnerDettaglioView.as_view(),
        name="dashboard-proprietario-dettaglio-bilancio",
    ),
    path("quadro-annuale/<int:anno>/", QuadroAnnualeView.as_view(), name="quadro-annuale"),
    path(
        "tenants/<int:tenant_id>/situazione/",
        TenantSituazioneView.as_view(),
        name="tenant-situazione",
    ),
    path(
        "tenants/<int:tenant_id>/rendiconto/",
        RendicontoView.as_view(),
        name="tenant-rendiconto",
    ),
    path(
        "tenants/<int:tenant_id>/previsionale-utenze/",
        PrevisionaleUtenzeView.as_view(),
        name="tenant-previsionale-utenze",
    ),
    path(
        "tenants/<int:tenant_id>/conguaglia-previsionale/",
        ConguagliaPrevisionaleView.as_view(),
        name="tenant-conguaglia-previsionale",
    ),
]
