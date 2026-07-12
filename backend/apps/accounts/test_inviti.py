"""Test del flusso invito inquilino e reset/imposta password.

Coprono:
- ``accounts.inviti.invia_invito_inquilino``: email, link, ruolo, casi limite;
- l'endpoint ``/api/auth/password/reset/`` brandizzato (link verso la SPA);
- che il token dell'invito sia validabile da ``/api/auth/password/reset/confirm/``
  e che l'inquilino possa poi autenticarsi con la nuova password.
"""
import re

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from accounts.inviti import invia_invito_inquilino
from properties.models import TenantProfile

LINK_RE = re.compile(r"/imposta-password/([^/\s]+)/([^/\s<\"]+)")


@pytest.fixture
def client():
    return APIClient(enforce_csrf_checks=False)


@pytest.fixture
def inquilino_user(db):
    return User.objects.create_user("inquidemo", email="demo@v.it", password="pwd123!")


@pytest.fixture
def tenant(db, inquilino_user, immobile):
    return TenantProfile.objects.create(
        user=inquilino_user,
        property=immobile,
        nominativo="Demo Inquilino",
        giorno_pagamento_affitto=1,
    )


def test_invito_manda_email_con_link_e_username(tenant, mailoutbox):
    esito = invia_invito_inquilino(tenant)

    assert esito["esito"] == "inviato"
    assert esito["email"] == "demo@v.it"
    assert len(mailoutbox) == 1
    msg = mailoutbox[0]
    assert msg.to == ["demo@v.it"]
    # username e link presenti nel corpo testo
    assert "inquidemo" in msg.body
    assert LINK_RE.search(msg.body)
    # versione HTML allegata col pulsante
    html = msg.alternatives[0][0]
    assert "Imposta la password" in html


def test_invito_aggiunge_al_gruppo_inquilini(tenant):
    assert not tenant.user.groups.filter(name="inquilini").exists()
    invia_invito_inquilino(tenant)
    assert tenant.user.groups.filter(name="inquilini").exists()


def test_invito_senza_email_da_errore(db, immobile):
    u = User.objects.create_user("senzaemail", password="pwd123!")
    t = TenantProfile.objects.create(
        user=u, property=immobile, nominativo="Senza Email",
        giorno_pagamento_affitto=1,
    )
    esito = invia_invito_inquilino(t)
    assert esito["esito"] == "errore"
    assert "email" in esito["errore"].lower()


def test_invito_usa_email_alt_e_la_copia_su_user(db, mailoutbox, immobile):
    u = User.objects.create_user("soloalt", password="pwd123!")  # user.email vuoto
    t = TenantProfile.objects.create(
        user=u,
        property=immobile,
        nominativo="Solo Alt",
        giorno_pagamento_affitto=1,
        email_alt="alt@v.it",
    )
    esito = invia_invito_inquilino(t)
    assert esito["esito"] == "inviato"
    assert esito["email"] == "alt@v.it"
    u.refresh_from_db()
    # copiata su user.email così è utilizzabile anche per il login via email
    assert u.email == "alt@v.it"


def test_invito_registra_notification(tenant):
    invia_invito_inquilino(tenant)
    assert tenant.user.notifications.filter(canale="email").exists()


def test_reset_endpoint_genera_link_spa(client, inquilino_user, mailoutbox):
    """L'endpoint password/reset deve mandare un'email il cui link punta alla
    SPA (/imposta-password/...), grazie a SpaPasswordResetSerializer."""
    resp = client.post(
        "/api/auth/password/reset/", {"email": "demo@v.it"}, format="json"
    )
    assert resp.status_code == 200
    assert len(mailoutbox) == 1
    assert LINK_RE.search(mailoutbox[0].body)


def test_invito_link_validabile_e_login(client, tenant, mailoutbox):
    """Il token dell'invito è accettato dal confirm e dopo l'inquilino entra."""
    invia_invito_inquilino(tenant)
    match = LINK_RE.search(mailoutbox[0].body)
    uid, token = match.group(1), match.group(2)

    nuova = "NuovaPwd123!"
    resp = client.post(
        "/api/auth/password/reset/confirm/",
        {"uid": uid, "token": token, "new_password1": nuova, "new_password2": nuova},
        format="json",
    )
    assert resp.status_code == 200, resp.content

    # ora il login con la nuova password funziona
    login = client.post(
        "/api/auth/login/",
        {"username": "inquidemo", "password": nuova},
        format="json",
    )
    assert login.status_code in (200, 204)


def test_confirm_token_invalido(client, tenant, mailoutbox):
    invia_invito_inquilino(tenant)
    uid = LINK_RE.search(mailoutbox[0].body).group(1)
    resp = client.post(
        "/api/auth/password/reset/confirm/",
        {
            "uid": uid,
            "token": "xxxxxx-invalido",
            "new_password1": "NuovaPwd123!",
            "new_password2": "NuovaPwd123!",
        },
        format="json",
    )
    assert resp.status_code == 400
