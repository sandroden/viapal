"""
Test del servizio Web Push (notifications/push.py) e delle action API.

``webpush`` di pywebpush viene mockato: qui si verifica la logica attorno
(prune delle subscription morte, logging Notification, esiti), non la
crittografia né il push service reale.
"""
from unittest import mock

import pytest
from django.contrib.auth.models import User
from pywebpush import WebPushException
from rest_framework.test import APIClient

from notifications.models import Notification, PushSubscription
from notifications.push import invia_push, push_configurato


@pytest.fixture(autouse=True)
def vapid_keys(settings):
    """Chiavi VAPID deterministiche per i test.

    In CI pytest gira con ``ENV=production``: lì le chiavi arrivano da env
    (vuote) e ``push_configurato()`` sarebbe False, rendendo no-op ogni
    invio. Le fissiamo qui così i test non dipendono dall'ambiente; i casi
    che vogliono il canale spento le azzerano nel corpo del test.
    """
    settings.VAPID_PRIVATE_KEY = "test-vapid-private"
    settings.VAPID_PUBLIC_KEY = "test-vapid-public"
    settings.VAPID_CLAIMS_SUB = "mailto:test@viapal.it"


@pytest.fixture
def user(db):
    return User.objects.create_user("push_user", email="p@v.it", password="pwd123!")


@pytest.fixture
def subscription(user):
    return PushSubscription.objects.create(
        user=user,
        endpoint="https://push.example.com/abc",
        p256dh="fakep256dh",
        auth="fakeauth",
        device_label="Chrome su Linux",
    )


def _webpush_exception(status_code):
    response = mock.Mock(status_code=status_code)
    return WebPushException("boom", response=response)


class TestInviaPush:
    def test_senza_subscription_no_op(self, user):
        esito = invia_push(user, "Titolo", "Corpo")
        assert esito == {"inviate": 0, "rimosse": 0, "errori": 0}
        assert Notification.objects.count() == 0

    def test_invio_ok_logga_notification(self, user, subscription):
        with mock.patch("pywebpush.webpush") as wp:
            esito = invia_push(user, "Titolo", "Corpo", url="/i/utenze/1")
        assert esito["inviate"] == 1
        assert wp.call_count == 1
        # payload JSON con title/body/url per il service worker
        payload = wp.call_args.kwargs["data"]
        assert '"title": "Titolo"' in payload
        assert '"url": "/i/utenze/1"' in payload
        notifica = Notification.objects.get()
        assert notifica.user == user
        assert notifica.canale == Notification.CanaleComunicazione.PUSH
        assert notifica.inviata_at is not None
        subscription.refresh_from_db()
        assert subscription.ultima_attivita is not None

    def test_410_elimina_subscription(self, user, subscription):
        with mock.patch("pywebpush.webpush", side_effect=_webpush_exception(410)):
            esito = invia_push(user, "Titolo", "Corpo")
        assert esito == {"inviate": 0, "rimosse": 1, "errori": 0}
        assert not PushSubscription.objects.filter(pk=subscription.pk).exists()
        assert Notification.objects.count() == 0

    def test_errore_generico_non_elimina(self, user, subscription):
        with mock.patch("pywebpush.webpush", side_effect=_webpush_exception(500)):
            esito = invia_push(user, "Titolo", "Corpo")
        assert esito == {"inviate": 0, "rimosse": 0, "errori": 1}
        assert PushSubscription.objects.filter(pk=subscription.pk).exists()

    def test_senza_chiavi_vapid_no_op(self, user, subscription, settings):
        settings.VAPID_PRIVATE_KEY = ""
        assert not push_configurato()
        with mock.patch("pywebpush.webpush") as wp:
            esito = invia_push(user, "Titolo", "Corpo")
        assert esito == {"inviate": 0, "rimosse": 0, "errori": 0}
        wp.assert_not_called()

    def test_salva_notification_false(self, user, subscription):
        with mock.patch("pywebpush.webpush"):
            invia_push(user, "Titolo", "Corpo", salva_notification=False)
        assert Notification.objects.count() == 0


class TestPushApiActions:
    @pytest.fixture
    def client(self, user):
        c = APIClient()
        c.force_login(user)
        return c

    def test_vapid_public_key(self, client, settings):
        settings.VAPID_PUBLIC_KEY = "chiave-pubblica"
        settings.VAPID_PRIVATE_KEY = "chiave-privata"
        resp = client.get("/api/v1/push-subscriptions/vapid-public-key/")
        assert resp.status_code == 200
        assert resp.json() == {"abilitato": True, "public_key": "chiave-pubblica"}

    def test_vapid_public_key_non_configurata(self, client, settings):
        settings.VAPID_PUBLIC_KEY = ""
        settings.VAPID_PRIVATE_KEY = ""
        resp = client.get("/api/v1/push-subscriptions/vapid-public-key/")
        assert resp.json()["abilitato"] is False

    def test_upsert_stesso_endpoint(self, client, user, subscription):
        resp = client.post(
            "/api/v1/push-subscriptions/",
            {
                "endpoint": subscription.endpoint,
                "p256dh": "nuova-p256dh",
                "auth": "nuova-auth",
                "device_label": "Chrome su Android",
            },
            format="json",
        )
        assert resp.status_code == 200  # aggiornata, non creata
        assert PushSubscription.objects.count() == 1
        subscription.refresh_from_db()
        assert subscription.p256dh == "nuova-p256dh"
        assert subscription.device_label == "Chrome su Android"

    def test_upsert_riassegna_utente(self, client, user, db):
        altro = User.objects.create_user("altro_push", password="pwd123!")
        sub = PushSubscription.objects.create(
            user=altro,
            endpoint="https://push.example.com/condiviso",
            p256dh="x",
            auth="y",
        )
        resp = client.post(
            "/api/v1/push-subscriptions/",
            {"endpoint": sub.endpoint, "p256dh": "x2", "auth": "y2"},
            format="json",
        )
        assert resp.status_code == 200
        sub.refresh_from_db()
        # Stesso device, nuovo login: la subscription passa all'utente corrente.
        assert sub.user == user

    def test_push_di_prova(self, client, user, subscription):
        with mock.patch("pywebpush.webpush") as wp:
            resp = client.post("/api/v1/push-subscriptions/test/")
        assert resp.status_code == 200
        assert resp.json()["inviate"] == 1
        assert wp.call_count == 1
        # La prova non deve sporcare il log delle notifiche reali.
        assert Notification.objects.count() == 0
