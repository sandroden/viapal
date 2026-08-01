"""
URL router per le API dell'app notifications.
"""
from rest_framework.routers import DefaultRouter

from notifications.views import (
    ComunicazioniViewSet,
    MessageTemplateViewSet,
    NotificationViewSet,
    PushSubscriptionViewSet,
    ReminderRuleViewSet,
)

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"comunicazioni", ComunicazioniViewSet, basename="comunicazione")
router.register(r"push-subscriptions", PushSubscriptionViewSet, basename="push-subscription")
router.register(r"reminder-rules", ReminderRuleViewSet, basename="reminder-rule")
router.register(r"message-templates", MessageTemplateViewSet, basename="message-template")

urlpatterns = router.urls
