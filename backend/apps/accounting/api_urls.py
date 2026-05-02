"""
URL router per le API dell'app accounting.
"""
from rest_framework.routers import DefaultRouter

from accounting.views import InterOwnerEntryViewSet, OwnerLedgerEntryViewSet

router = DefaultRouter()
router.register(r"ledger-entries", OwnerLedgerEntryViewSet, basename="ledger-entry")
router.register(r"inter-owner-entries", InterOwnerEntryViewSet, basename="inter-owner-entry")

urlpatterns = router.urls
