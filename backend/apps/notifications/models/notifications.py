"""
Modelli per notifiche push, solleciti configurabili e template messaggi.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from properties.models import TimestampedModel


class MessageTemplate(TimestampedModel):
    """Template di un messaggio di notifica con placeholder."""

    class CanaleComunicazione(models.TextChoices):
        EMAIL = "email", "Email"
        PUSH = "push", "Push notification"
        SMS = "sms", "SMS"

    codice = models.SlugField(
        unique=True,
        verbose_name="codice",
        help_text="Identificativo univoco del template (es. 'affitto_promemoria_pre').",
    )
    titolo = models.CharField(
        max_length=200,
        verbose_name="titolo",
    )
    corpo = models.TextField(
        verbose_name="corpo",
        help_text="Testo del messaggio con placeholder {{variabile}}.",
    )
    canale = models.CharField(
        max_length=10,
        choices=CanaleComunicazione.choices,
        verbose_name="canale",
    )

    class Meta:
        verbose_name = "template messaggio"
        verbose_name_plural = "template messaggi"
        ordering = ["codice"]

    def __str__(self):
        return f"[{self.get_canale_display()}] {self.codice}"


class ReminderRule(TimestampedModel):
    """Regola configurabile per l'invio automatico di solleciti."""

    class ApplicabileA(models.TextChoices):
        AFFITTO = "affitto", "Affitto"
        CONGUAGLIO = "conguaglio", "Conguaglio utenze"
        EXTRA = "extra", "Addebito extra"

    class CanaleSollecito(models.TextChoices):
        EMAIL = "email", "Solo email"
        PUSH = "push", "Solo push"
        BOTH = "both", "Email + push"

    class Destinatario(models.TextChoices):
        INQUILINO = "inquilino", "Inquilino"
        PROPRIETARIO = "proprietario", "Proprietario"
        ENTRAMBI = "entrambi", "Entrambi"

    applicabile_a = models.CharField(
        max_length=20,
        choices=ApplicabileA.choices,
        verbose_name="applicabile a",
    )
    giorni_offset = models.IntegerField(
        verbose_name="giorni offset",
        help_text="Giorni rispetto alla scadenza: negativo = prima, positivo = dopo.",
    )
    canale = models.CharField(
        max_length=10,
        choices=CanaleSollecito.choices,
        verbose_name="canale",
    )
    destinatario = models.CharField(
        max_length=20,
        choices=Destinatario.choices,
        verbose_name="destinatario",
    )
    template = models.ForeignKey(
        MessageTemplate,
        on_delete=models.SET_NULL,
        related_name="reminder_rules",
        null=True,
        blank=True,
        verbose_name="template messaggio",
    )
    attiva = models.BooleanField(
        default=True,
        verbose_name="attiva",
    )

    class Meta:
        verbose_name = "regola sollecito"
        verbose_name_plural = "regole solleciti"
        ordering = ["applicabile_a", "giorni_offset"]

    def __str__(self):
        segno = "+" if self.giorni_offset >= 0 else ""
        return (
            f"{self.get_applicabile_a_display()} "
            f"{segno}{self.giorni_offset}gg — "
            f"{self.get_canale_display()} → {self.get_destinatario_display()}"
        )


class PushSubscription(TimestampedModel):
    """Registrazione di un device per le notifiche push (VAPID)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
        verbose_name="utente",
    )
    endpoint = models.TextField(
        unique=True,
        verbose_name="endpoint",
    )
    p256dh = models.TextField(
        verbose_name="chiave p256dh",
    )
    auth = models.TextField(
        verbose_name="auth",
    )
    device_label = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="etichetta device",
    )
    ultima_attivita = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="ultima attività",
    )

    class Meta:
        verbose_name = "iscrizione push"
        verbose_name_plural = "iscrizioni push"
        ordering = ["-created_at"]

    def __str__(self):
        label = self.device_label or self.endpoint[:40]
        return f"{self.user} — {label}"


class Notification(TimestampedModel):
    """Log di una notifica inviata o da inviare a un utente."""

    class CanaleComunicazione(models.TextChoices):
        EMAIL = "email", "Email"
        PUSH = "push", "Push notification"
        SMS = "sms", "SMS"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="utente",
    )
    regola = models.ForeignKey(
        ReminderRule,
        on_delete=models.SET_NULL,
        related_name="notifications",
        null=True,
        blank=True,
        verbose_name="regola sollecito",
    )
    oggetto = models.CharField(
        max_length=200,
        verbose_name="oggetto",
    )
    corpo = models.TextField(
        verbose_name="corpo",
    )
    inviata_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="inviata il",
    )
    letta_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="letta il",
    )
    canale = models.CharField(
        max_length=10,
        choices=CanaleComunicazione.choices,
        verbose_name="canale",
    )
    # Generic FK per collegare a qualsiasi oggetto del dominio
    oggetto_riferimento_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="tipo oggetto collegato",
    )
    oggetto_riferimento_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        verbose_name="ID oggetto collegato",
    )
    oggetto_riferimento = GenericForeignKey(
        "oggetto_riferimento_type",
        "oggetto_riferimento_id",
    )

    class Meta:
        verbose_name = "notifica"
        verbose_name_plural = "notifiche"
        ordering = ["-created_at"]

    def __str__(self):
        stato = "inviata" if self.inviata_at else "in attesa"
        return f"{self.user} — {self.oggetto} [{stato}]"
