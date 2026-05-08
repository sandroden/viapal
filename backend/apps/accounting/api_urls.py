"""
URL router per le API dell'app accounting.
"""
from rest_framework.routers import DefaultRouter

from accounting.views import (
    InterOwnerEntryViewSet,
    OwnerLedgerEntryViewSet,
    OwnerSettlementViewSet,
)

router = DefaultRouter()
router.register(r"owner-ledger", OwnerLedgerEntryViewSet, basename="ledger-entry")
router.register(r"inter-owner-entries", InterOwnerEntryViewSet, basename="inter-owner-entry")
router.register(r"owner-settlements", OwnerSettlementViewSet, basename="owner-settlement")

urlpatterns = router.urls
