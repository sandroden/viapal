"""
ViewSet per l'app notifications.
Ogni utente vede e gestisce solo le proprie notifiche/subscription.
"""
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from notifications.models import Notification, PushSubscription
from notifications.push import invia_push, push_configurato
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

    def create(self, request, *args, **kwargs):
        """Upsert per ``endpoint``: il browser può ri-sottoscrivere lo stesso
        device (stesso endpoint) dopo un logout/login, anche con un altro
        utente — l'endpoint è unique, quindi si aggiorna invece di dare 400.
        """
        endpoint = request.data.get("endpoint")
        esistente = (
            PushSubscription.objects.filter(endpoint=endpoint).first()
            if endpoint
            else None
        )
        if esistente is None:
            return super().create(request, *args, **kwargs)
        serializer = self.get_serializer(esistente, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="vapid-public-key")
    def vapid_public_key(self, request):
        """Chiave pubblica VAPID per ``pushManager.subscribe`` nel frontend.

        ``abilitato=False`` (chiavi non configurate) → il frontend nasconde
        il toggle notifiche.
        """
        return Response(
            {
                "abilitato": push_configurato(),
                "public_key": settings.VAPID_PUBLIC_KEY,
            }
        )

    @action(detail=False, methods=["post"], url_path="test")
    def test(self, request):
        """Invia una push di prova ai device dell'utente corrente."""
        esito = invia_push(
            request.user,
            titolo="Viapal — notifica di prova",
            corpo="Le notifiche push funzionano su questo dispositivo. 🎉",
            url="/",
            salva_notification=False,
        )
        return Response(esito)
