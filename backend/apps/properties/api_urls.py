"""
URL router per le API dell'app properties.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from properties.views import (
    ContractViewSet,
    GalleryAreaViewSet,
    GalleryImageViewSet,
    OwnerBankAccountViewSet,
    OwnerProfileViewSet,
    PropertyViewSet,
    PublicGalleryView,
    RoomAssignmentViewSet,
    RoomViewSet,
    TenantDocumentViewSet,
    TenantProfileViewSet,
)

router = DefaultRouter()
router.register(r"owners", OwnerProfileViewSet, basename="owner-profile")
router.register(r"tenants", TenantProfileViewSet, basename="tenant-profile")
router.register(r"tenant-documents", TenantDocumentViewSet, basename="tenant-document")
router.register(r"properties", PropertyViewSet, basename="property")
router.register(r"rooms", RoomViewSet, basename="room")
router.register(r"room-assignments", RoomAssignmentViewSet, basename="room-assignment")
router.register(r"gallery-areas", GalleryAreaViewSet, basename="gallery-area")
router.register(r"gallery-images", GalleryImageViewSet, basename="gallery-image")
router.register(r"contracts", ContractViewSet, basename="contract")
router.register(r"bank-accounts", OwnerBankAccountViewSet, basename="owner-bank-account")

urlpatterns = [
    path(
        "public/galleria/<slug:slug>/",
        PublicGalleryView.as_view(),
        name="public-gallery",
    ),
    *router.urls,
]
