"""
Test dell'API dei modelli documento (``/api/v1/document-templates/``).

Il testo dei documenti è un dato dell'immobile: qui si verifica che ogni
immobile veda e modifichi solo i propri, e che le due action di supporto
(esempio e segnaposto) restino allineate al generatore.
"""
import re

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from properties.documenti import esempio
from properties.models import DocumentTemplate, PropertyMembership, TenantProfile

pytestmark = pytest.mark.django_db

URL = "/api/v1/document-templates/"
ATTO = "atto_subentro_locazione"
CESSIONE = "cessione_fabbricato"


def _client(user):
    c = APIClient(enforce_csrf_checks=False)
    c.force_login(user)
    return c


def _membro(immobile, username, ruolo=PropertyMembership.Ruolo.PROPRIETARIO):
    user = User.objects.create_user(username=username)
    PropertyMembership.objects.create(property=immobile, user=user, ruolo=ruolo)
    return _client(user)


@pytest.fixture
def client_prop(immobile):
    return _membro(immobile, "prop")


@pytest.fixture
def client_sola_lettura(immobile):
    return _membro(immobile, "lettore", PropertyMembership.Ruolo.SOLA_LETTURA)


@pytest.fixture
def client_inq(immobile):
    user = User.objects.create_user(username="inq")
    gruppo, _ = Group.objects.get_or_create(name="inquilini")
    user.groups.add(gruppo)
    TenantProfile.objects.create(
        user=user, property=immobile, nominativo="Inq", giorno_pagamento_affitto=5
    )
    return _client(user)


class TestCrud:
    def test_carica_un_modello(self, client_prop, immobile):
        resp = client_prop.post(
            URL,
            {"codice": ATTO, "nome": "Atto 2026", "corpo_html": "<p>{{stanza}}</p>"},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        modello = DocumentTemplate.objects.get()
        assert modello.property_id == immobile.pk
        assert modello.corpo_html == "<p>{{stanza}}</p>"

    def test_un_solo_modello_per_codice(self, client_prop):
        dati = {"codice": ATTO, "corpo_html": "<p>x</p>"}
        assert client_prop.post(URL, dati, format="json").status_code == 201
        assert client_prop.post(URL, dati, format="json").status_code == 400

    def test_sostituisce_il_corpo(self, client_prop):
        creato = client_prop.post(
            URL, {"codice": ATTO, "corpo_html": "<p>vecchio</p>"}, format="json"
        ).json()
        resp = client_prop.patch(
            f"{URL}{creato['id']}/", {"corpo_html": "<p>nuovo</p>"}, format="json"
        )
        assert resp.status_code == 200
        assert DocumentTemplate.objects.get().corpo_html == "<p>nuovo</p>"

    def test_elimina(self, client_prop):
        creato = client_prop.post(
            URL, {"codice": ATTO, "corpo_html": "<p>x</p>"}, format="json"
        ).json()
        assert client_prop.delete(f"{URL}{creato['id']}/").status_code == 204
        assert not DocumentTemplate.objects.exists()

    def test_modello_di_altro_immobile_invisibile(self, client_prop, immobile2):
        DocumentTemplate.objects.create(
            property=immobile2, codice=ATTO, corpo_html="<p>altrove</p>"
        )
        assert client_prop.get(URL).json() == []


class TestPermessi:
    def test_sola_lettura_legge_ma_non_scrive(self, client_sola_lettura):
        assert client_sola_lettura.get(URL).status_code == 200
        resp = client_sola_lettura.post(
            URL, {"codice": ATTO, "corpo_html": "<p>x</p>"}, format="json"
        )
        assert resp.status_code == 403

    def test_inquilino_non_accede(self, client_inq):
        assert client_inq.get(URL).status_code == 403


class TestSupporto:
    def test_esempio(self, client_prop):
        resp = client_prop.get(f"{URL}esempio/", {"codice": CESSIONE})
        assert resp.status_code == 200
        assert resp.json()["corpo_html"] == esempio(CESSIONE)

    def test_segnaposto_coprono_l_esempio(self, client_prop):
        """L'elenco mostrato a chi scrive un modello deve contenere tutti i
        segnaposto che l'esempio già usa."""
        dati = client_prop.get(f"{URL}segnaposto/", {"codice": ATTO}).json()
        disponibili = {s["chiave"] for s in dati["segnaposto"]}
        usati = set(re.findall(r"\{\{(\w+)\}\}", esempio(ATTO)))
        assert usati <= disponibili
        assert dati["titolo"] == "Atto di subentro nel contratto di locazione"

    def test_codice_sconosciuto_400(self, client_prop):
        assert client_prop.get(f"{URL}esempio/", {"codice": "x"}).status_code == 400
        assert client_prop.get(f"{URL}segnaposto/").status_code == 400
