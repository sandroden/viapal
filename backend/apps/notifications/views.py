"""
ViewSet per l'app notifications.
Ogni utente vede e gestisce solo le proprie notifiche/subscription.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from notifications.models import Notification, PushSubscription
from notifications.serializers import NotificationSerializer, PushSubscriptionSerializer


class NotificationViewSet(ReadOnlyModelViewSet):
    """
    Notifiche: l'utente vede solo le proprie.
    """

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by("-created_at")


class PushSubscriptionViewSet(ModelViewSet):
    """
    Subscription push: CRUD limitato all'utente corrente.
    """

    serializer_class = PushSubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PushSubscription.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
