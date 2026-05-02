"""
URL per gli endpoint custom dashboard.
"""
from django.urls import path

from billing.dashboard_views import (
    DashboardInquilinoView,
    DashboardProprietarioView,
    QuadroAnnualeView,
    TenantSituazioneView,
)

urlpatterns = [
    path("dashboard/inquilino/", DashboardInquilinoView.as_view(), name="dashboard-inquilino"),
    path("dashboard/proprietario/", DashboardProprietarioView.as_view(), name="dashboard-proprietario"),
    path("quadro-annuale/<int:anno>/", QuadroAnnualeView.as_view(), name="quadro-annuale"),
    path(
        "tenants/<int:tenant_id>/situazione/",
        TenantSituazioneView.as_view(),
        name="tenant-situazione",
    ),
]
