"""
Test API multiproprietà: PropertyViewSet (CRUD, membri, quote, inviti)
e /api/auth/user/ esteso con properties/default_property_id.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from properties.models import (
    OwnerProfile,
    OwnershipShare,
    PropertyMembership,
    Room,
    TenantProfile,
)
from properties.models.owner import quote_attive_at


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    return APIClient(enforce_csrf_checks=False)


@pytest.fixture
def gruppo_proprietari(db):
    grp, _ = Group.objects.get_or_create(name="proprietari")
    return grp


@pytest.fixture
def gruppo_inquilini(db):
    grp, _ = Group.objects.get_or_create(name="inquilini")
    return grp


@pytest.fixture
def user_prop(db, gruppo_proprietari, immobile):
    """Proprietario dell'immobile di test."""
    u = User.objects.create_user("prop_a", email="prop_a@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
    )
    return u


@pytest.fixture
def owner_profile(db, user_prop):
    return OwnerProfile.objects.create(user=user_prop, nominativo="Prop A")


@pytest.fixture
def user_prop2(db, gruppo_proprietari, immobile):
    """Secondo proprietario dell'immobile (per quote/ultimo-proprietario)."""
    u = User.objects.create_user("prop_b", email="prop_b@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
    )
    return u


@pytest.fixture
def owner_profile2(db, user_prop2):
    return OwnerProfile.objects.create(user=user_prop2, nominativo="Prop B")


@pytest.fixture
def user_gestore(db, gruppo_proprietari, immobile):
    """Gestore (membership senza quota) dell'immobile di test."""
    u = User.objects.create_user("gest", email="gest@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.GESTORE,
    )
    return u


@pytest.fixture
def user_altro(db, gruppo_proprietari, immobile2):
    """Proprietario di un ALTRO immobile: non membro dell'immobile di test."""
    u = User.objects.create_user("altro", email="altro@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile2, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
    )
    return u


@pytest.fixture
def user_inq(db, gruppo_inquilini, immobile):
    """Inquilino: nessuna membership, solo TenantProfile."""
    u = User.objects.create_user("inq", email="inq@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    TenantProfile.objects.create(
        user=u, property=immobile, nominativo="Inquilino",
        giorno_pagamento_affitto=1,
    )
    return u


@pytest.fixture
def client_prop(api_client, user_prop):
    api_client.force_login(user_prop)
    return api_client


@pytest.fixture
def client_gestore(api_client, user_gestore):
    api_client.force_login(user_gestore)
    return api_client


@pytest.fixture
def client_inq(api_client, user_inq):
    api_client.force_login(user_inq)
    return api_client


@pytest.fixture
def client_altro(api_client, user_altro):
    api_client.force_login(user_altro)
    return api_client


def _membership_id(prop, user):
    return PropertyMembership.objects.get(property=prop, user=user).pk


# ---------------------------------------------------------------------------
# Lista / retrieve
# ---------------------------------------------------------------------------


