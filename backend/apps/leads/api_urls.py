"""Router delle API dei lead."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from leads.views import LeadBulkUpsertView, LeadViewSet

router = DefaultRouter()
router.register(r"leads", LeadViewSet, basename="lead")

urlpatterns = [
    # Prima del router: altrimenti il detail del ViewSet cattura
    # "bulk-upsert" come pk (stessa trappola del bulk-import movimenti).
    path("leads/bulk-upsert/", LeadBulkUpsertView.as_view(), name="lead-bulk-upsert"),
    *router.urls,
]
