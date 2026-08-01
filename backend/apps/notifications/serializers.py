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


# Etichette leggibili dei tipi di comunicazione. Mappa esplicita, non una
# deduzione dal ContentType: invito inquilino e riepilogo addebiti puntano
# entrambi a un TenantProfile e il ContentType non li distinguerebbe.
TIPO_LABEL = {
    "avviso_utenze": "Avviso utenze",
    "riepilogo_addebiti": "Riepilogo addebiti",
    "invito_inquilino": "Invito inquilino",
    "invito_membership": "Invito membro",
    "commento": "Nota su addebito",
}


class ComunicazioneSerializer(serializers.ModelSerializer):
    """Riga del registro comunicazioni (lista per immobile).

    Il corpo **non** c'è: è il payload pesante di questa tabella e serve solo
    nel dettaglio (``GET /api/v1/comunicazioni/<id>/``).
    """

    canale_display = serializers.CharField(source="get_canale_display", read_only=True)
    tenant_id = serializers.IntegerField(
        source="user.tenant_profile.id", read_only=True
    )
    tenant_nominativo = serializers.CharField(
        source="user.tenant_profile.nominativo", read_only=True
    )
    tipo_display = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "tenant_id",
            "tenant_nominativo",
            "destinatario",
            "canale",
            "canale_display",
            "codice",
            "tipo_display",
            "oggetto",
            "inviata_at",
            "letta_at",
            "errore",
            "created_at",
        ]

    def get_tipo_display(self, obj) -> str:
        return TIPO_LABEL.get(obj.codice, obj.codice or "—")


class ComunicazioneDettaglioSerializer(ComunicazioneSerializer):
    """Come sopra, più il testo realmente recapitato."""

    class Meta(ComunicazioneSerializer.Meta):
        fields = ComunicazioneSerializer.Meta.fields + ["corpo", "corpo_html"]


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
