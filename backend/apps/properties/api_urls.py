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
    TenantProfileViewSet,
)

router = DefaultRouter()
router.register(r"owner-profiles", OwnerProfileViewSet, basename="owner-profile")
router.register(r"tenant-profiles", TenantProfileViewSet, basename="tenant-profile")
router.register(r"rooms", RoomViewSet, basename="room")
router.register(r"room-assignments", RoomAssignmentViewSet, basename="room-assignment")
router.register(r"contracts", ContractViewSet, basename="contract")
router.register(r"owner-bank-accounts", OwnerBankAccountViewSet, basename="owner-bank-account")

urlpatterns = router.urls
