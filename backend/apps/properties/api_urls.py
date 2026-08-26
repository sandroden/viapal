"""
URL router per le API dell'app properties.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from properties.og import og_image
from properties.views import (
    ContractViewSet,
    DocumentShareViewSet,
    DocumentTemplateViewSet,
    GalleryAreaViewSet,
    GalleryImageViewSet,
    InformativaPrivacyView,
    OwnerBankAccountViewSet,
    OwnerProfileViewSet,
    PropertyDocumentViewSet,
    PropertyViewSet,
    PublicDocumentShareView,
    PublicGalleryView,
    PublicShareFileView,
    RoomAssignmentViewSet,
    RoomViewSet,
    ShareItemViewSet,
    TenantDocumentViewSet,
    TenantProfileViewSet,
)

router = DefaultRouter()
router.register(r"properties", PropertyViewSet, basename="property")
router.register(r"owners", OwnerProfileViewSet, basename="owner-profile")
router.register(r"tenants", TenantProfileViewSet, basename="tenant-profile")
router.register(r"tenant-documents", TenantDocumentViewSet, basename="tenant-document")
router.register(
    r"property-documents", PropertyDocumentViewSet, basename="property-document"
)
router.register(r"rooms", RoomViewSet, basename="room")
router.register(r"room-assignments", RoomAssignmentViewSet, basename="room-assignment")
router.register(r"gallery-areas", GalleryAreaViewSet, basename="gallery-area")
router.register(r"gallery-images", GalleryImageViewSet, basename="gallery-image")
router.register(r"contracts", ContractViewSet, basename="contract")
router.register(
    r"document-templates", DocumentTemplateViewSet, basename="document-template"
)
router.register(r"bank-accounts", OwnerBankAccountViewSet, basename="owner-bank-account")
router.register(r"document-shares", DocumentShareViewSet, basename="document-share")
router.register(r"share-items", ShareItemViewSet, basename="share-item")

urlpatterns = [
    path(
        "public/galleria/<slug:slug>/",
        PublicGalleryView.as_view(),
        name="public-gallery",
    ),
    # Anteprima social: sotto /api/ perché il reverse proxy ci instrada già.
    path(
        "public/og-image/<slug:slug>.jpg",
        og_image,
        name="public-og-image",
    ),
    path(
        "public/documenti/<str:token>/",
        PublicDocumentShareView.as_view(),
        name="public-document-share",
    ),
    path(
        "public/documenti/<str:token>/file/<int:item_id>/",
        PublicShareFileView.as_view(),
        name="public-document-share-file",
    ),
    path(
        "privacy/informativa/",
        InformativaPrivacyView.as_view(),
        name="privacy-informativa",
    ),
    *router.urls,
]