class TestPropertyList:
    def test_membro_vede_solo_i_suoi_immobili(
        self, client_prop, immobile, immobile2, user_altro
    ):
        resp = client_prop.get("/api/v1/properties/")
        assert resp.status_code == 200
        dati = resp.json()
        assert [p["id"] for p in dati] == [immobile.id]
        assert dati[0]["mio_ruolo"] == "proprietario"

    def test_inquilino_senza_membership_lista_vuota(self, client_inq, immobile):
        resp = client_inq.get("/api/v1/properties/")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestPropertyCreate:
    def test_membro_crea_default_proprietario_con_quota(self, client_prop, user_prop):
        resp = client_prop.post(
            "/api/v1/properties/",
            {"nome": "Nuova Casa", "indirizzo": "Via Nuova 3"},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        prop_id = resp.json()["id"]
        m = PropertyMembership.objects.get(property_id=prop_id, user=user_prop)
        assert m.ruolo == PropertyMembership.Ruolo.PROPRIETARIO
        # OwnerProfile creato al volo e quota unica 1.0 aperta da oggi
        profilo = OwnerProfile.objects.get(user=user_prop)
        share = OwnershipShare.objects.get(property_id=prop_id)
        assert share.owner == profilo
        assert share.quota == Decimal("1.0000")
        assert share.valid_from == datetime.date.today()
        assert share.valid_to is None
        assert resp.json()["mio_ruolo"] == "proprietario"

    def test_membro_crea_come_gestore_senza_quota(self, client_prop, user_prop):
        resp = client_prop.post(
            "/api/v1/properties/",
            {"nome": "Casa Gestita", "ruolo_creatore": "gestore"},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        prop_id = resp.json()["id"]
        m = PropertyMembership.objects.get(property_id=prop_id, user=user_prop)
        assert m.ruolo == PropertyMembership.Ruolo.GESTORE
        assert not OwnershipShare.objects.filter(property_id=prop_id).exists()

    def test_ruolo_creatore_non_valido_400(self, client_prop):
        resp = client_prop.post(
            "/api/v1/properties/",
            {"nome": "Casa X", "ruolo_creatore": "sola_lettura"},
            format="json",
        )
        assert resp.status_code == 400

    def test_utente_senza_membership_non_crea(self, client_inq):
        resp = client_inq.post(
            "/api/v1/properties/", {"nome": "Abusiva"}, format="json"
        )
        assert resp.status_code == 403
        assert not PropertyMembership.objects.filter(user__username="inq").exists()


# ---------------------------------------------------------------------------
# Update / delete
# ---------------------------------------------------------------------------


class TestPropertyUpdateDelete:
    def test_patch_da_gestore_ok(self, client_gestore, immobile):
        resp = client_gestore.patch(
            f"/api/v1/properties/{immobile.id}/",
            {"nome": "Rinominato"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        immobile.refresh_from_db()
        assert immobile.nome == "Rinominato"

    def test_patch_da_non_membro_404(self, client_altro, immobile):
        resp = client_altro.patch(
            f"/api/v1/properties/{immobile.id}/", {"nome": "Hack"}, format="json"
        )
        # Non membro: l'immobile non è nel suo queryset (non se ne rivela
        # l'esistenza).
        assert resp.status_code == 404
        immobile.refresh_from_db()
        assert immobile.nome != "Hack"

    def test_delete_da_gestore_403(self, client_gestore, immobile):
        resp = client_gestore.delete(f"/api/v1/properties/{immobile.id}/")
        assert resp.status_code == 403

    def test_delete_da_proprietario_immobile_vuoto_204(self, client_prop, immobile):
        resp = client_prop.delete(f"/api/v1/properties/{immobile.id}/")
        assert resp.status_code == 204
        from properties.models import Property

        assert not Property.objects.filter(pk=immobile.pk).exists()

    def test_delete_immobile_con_stanze_409(self, client_prop, immobile):
        Room.objects.create(property=immobile, nome="Camera", ordinamento=1)
        resp = client_prop.delete(f"/api/v1/properties/{immobile.id}/")
        assert resp.status_code == 409
        from properties.models import Property

        assert Property.objects.filter(pk=immobile.pk).exists()


# ---------------------------------------------------------------------------
# Membri
# ---------------------------------------------------------------------------


class TestMembri:
    def test_get_membri_da_membro(self, client_gestore, immobile, user_prop, user_gestore):
        resp = client_gestore.get(f"/api/v1/properties/{immobile.id}/membri/")
        assert resp.status_code == 200
        per_user = {m["user"]: m["ruolo"] for m in resp.json()}
        assert per_user == {
            user_prop.id: "proprietario",
            user_gestore.id: "gestore",
        }

    def test_post_membro_da_proprietario(self, client_prop, immobile, user_altro):
        resp = client_prop.post(
            f"/api/v1/properties/{immobile.id}/membri/",
            {"user": user_altro.id, "ruolo": "sola_lettura"},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        m = PropertyMembership.objects.get(property=immobile, user=user_altro)
        assert m.ruolo == PropertyMembership.Ruolo.SOLA_LETTURA
        assert m.invitato_da_id is not None

    def test_post_membro_da_gestore_403(self, client_gestore, immobile, user_altro):
        resp = client_gestore.post(
            f"/api/v1/properties/{immobile.id}/membri/",
            {"user": user_altro.id, "ruolo": "gestore"},
            format="json",
        )
        assert resp.status_code == 403
        assert not PropertyMembership.objects.filter(
            property=immobile, user=user_altro
        ).exists()

    def test_delete_ultimo_proprietario_409(self, client_prop, immobile, user_prop):
        mid = _membership_id(immobile, user_prop)
        resp = client_prop.delete(f"/api/v1/properties/{immobile.id}/membri/{mid}/")
        assert resp.status_code == 409
        assert PropertyMembership.objects.filter(pk=mid).exists()

    def test_delete_proprietario_non_ultimo_204(
        self, client_prop, immobile, user_prop2
    ):
        mid = _membership_id(immobile, user_prop2)
        resp = client_prop.delete(f"/api/v1/properties/{immobile.id}/membri/{mid}/")
        assert resp.status_code == 204
        assert not PropertyMembership.objects.filter(pk=mid).exists()

    def test_patch_degradazione_ultimo_proprietario_409(
        self, client_prop, immobile, user_prop
    ):
        mid = _membership_id(immobile, user_prop)
        resp = client_prop.patch(
            f"/api/v1/properties/{immobile.id}/membri/{mid}/",
            {"ruolo": "gestore"},
            format="json",
        )
        assert resp.status_code == 409
        assert PropertyMembership.objects.get(pk=mid).ruolo == "proprietario"

    def test_patch_promozione_gestore_ok(self, client_prop, immobile, user_gestore):
        mid = _membership_id(immobile, user_gestore)
        resp = client_prop.patch(
            f"/api/v1/properties/{immobile.id}/membri/{mid}/",
            {"ruolo": "proprietario"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        assert PropertyMembership.objects.get(pk=mid).ruolo == "proprietario"


# ---------------------------------------------------------------------------
# Quote
# ---------------------------------------------------------------------------


class TestQuote:
    def test_post_nuovo_assetto_chiude_e_sostituisce(
        self, client_prop, immobile, user_prop, user_prop2,
        owner_profile, owner_profile2,
    ):
        # Assetto iniziale: 100% al primo proprietario dal 2025.
        OwnershipShare.objects.create(
            property=immobile, owner=owner_profile,
            quota=Decimal("1.0000"), valid_from=datetime.date(2025, 1, 1),
        )
        nuovo_dal = datetime.date(2026, 1, 1)
        resp = client_prop.post(
            f"/api/v1/properties/{immobile.id}/quote/",
            {
                "valid_from": nuovo_dal.isoformat(),
                "quote": [
                    {"user": user_prop.id, "quota": "0.5"},
                    {"user": user_prop2.id, "quota": "0.5"},
                ],
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        assert len(resp.json()) == 2
        # La vecchia quota è stata chiusa a valid_from del nuovo assetto.
        vecchia = OwnershipShare.objects.get(
            property=immobile, valid_from=datetime.date(2025, 1, 1)
        )
        assert vecchia.valid_to == nuovo_dal
        # quote_attive_at riflette il nuovo assetto...
        attive = quote_attive_at(immobile, datetime.date(2026, 6, 1))
        assert attive == {
            owner_profile: Decimal("0.5"),
            owner_profile2: Decimal("0.5"),
        }
        # ...mentre prima del cambio vale ancora il vecchio.
        prima = quote_attive_at(immobile, datetime.date(2025, 6, 1))
        assert prima == {owner_profile: Decimal("1")}

    def test_post_quote_somma_diversa_da_uno_400(
        self, client_prop, immobile, user_prop, user_prop2,
        owner_profile, owner_profile2,
    ):
        resp = client_prop.post(
            f"/api/v1/properties/{immobile.id}/quote/",
            {
                "valid_from": "2026-01-01",
                "quote": [
                    {"user": user_prop.id, "quota": "0.5"},
                    {"user": user_prop2.id, "quota": "0.6"},
                ],
            },
            format="json",
        )
        assert resp.status_code == 400
        assert not OwnershipShare.objects.filter(property=immobile).exists()

    def test_post_quote_user_non_proprietario_400(
        self, client_prop, immobile, user_gestore, owner_profile
    ):
        resp = client_prop.post(
            f"/api/v1/properties/{immobile.id}/quote/",
            {
                "valid_from": "2026-01-01",
                "quote": [{"user": user_gestore.id, "quota": "1.0"}],
            },
            format="json",
        )
        assert resp.status_code == 400
        assert not OwnershipShare.objects.filter(property=immobile).exists()


# ---------------------------------------------------------------------------
# Inviti
# ---------------------------------------------------------------------------


class TestInviti:
    def test_invito_email_nuova_crea_utente_e_manda_link(
        self, client_prop, immobile, mailoutbox
    ):
        resp = client_prop.post(
            f"/api/v1/properties/{immobile.id}/inviti/",
            {"email": "nuovo@v.it", "ruolo": "gestore", "nominativo": "Mario Rossi"},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        assert resp.json()["creato"] is True
        nuovo = User.objects.get(email="nuovo@v.it")
        assert nuovo.username == "nuovo@v.it"
        assert not nuovo.has_usable_password()
        assert nuovo.first_name == "Mario" and nuovo.last_name == "Rossi"
        m = PropertyMembership.objects.get(property=immobile, user=nuovo)
        assert m.ruolo == PropertyMembership.Ruolo.GESTORE
        # Email con link imposta-password
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ["nuovo@v.it"]
        assert "/imposta-password/" in mailoutbox[0].body
        # Gestore: niente OwnerProfile
        assert not OwnerProfile.objects.filter(user=nuovo).exists()

    def test_invito_ruolo_proprietario_crea_owner_profile(
        self, client_prop, immobile, mailoutbox
    ):
        resp = client_prop.post(
            f"/api/v1/properties/{immobile.id}/inviti/",
            {"email": "socio@v.it", "ruolo": "proprietario", "nominativo": "Socio Uno"},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        nuovo = User.objects.get(email="socio@v.it")
        assert OwnerProfile.objects.get(user=nuovo).nominativo == "Socio Uno"
        assert PropertyMembership.objects.filter(
            property=immobile, user=nuovo,
            ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
        ).exists()

    def test_invito_email_esistente_aggiunge_membership_senza_link(
        self, client_prop, immobile, user_altro, mailoutbox
    ):
        resp = client_prop.post(
            f"/api/v1/properties/{immobile.id}/inviti/",
            {"email": user_altro.email, "ruolo": "sola_lettura"},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        assert resp.json()["creato"] is False
        assert PropertyMembership.objects.filter(
            property=immobile, user=user_altro,
            ruolo=PropertyMembership.Ruolo.SOLA_LETTURA,
        ).exists()
        # Ha già le credenziali: la mail non contiene il link imposta-password.
        assert len(mailoutbox) == 1
        assert "/imposta-password/" not in mailoutbox[0].body

    def test_invito_doppio_400(self, client_prop, immobile, mailoutbox):
        payload = {"email": "doppio@v.it", "ruolo": "gestore"}
        resp1 = client_prop.post(
            f"/api/v1/properties/{immobile.id}/inviti/", payload, format="json"
        )
        assert resp1.status_code == 201
        resp2 = client_prop.post(
            f"/api/v1/properties/{immobile.id}/inviti/", payload, format="json"
        )
        assert resp2.status_code == 400
        assert "membro" in resp2.json()["detail"]
        # Un solo utente e una sola email inviata.
        assert User.objects.filter(email="doppio@v.it").count() == 1
        assert len(mailoutbox) == 1

    def test_invito_da_gestore_403(self, client_gestore, immobile, mailoutbox):
        resp = client_gestore.post(
            f"/api/v1/properties/{immobile.id}/inviti/",
            {"email": "x@v.it", "ruolo": "gestore"},
            format="json",
        )
        assert resp.status_code == 403
        assert not User.objects.filter(email="x@v.it").exists()
        assert len(mailoutbox) == 0


# ---------------------------------------------------------------------------
# /api/auth/user/ esteso
# ---------------------------------------------------------------------------


class TestAuthUser:
    def test_user_con_due_membership_vede_properties_e_default(
        self, api_client, gruppo_proprietari, immobile, immobile2
    ):
        u = User.objects.create_user("multi", email="multi@v.it", password="pwd123!")
        u.groups.add(gruppo_proprietari)
        PropertyMembership.objects.create(
            property=immobile, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
        )
        PropertyMembership.objects.create(
            property=immobile2, user=u, ruolo=PropertyMembership.Ruolo.GESTORE,
        )
        api_client.force_login(u)
        resp = api_client.get("/api/auth/user/")
        assert resp.status_code == 200
        dati = resp.json()
        per_id = {p["id"]: p for p in dati["properties"]}
        assert set(per_id) == {immobile.id, immobile2.id}
        assert per_id[immobile.id]["ruolo"] == "proprietario"
        assert per_id[immobile.id]["nome"] == immobile.nome
        assert per_id[immobile2.id]["ruolo"] == "gestore"
        # Default = prima property accessibile (ordinamento per nome).
        assert dati["default_property_id"] == immobile.id
        assert dati["role"] == "proprietario"

    def test_inquilino_senza_membership_properties_vuote(self, client_inq):
        resp = client_inq.get("/api/auth/user/")
        assert resp.status_code == 200
        dati = resp.json()
        assert dati["properties"] == []
        assert dati["default_property_id"] is None
        assert dati["role"] == "inquilino"
