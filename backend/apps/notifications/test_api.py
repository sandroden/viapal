"""
Test API per l'app notifications.

Coprono:
- Notification: utente vede solo le proprie
- PushSubscription: CRUD limitato all'utente
"""
import datetime

import pytest
from django.contrib.auth.models import Group, User
from django.utils import timezone
from rest_framework.test import APIClient

from notifications.models import Notification, PushSubscription


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    return APIClient(enforce_csrf_checks=False)


@pytest.fixture
def gruppo_inquilini(db):
    grp, _ = Group.objects.get_or_create(name="inquilini")
    return grp


@pytest.fixture
def user_a(db, gruppo_inquilini):
    u = User.objects.create_user("notif_user_a", email="na@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    return u


@pytest.fixture
def user_b(db, gruppo_inquilini):
    u = User.objects.create_user("notif_user_b", email="nb@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    return u


@pytest.fixture
def notifica_a(db, user_a):
    return Notification.objects.create(
        user=user_a,
        oggetto="Promemoria affitto",
        corpo="Il tuo affitto scade domani.",
        canale="push",
        inviata_at=timezone.now(),
    )


@pytest.fixture
def notifica_b(db, user_b):
    return Notification.objects.create(
        user=user_b,
        oggetto="Conguaglio inviato",
        corpo="Il tuo conguaglio e' disponibile.",
        canale="push",
        inviata_at=timezone.now(),
    )


@pytest.fixture
def subscription_a(db, user_a):
    return PushSubscription.objects.create(
        user=user_a,
        endpoint="https://push.example.com/sub-user-a",
        p256dh="fakep256dh_a",
        auth="fakeauth_a",
        device_label="Browser A",
    )


@pytest.fixture
def client_a(api_client, user_a):
    api_client.force_login(user_a)
    return api_client


@pytest.fixture
def client_b(api_client, user_b):
    api_client.force_login(user_b)
    return api_client


# ---------------------------------------------------------------------------
# Test NotificationViewSet
# ---------------------------------------------------------------------------


class TestNotificationViewSet:
    def test_utente_vede_solo_proprie(self, client_a, notifica_a, notifica_b):
        resp = client_a.get("/api/v1/notifications/")
        assert resp.status_code == 200
        ids = [n["id"] for n in resp.json()]
        assert notifica_a.id in ids
        assert notifica_b.id not in ids

    def test_nessuna_notifica_su_utente_vuoto(self, client_b):
        resp = client_b.get("/api/v1/notifications/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_detail_notifica_propria(self, client_a, notifica_a):
        resp = client_a.get(f"/api/v1/notifications/{notifica_a.id}/")
        assert resp.status_code == 200
        assert resp.json()["oggetto"] == "Promemoria affitto"

    def test_detail_notifica_altrui_non_trovata(self, client_a, notifica_b):
        resp = client_a.get(f"/api/v1/notifications/{notifica_b.id}/")
        assert resp.status_code == 404

    def test_anonimo_non_accede(self, api_client):
        resp = api_client.get("/api/v1/notifications/")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test PushSubscriptionViewSet
# ---------------------------------------------------------------------------


class TestPushSubscriptionViewSet:
    def test_utente_vede_solo_proprie_subscription(self, client_a, subscription_a):
        resp = client_a.get("/api/v1/push-subscriptions/")
        assert resp.status_code == 200
        ids = [s["id"] for s in resp.json()]
        assert subscription_a.id in ids

    def test_crea_subscription(self, client_a):
        resp = client_a.post(
            "/api/v1/push-subscriptions/",
            {
                "endpoint": "https://push.example.com/new-sub",
                "p256dh": "abcdefgh123456",
                "auth": "xyzauth",
                "device_label": "Nuovo Browser",
            },
            format="json",
        )
        assert resp.status_code == 201
        # Verifica che l'utente sia stato assegnato automaticamente
        sub_id = resp.json()["id"]
        assert PushSubscription.objects.get(pk=sub_id).user.username == "notif_user_a"

    def test_elimina_propria_subscription(self, client_a, subscription_a):
        resp = client_a.delete(f"/api/v1/push-subscriptions/{subscription_a.id}/")
        assert resp.status_code == 204
        assert not PushSubscription.objects.filter(pk=subscription_a.id).exists()

    def test_non_vede_subscription_altrui(self, client_a, user_b):
        sub_b = PushSubscription.objects.create(
            user=user_b,
            endpoint="https://push.example.com/sub-b-2",
            p256dh="fakep256_b2",
            auth="fakeauth_b2",
        )
        resp = client_a.get(f"/api/v1/push-subscriptions/{sub_b.id}/")
        assert resp.status_code == 404
