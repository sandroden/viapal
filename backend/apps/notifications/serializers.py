"""
Serializer per l'app notifications.
"""
from rest_framework import serializers

from notifications.models import (
    MessageTemplate,
    Notification,
    PushSubscription,
    ReminderRule,
)


class MessageTemplateSerializer(serializers.ModelSerializer):
    canale_display = serializers.CharField(source="get_canale_display", read_only=True)
    # La property è assegnata dal server (immobile attivo): mai in scrittura.
    property = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = MessageTemplate
        fields = [
            "id",
            "property",
            "codice",
            "titolo",
            "corpo",
            "canale",
            "canale_display",
        ]


class ReminderRuleSerializer(serializers.ModelSerializer):
    applicabile_a_display = serializers.CharField(
        source="get_applicabile_a_display", read_only=True
    )
    canale_display = serializers.CharField(source="get_canale_display", read_only=True)
    destinatario_display = serializers.CharField(
        source="get_destinatario_display", read_only=True
    )
    template_codice = serializers.CharField(
        source="template.codice", read_only=True, allow_null=True
    )
    property = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ReminderRule
        fields = [
            "id",
            "property",
            "applicabile_a",
            "applicabile_a_display",
            "giorni_offset",
            "canale",
            "canale_display",
            "destinatario",
            "destinatario_display",
            "template",
            "template_codice",
            "attiva",
        ]


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
