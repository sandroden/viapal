"""
URL per gli endpoint custom dashboard.
"""
from django.urls import path

from billing.dashboard_views import (
    DashboardInquilinoView,
    DashboardProprietarioView,
    QuadroAnnualeView,
)

urlpatterns = [
    path("dashboard/inquilino/", DashboardInquilinoView.as_view(), name="dashboard-inquilino"),
    path("dashboard/proprietario/", DashboardProprietarioView.as_view(), name="dashboard-proprietario"),
    path("quadro-annuale/<int:anno>/", QuadroAnnualeView.as_view(), name="quadro-annuale"),
]
