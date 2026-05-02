"""
Test per l'app notifications.

Coprono:
- MessageTemplate: creazione e __str__
- ReminderRule: configurazione solleciti
- PushSubscription: registrazione device
- Notification: log notifica con Generic FK
"""
import datetime

import pytest
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from notifications.models import MessageTemplate, Notification, PushSubscription, ReminderRule


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    return User.objects.create_user("eshani", email="eshani@v.it", password="pwd")


@pytest.fixture
def template_affitto(db):
    return MessageTemplate.objects.create(
        codice="affitto_promemoria_pre",
        titolo="Promemoria affitto",
        corpo="Caro {{nominativo}}, il tuo affitto di {{importo}}€ scade domani.",
        canale="push",
    )


# ---------------------------------------------------------------------------
# Test MessageTemplate
# ---------------------------------------------------------------------------


class TestMessageTemplate:
    def test_creazione(self, db, template_affitto):
        assert template_affitto.pk is not None
        assert "affitto_promemoria_pre" in str(template_affitto)
        assert "push" in str(template_affitto).lower() or "Push" in str(template_affitto)

    def test_unique_codice(self, db, template_affitto):
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            MessageTemplate.objects.create(
                codice="affitto_promemoria_pre",  # duplicato
                titolo="Altro template",
                corpo="...",
                canale="email",
            )


# ---------------------------------------------------------------------------
# Test ReminderRule
# ---------------------------------------------------------------------------


class TestReminderRule:
    def test_creazione_sollecito_pre_scadenza(self, db, template_affitto):
        rule = ReminderRule.objects.create(
            applicabile_a="affitto",
            giorni_offset=-1,
            canale="push",
            destinatario="inquilino",
            template=template_affitto,
        )
        assert rule.pk is not None
        assert rule.attiva is True
        assert "-1" in str(rule)

    def test_sollecito_post_scadenza(self, db):
        """Sollecito +9 giorni dopo scadenza, via email+push a entrambi."""
        rule = ReminderRule.objects.create(
            applicabile_a="affitto",
            giorni_offset=9,
            canale="both",
            destinatario="entrambi",
        )
        assert "+9" in str(rule)

    def test_regola_inattiva(self, db):
        rule = ReminderRule.objects.create(
            applicabile_a="conguaglio",
            giorni_offset=0,
            canale="push",
            destinatario="inquilino",
            attiva=False,
        )
        assert rule.attiva is False


# ---------------------------------------------------------------------------
# Test PushSubscription
# ---------------------------------------------------------------------------


class TestPushSubscription:
    def test_creazione(self, db, user):
        sub = PushSubscription.objects.create(
            user=user,
            endpoint="https://fcm.googleapis.com/fcm/send/fake-endpoint-1",
            p256dh="chiave_pubblica_base64",
            auth="auth_secret_base64",
            device_label="iPhone di Eshani",
        )
        assert sub.pk is not None
        assert "Eshani" in str(sub)

    def test_endpoint_unique(self, db, user):
        from django.db import IntegrityError

        PushSubscription.objects.create(
            user=user,
            endpoint="https://fcm.googleapis.com/fcm/send/unique-endpoint",
            p256dh="chiave",
            auth="auth",
        )
        user2 = User.objects.create_user("diana", email="diana@v.it", password="pwd")
        with pytest.raises(IntegrityError):
            PushSubscription.objects.create(
                user=user2,
                endpoint="https://fcm.googleapis.com/fcm/send/unique-endpoint",  # duplicato
                p256dh="chiave2",
                auth="auth2",
            )


# ---------------------------------------------------------------------------
# Test Notification
# ---------------------------------------------------------------------------


class TestNotification:
    def test_creazione_senza_riferimento(self, db, user, template_affitto):
        rule = ReminderRule.objects.create(
            applicabile_a="affitto",
            giorni_offset=-1,
            canale="push",
            destinatario="inquilino",
            template=template_affitto,
        )
        notif = Notification.objects.create(
            user=user,
            regola=rule,
            oggetto="Promemoria: affitto domani",
            corpo="Il tuo affitto scade domani.",
            canale="push",
        )
        assert notif.pk is not None
        assert "in attesa" in str(notif)

    def test_notifica_inviata(self, db, user):
        import datetime

        notif = Notification.objects.create(
            user=user,
            oggetto="Conguaglio ottobre inviato",
            corpo="Il tuo conguaglio di ottobre è €58.50.",
            canale="email",
            inviata_at=datetime.datetime(2024, 11, 1, 9, 0),
        )
        assert "inviata" in str(notif)

    def test_notifica_con_generic_fk(self, db, user):
        """Una notifica può essere collegata a qualsiasi oggetto del dominio tramite GenericFK."""
        # Usiamo User stesso come oggetto di riferimento per semplicità
        ct = ContentType.objects.get_for_model(User)
        notif = Notification.objects.create(
            user=user,
            oggetto="Test generic FK",
            corpo="Test",
            canale="push",
            oggetto_riferimento_type=ct,
            oggetto_riferimento_id=user.pk,
        )
        assert notif.oggetto_riferimento == user
