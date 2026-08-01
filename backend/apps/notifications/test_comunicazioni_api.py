"""
Test di ``GET /api/v1/comunicazioni/`` — il registro delle comunicazioni
inviate agli inquilini, letto da un membro dell'immobile.

Il punto delicato è lo scoping: la lista deve contenere le comunicazioni
degli inquilini di *questo* immobile e nient'altro — né quelle di un altro
immobile, né quelle verso proprietari e gestori.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()

URL = "/api/v1/comunicazioni/"


def _tenant(immobile, suffisso):
    from properties.models import Room, RoomAssignment, TenantProfile

    room = Room.objects.create(
        property=immobile, nome=f"Camera {suffisso}", ordinamento=1
    )
    user = User.objects.create_user(
        username=f"tenant_com_{suffisso}", password="x", email=f"{suffisso}@ex.it"
    )
    tenant = TenantProfile.objects.create(
        property=immobile,
        user=user,
        nominativo=f"Inquilino {suffisso}",
        giorno_pagamento_affitto=1,
    )
    RoomAssignment.objects.create(
        tenant=tenant,
        room=room,
        valid_from=datetime.date(2024, 1, 1),
        canone_mensile=Decimal("400.00"),
    )
    return tenant


def _membro(immobile, username, ruolo=None):
    from properties.models import PropertyMembership

    ruolo = ruolo or PropertyMembership.Ruolo.PROPRIETARIO
    user = User.objects.create_user(username=username, password="x", email=f"{username}@ex.it")
    grp, _ = Group.objects.get_or_create(name="proprietari")
    user.groups.add(grp)
    PropertyMembership.objects.create(property=immobile, user=user, ruolo=ruolo)
    return user


def _notifica(user, codice, oggetto="Oggetto", canale=None, errore="", giorni_fa=0,
              oggetto_riferimento=None, corpo_html="<p>ciao</p>"):
    from notifications.models import Notification

    n = Notification.objects.create(
        user=user,
        canale=canale or Notification.CanaleComunicazione.EMAIL,
        codice=codice,
        destinatario=user.email,
        oggetto=oggetto,
        corpo="testo",
        corpo_html=corpo_html,
        errore=errore,
        inviata_at=None if errore else timezone.now(),
        oggetto_riferimento=oggetto_riferimento,
    )
    if giorni_fa:
        nuova = timezone.now() - datetime.timedelta(days=giorni_fa)
        Notification.objects.filter(pk=n.pk).update(created_at=nuova)
        n.refresh_from_db()
    return n


def _client(user, property_id=None):
    c = APIClient()
    c.force_authenticate(user=user)
    if property_id:
        c.credentials(HTTP_X_PROPERTY_ID=str(property_id))
    return c


class TestScoping:
    def test_solo_inquilini_dell_immobile(self, immobile, immobile2):
        t1 = _tenant(immobile, "uno")
        t2 = _tenant(immobile2, "due")
        _notifica(t1.user, "riepilogo_addebiti", oggetto="Mio")
        _notifica(t2.user, "riepilogo_addebiti", oggetto="Altrui")

        body = _client(_membro(immobile, "propr_scope")).get(URL).json()
        assert [x["oggetto"] for x in body["results"]] == ["Mio"]
        assert body["results"][0]["tenant_nominativo"] == "Inquilino uno"
        assert body["results"][0]["tenant_id"] == t1.id

    def test_esclude_notifiche_ai_proprietari(self, immobile):
        """Le note sugli addebiti vanno ai proprietari: non sono 'cosa ho
        inviato agli inquilini' e non devono comparire."""
        tenant = _tenant(immobile, "tre")
        propr = _membro(immobile, "propr_escl")
        _notifica(tenant.user, "riepilogo_addebiti", oggetto="All'inquilino")
        _notifica(propr, "commento", oggetto="Al proprietario")

        body = _client(propr).get(URL).json()
        assert [x["oggetto"] for x in body["results"]] == ["All'inquilino"]

    def test_non_membro_403(self, immobile, immobile2):
        tenant = _tenant(immobile, "quattro")
        _notifica(tenant.user, "riepilogo_addebiti")
        estraneo = _membro(immobile2, "estraneo")
        resp = _client(estraneo, property_id=immobile.id).get(URL)
        assert resp.status_code == 403

    def test_sola_lettura_puo_leggere(self, immobile):
        from properties.models import PropertyMembership

        tenant = _tenant(immobile, "cinque")
        _notifica(tenant.user, "riepilogo_addebiti")
        ro = _membro(immobile, "ro_com", ruolo=PropertyMembership.Ruolo.SOLA_LETTURA)
        resp = _client(ro).get(URL)
        assert resp.status_code == 200
        assert resp.json()["count"] == 1


