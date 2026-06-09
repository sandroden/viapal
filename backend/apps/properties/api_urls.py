"""
URL router per le API dell'app properties.
"""
from rest_framework.routers import DefaultRouter

from properties.views import (
    ContractViewSet,
    OwnerBankAccountViewSet,
    OwnerProfileViewSet,
    RoomAssignmentViewSet,
    RoomViewSet,
    TenantDocumentViewSet,
    TenantProfileViewSet,
)

router = DefaultRouter()
router.register(r"owners", OwnerProfileViewSet, basename="owner-profile")
router.register(r"tenants", TenantProfileViewSet, basename="tenant-profile")
router.register(r"tenant-documents", TenantDocumentViewSet, basename="tenant-document")
router.register(r"rooms", RoomViewSet, basename="room")
router.register(r"room-assignments", RoomAssignmentViewSet, basename="room-assignment")
router.register(r"contracts", ContractViewSet, basename="contract")
router.register(r"bank-accounts", OwnerBankAccountViewSet, basename="owner-bank-account")

urlpatterns = router.urls
