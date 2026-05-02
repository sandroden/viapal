"""
URL router per le API dell'app notifications.
"""
from rest_framework.routers import DefaultRouter

from notifications.views import NotificationViewSet, PushSubscriptionViewSet

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"push-subscriptions", PushSubscriptionViewSet, basename="push-subscription")

urlpatterns = router.urls
