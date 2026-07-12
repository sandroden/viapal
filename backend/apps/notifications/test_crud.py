"""
Test CRUD per ReminderRule e MessageTemplate (Fase D — sostituzione admin).

Entrambi gli endpoint sono property-scoped (IsPropertyMember): CRUD felice
da membro operativo, 403 scritture per sola_lettura e inquilini, isolamento
cross-property (create sull'immobile attivo, oggetti altrui → 404).
"""
import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from notifications.models import MessageTemplate, ReminderRule
from properties.models import PropertyMembership, TenantProfile

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gruppo_proprietari(db):
    grp, _ = Group.objects.get_or_create(name="proprietari")
    return grp


@pytest.fixture
def gruppo_inquilini(db):
    grp, _ = Group.objects.get_or_create(name="inquilini")
    return grp


def _client(user):
    c = APIClient(enforce_csrf_checks=False)
    c.force_login(user)
    return c


@pytest.fixture
def client_operativo(immobile, gruppo_proprietari):
    u = User.objects.create_user("not_owner", email="not_owner@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    return _client(u)


@pytest.fixture
def client_sola_lettura(immobile, gruppo_proprietari):
    u = User.objects.create_user("not_readonly", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.SOLA_LETTURA
    )
    return _client(u)


@pytest.fixture
def client_inquilino(immobile, gruppo_inquilini):
    u = User.objects.create_user("not_inq", email="not_inq@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    TenantProfile.objects.create(
        user=u, property=immobile, nominativo="Inquilino Notifiche",
        giorno_pagamento_affitto=1,
    )
    return _client(u)


@pytest.fixture
def template(immobile):
    return MessageTemplate.objects.create(
        property=immobile,
        codice="affitto_promemoria_pre",
        titolo="Promemoria affitto",
        corpo="Ciao {{nome}}, l'affitto scade il {{scadenza}}.",
        canale=MessageTemplate.CanaleComunicazione.EMAIL,
    )


@pytest.fixture
def regola(immobile, template):
    return ReminderRule.objects.create(
        property=immobile,
        applicabile_a=ReminderRule.ApplicabileA.AFFITTO,
        giorni_offset=-3,
        canale=ReminderRule.CanaleSollecito.EMAIL,
        destinatario=ReminderRule.Destinatario.INQUILINO,
        template=template,
    )


@pytest.fixture
def mondo_b(immobile2):
    from types import SimpleNamespace

    m = SimpleNamespace(property=immobile2)
    m.template = MessageTemplate.objects.create(
        property=immobile2,
        codice="affitto_promemoria_pre",
        titolo="Promemoria B",
        corpo="Corpo B",
        canale=MessageTemplate.CanaleComunicazione.EMAIL,
    )
    m.regola = ReminderRule.objects.create(
        property=immobile2,
        applicabile_a=ReminderRule.ApplicabileA.AFFITTO,
        giorni_offset=1,
        canale=ReminderRule.CanaleSollecito.PUSH,
        destinatario=ReminderRule.Destinatario.INQUILINO,
    )
    return m


# ---------------------------------------------------------------------------
# MessageTemplateViewSet
# ---------------------------------------------------------------------------


class TestMessageTemplateCrud:
    PAYLOAD = {
        "codice": "sollecito_utenze",
        "titolo": "Sollecito utenze",
        "corpo": "Ciao {{nome}}, ricordati le utenze.",
        "canale": "email",
    }

    def test_create_atterra_su_immobile_attivo(self, client_operativo, immobile):
        resp = client_operativo.post(
            "/api/v1/message-templates/", self.PAYLOAD, format="json"
        )
        assert resp.status_code == 201, resp.content
        creato = MessageTemplate.objects.get(pk=resp.json()["id"])
        assert creato.property_id == immobile.id
        assert resp.json()["property"] == immobile.id

    def test_codice_duplicato_400(self, client_operativo, template):
        resp = client_operativo.post(
            "/api/v1/message-templates/",
            {**self.PAYLOAD, "codice": template.codice},
            format="json",
        )
        assert resp.status_code == 400
        assert "codice" in resp.json()

    def test_stesso_codice_su_altro_immobile_ok(self, client_operativo, mondo_b):
        # mondo_b usa già 'affitto_promemoria_pre': su A resta libero.
        resp = client_operativo.post(
            "/api/v1/message-templates/",
            {**self.PAYLOAD, "codice": mondo_b.template.codice},
            format="json",
        )
        assert resp.status_code == 201, resp.content

    def test_update(self, client_operativo, template):
        resp = client_operativo.patch(
            f"/api/v1/message-templates/{template.id}/",
            {"titolo": "Nuovo titolo"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        template.refresh_from_db()
        assert template.titolo == "Nuovo titolo"

    def test_delete(self, client_operativo, template):
        resp = client_operativo.delete(f"/api/v1/message-templates/{template.id}/")
        assert resp.status_code == 204
        assert not MessageTemplate.objects.filter(pk=template.id).exists()

    def test_list_scopata(self, client_operativo, template, mondo_b):
        resp = client_operativo.get("/api/v1/message-templates/")
        assert resp.status_code == 200
        ids = {t["id"] for t in resp.json()}
        assert template.id in ids
        assert mondo_b.template.id not in ids

    def test_sola_lettura_legge_ma_non_scrive(self, client_sola_lettura, template):
        resp = client_sola_lettura.get("/api/v1/message-templates/")
        assert resp.status_code == 200
        resp = client_sola_lettura.post(
            "/api/v1/message-templates/", self.PAYLOAD, format="json"
        )
        assert resp.status_code == 403

    def test_inquilino_non_accede(self, client_inquilino):
        resp = client_inquilino.get("/api/v1/message-templates/")
        assert resp.status_code == 403
        resp = client_inquilino.post(
            "/api/v1/message-templates/", self.PAYLOAD, format="json"
        )
        assert resp.status_code == 403

    def test_template_altrui_404(self, client_operativo, mondo_b):
        resp = client_operativo.patch(
            f"/api/v1/message-templates/{mondo_b.template.id}/",
            {"titolo": "Hack"},
            format="json",
        )
        assert resp.status_code == 404
        resp = client_operativo.delete(
            f"/api/v1/message-templates/{mondo_b.template.id}/"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# ReminderRuleViewSet
# ---------------------------------------------------------------------------


class TestReminderRuleCrud:
    PAYLOAD = {
        "applicabile_a": "affitto",
        "giorni_offset": -5,
        "canale": "both",
        "destinatario": "inquilino",
        "attiva": True,
    }

    def test_create_atterra_su_immobile_attivo(
        self, client_operativo, immobile, template
    ):
        resp = client_operativo.post(
            "/api/v1/reminder-rules/",
            {**self.PAYLOAD, "template": template.id},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        creata = ReminderRule.objects.get(pk=resp.json()["id"])
        assert creata.property_id == immobile.id
        assert creata.template_id == template.id
        assert creata.giorni_offset == -5

    def test_create_senza_template(self, client_operativo, immobile):
        resp = client_operativo.post(
            "/api/v1/reminder-rules/", self.PAYLOAD, format="json"
        )
        assert resp.status_code == 201, resp.content

    def test_template_altrui_400(self, client_operativo, mondo_b):
        resp = client_operativo.post(
            "/api/v1/reminder-rules/",
            {**self.PAYLOAD, "template": mondo_b.template.id},
            format="json",
        )
        assert resp.status_code == 400
        assert "template" in resp.json()

    def test_update(self, client_operativo, regola):
        resp = client_operativo.patch(
            f"/api/v1/reminder-rules/{regola.id}/",
            {"giorni_offset": 2, "attiva": False},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        regola.refresh_from_db()
        assert regola.giorni_offset == 2
        assert regola.attiva is False

    def test_delete(self, client_operativo, regola):
        resp = client_operativo.delete(f"/api/v1/reminder-rules/{regola.id}/")
        assert resp.status_code == 204
        assert not ReminderRule.objects.filter(pk=regola.id).exists()

    def test_list_scopata(self, client_operativo, regola, mondo_b):
        resp = client_operativo.get("/api/v1/reminder-rules/")
        assert resp.status_code == 200
        ids = {r["id"] for r in resp.json()}
        assert regola.id in ids
        assert mondo_b.regola.id not in ids

    def test_sola_lettura_legge_ma_non_scrive(self, client_sola_lettura, regola):
        resp = client_sola_lettura.get("/api/v1/reminder-rules/")
        assert resp.status_code == 200
        resp = client_sola_lettura.patch(
            f"/api/v1/reminder-rules/{regola.id}/", {"attiva": False}, format="json"
        )
        assert resp.status_code == 403

    def test_inquilino_non_accede(self, client_inquilino):
        resp = client_inquilino.get("/api/v1/reminder-rules/")
        assert resp.status_code == 403

    def test_regola_altrui_404(self, client_operativo, mondo_b):
        resp = client_operativo.delete(f"/api/v1/reminder-rules/{mondo_b.regola.id}/")
        assert resp.status_code == 404
        assert ReminderRule.objects.filter(pk=mondo_b.regola.id).exists()
