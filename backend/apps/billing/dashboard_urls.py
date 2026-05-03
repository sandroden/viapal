"""
URL per gli endpoint custom dashboard.
"""
from django.urls import path

from billing.dashboard_views import (
    BilancioOwnerDettaglioView,
    DashboardInquilinoView,
    DashboardProprietarioView,
    QuadroAnnualeView,
    TenantSituazioneView,
)

urlpatterns = [
    path("dashboard/inquilino/", DashboardInquilinoView.as_view(), name="dashboard-inquilino"),
    path("dashboard/proprietario/", DashboardProprietarioView.as_view(), name="dashboard-proprietario"),
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
]