class TestFiltri:
    def test_tipo_distingue_invito_e_riepilogo(self, immobile):
        """Stesso inquilino, stessa GenericFK: solo il codice li separa."""
        tenant = _tenant(immobile, "sei")
        _notifica(
            tenant.user, "invito_inquilino", oggetto="Invito",
            oggetto_riferimento=tenant,
        )
        _notifica(
            tenant.user, "riepilogo_addebiti", oggetto="Riepilogo",
            oggetto_riferimento=tenant,
        )
        c = _client(_membro(immobile, "propr_tipo"))

        body = c.get(URL, {"tipo": "riepilogo_addebiti"}).json()
        assert [x["oggetto"] for x in body["results"]] == ["Riepilogo"]
        assert body["results"][0]["tipo_display"] == "Riepilogo addebiti"

        body = c.get(URL, {"tipo": "invito_inquilino"}).json()
        assert [x["oggetto"] for x in body["results"]] == ["Invito"]

    def test_tenant_canale_esito(self, immobile):
        from notifications.models import Notification

        t1 = _tenant(immobile, "sette")
        t2 = _tenant(immobile, "otto")
        _notifica(t1.user, "riepilogo_addebiti", oggetto="Email ok")
        _notifica(
            t1.user, "riepilogo_addebiti", oggetto="Push",
            canale=Notification.CanaleComunicazione.PUSH,
        )
        _notifica(
            t2.user, "riepilogo_addebiti", oggetto="Fallita",
            errore="SMTP giù",
        )
        c = _client(_membro(immobile, "propr_filtri"))

        assert c.get(URL, {"tenant": t1.id}).json()["count"] == 2
        assert c.get(URL, {"canale": "push"}).json()["count"] == 1
        errori = c.get(URL, {"esito": "errore"}).json()
        assert [x["oggetto"] for x in errori["results"]] == ["Fallita"]
        assert errori["results"][0]["errore"] == "SMTP giù"
        assert errori["results"][0]["inviata_at"] is None
        assert c.get(URL, {"esito": "inviato"}).json()["count"] == 2

    def test_finestra_date(self, immobile):
        tenant = _tenant(immobile, "nove")
        _notifica(tenant.user, "riepilogo_addebiti", oggetto="Vecchia", giorni_fa=40)
        _notifica(tenant.user, "riepilogo_addebiti", oggetto="Recente")
        c = _client(_membro(immobile, "propr_date"))

        da = (timezone.now() - datetime.timedelta(days=7)).date().isoformat()
        body = c.get(URL, {"da": da}).json()
        assert [x["oggetto"] for x in body["results"]] == ["Recente"]

        a = (timezone.now() - datetime.timedelta(days=30)).date().isoformat()
        body = c.get(URL, {"a": a}).json()
        assert [x["oggetto"] for x in body["results"]] == ["Vecchia"]


class TestPayload:
    def test_lista_senza_corpo_dettaglio_con_corpo(self, immobile):
        tenant = _tenant(immobile, "dieci")
        n = _notifica(
            tenant.user, "riepilogo_addebiti", corpo_html="<p>HTML vero</p>"
        )
        c = _client(_membro(immobile, "propr_payload"))

        riga = c.get(URL).json()["results"][0]
        assert "corpo" not in riga
        assert "corpo_html" not in riga

        dettaglio = c.get(f"{URL}{n.id}/").json()
        assert dettaglio["corpo_html"] == "<p>HTML vero</p>"
        assert dettaglio["corpo"] == "testo"

    def test_paginazione(self, immobile):
        tenant = _tenant(immobile, "undici")
        for i in range(7):
            _notifica(tenant.user, "riepilogo_addebiti", oggetto=f"n{i}")
        c = _client(_membro(immobile, "propr_pag"))

        body = c.get(URL, {"limit": 3}).json()
        assert body["count"] == 7
        assert len(body["results"]) == 3
        assert body["next"]

    def test_dettaglio_di_altro_immobile_404(self, immobile, immobile2):
        t2 = _tenant(immobile2, "dodici")
        n = _notifica(t2.user, "riepilogo_addebiti")
        c = _client(_membro(immobile, "propr_404"))
        assert c.get(f"{URL}{n.id}/").status_code == 404
