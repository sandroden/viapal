"""
Serializer per l'app notifications.
"""
from rest_framework import serializers

from notifications.models import Notification, PushSubscription


class NotificationSerializer(serializers.ModelSerializer):
    canale_display = serializers.CharField(source="get_canale_display", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "user",
            "oggetto",
            "corpo",
            "canale",
            "canale_display",
            "inviata_at",
            "letta_at",
        ]
        read_only_fields = ["user", "inviata_at"]


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = [
            "id",
            "endpoint",
            "p256dh",
            "auth",
            "device_label",
            "ultima_attivita",
        ]
        read_only_fields = ["ultima_attivita"]
