"""
Test CRUD anagrafiche properties (Fase D — sostituzione admin Django).

Coprono i ViewSet passati da read-only a CRUD completo:
- RoomViewSet: CRUD, delete protetto (assignment) → 409;
- ContractViewSet: CRUD con property assegnata dal server;
- RoomAssignmentViewSet: create/update con full_clean (no-overlap, coerenza
  property) + wizard ``cessione``;
- TenantProfileViewSet: create (con User generato) / update lato gestione +
  action ``invita`` (mailoutbox);
- OwnerBankAccountViewSet: scrittura solo sui propri conti.

Per ogni endpoint: CRUD felice da membro operativo, 403 scritture per
sola_lettura e inquilini, isolamento cross-property (create sull'immobile
attivo, oggetti dell'altro immobile → 404).
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from billing.models import BankTransaction, Receivable
from properties.models import (
    Contract,
    OwnerBankAccount,
    OwnerProfile,
    PropertyMembership,
    Room,
    RoomAssignment,
    TenantProfile,
)

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
def user_owner(immobile, gruppo_proprietari):
    u = User.objects.create_user("crud_owner", email="crud_owner@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    return u


@pytest.fixture
def owner_profile(user_owner):
    return OwnerProfile.objects.create(user=user_owner, nominativo="Owner CRUD")


@pytest.fixture
def client_operativo(user_owner, owner_profile):
    return _client(user_owner)


@pytest.fixture
def client_sola_lettura(immobile, gruppo_proprietari):
    u = User.objects.create_user("crud_readonly", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.SOLA_LETTURA
    )
    return _client(u)


@pytest.fixture
def tenant(immobile, gruppo_inquilini):
    u = User.objects.create_user("crud_inq", email="crud_inq@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    return TenantProfile.objects.create(
        user=u, property=immobile, nominativo="Inquilino Crud",
        giorno_pagamento_affitto=1,
    )


@pytest.fixture
def tenant2(immobile, gruppo_inquilini):
    u = User.objects.create_user("crud_inq2", email="crud_inq2@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    return TenantProfile.objects.create(
        user=u, property=immobile, nominativo="Inquilino Crud Due",
        giorno_pagamento_affitto=5,
    )


@pytest.fixture
def client_inquilino(tenant):
    return _client(tenant.user)


@pytest.fixture
def room(immobile):
    return Room.objects.create(property=immobile, nome="Camera Crud", ordinamento=1)


@pytest.fixture
def assignment(room, tenant):
    return RoomAssignment.objects.create(
        room=room, tenant=tenant,
        valid_from=datetime.date(2025, 1, 1),
        canone_mensile=Decimal("400"),
    )


@pytest.fixture
def contract(immobile):
    return Contract.objects.create(
        property=immobile,
        data_stipula=datetime.date(2024, 9, 15),
        data_decorrenza=datetime.date(2024, 10, 1),
        durata_anni=4,
    )


@pytest.fixture
def conto(owner_profile):
    return OwnerBankAccount.objects.create(
        owner=owner_profile, banca="Banca Crud", intestatario="Owner CRUD",
        iban="IT60X0542811101000000000001",
    )


# --- mondo B (isolamento cross-property) -----------------------------------


@pytest.fixture
def mondo_b(immobile2, gruppo_proprietari, gruppo_inquilini):
    """Un secondo immobile con owner, stanza, inquilino, contratto e conto."""
    from types import SimpleNamespace

    m = SimpleNamespace(property=immobile2)
    m.user_owner = User.objects.create_user(
        "crud_owner_b", email="crud_owner_b@v.it", password="pwd123!"
    )
    m.user_owner.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile2, user=m.user_owner,
        ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
    )
    m.owner = OwnerProfile.objects.create(user=m.user_owner, nominativo="Owner B")
    m.conto = OwnerBankAccount.objects.create(
        owner=m.owner, banca="Banca B", intestatario="Owner B",
        iban="IT60X0542811101000000000002",
    )
    m.room = Room.objects.create(property=immobile2, nome="Camera B", ordinamento=1)
    user_t = User.objects.create_user(
        "crud_inq_b", email="crud_inq_b@v.it", password="pwd123!"
    )
    user_t.groups.add(gruppo_inquilini)
    m.tenant = TenantProfile.objects.create(
        user=user_t, property=immobile2, nominativo="Inquilino B",
        giorno_pagamento_affitto=1,
    )
    m.contract = Contract.objects.create(
        property=immobile2,
        data_stipula=datetime.date(2024, 9, 15),
        data_decorrenza=datetime.date(2024, 10, 1),
        durata_anni=4,
    )
    m.assignment = RoomAssignment.objects.create(
        room=m.room, tenant=m.tenant,
        valid_from=datetime.date(2025, 1, 1),
        canone_mensile=Decimal("300"),
    )
    return m


# ---------------------------------------------------------------------------
# RoomViewSet
# ---------------------------------------------------------------------------


class TestRoomCrud:
    def test_create_atterra_su_immobile_attivo(self, client_operativo, immobile):
        resp = client_operativo.post(
            "/api/v1/rooms/",
            {"nome": "Camera Nuova", "superficie_mq": "14.50", "ordinamento": 3},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        room = Room.objects.get(pk=resp.json()["id"])
        assert room.property_id == immobile.id
        assert room.superficie_mq == Decimal("14.50")
        assert resp.json()["property"] == immobile.id

    def test_update(self, client_operativo, room):
        resp = client_operativo.patch(
            f"/api/v1/rooms/{room.id}/",
            {"nome": "Camera Rinominata", "ordinamento": 9},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        room.refresh_from_db()
        assert room.nome == "Camera Rinominata"
        assert room.ordinamento == 9

    def test_delete_stanza_libera(self, client_operativo, room):
        resp = client_operativo.delete(f"/api/v1/rooms/{room.id}/")
        assert resp.status_code == 204
        assert not Room.objects.filter(pk=room.id).exists()

    def test_delete_stanza_con_assignment_409(self, client_operativo, room, assignment):
        resp = client_operativo.delete(f"/api/v1/rooms/{room.id}/")
        assert resp.status_code == 409
        assert "assegnazioni" in resp.json()["detail"]
        assert Room.objects.filter(pk=room.id).exists()

    def test_sola_lettura_non_scrive(self, client_sola_lettura, room):
        resp = client_sola_lettura.post(
            "/api/v1/rooms/", {"nome": "X"}, format="json"
        )
        assert resp.status_code == 403
        resp = client_sola_lettura.patch(
            f"/api/v1/rooms/{room.id}/", {"nome": "X"}, format="json"
        )
        assert resp.status_code == 403

    def test_inquilino_non_scrive(self, client_inquilino, room, assignment):
        resp = client_inquilino.post("/api/v1/rooms/", {"nome": "X"}, format="json")
        assert resp.status_code == 403
        resp = client_inquilino.delete(f"/api/v1/rooms/{room.id}/")
        assert resp.status_code == 403

    def test_stanza_altrui_404(self, client_operativo, mondo_b):
        resp = client_operativo.patch(
            f"/api/v1/rooms/{mondo_b.room.id}/", {"nome": "Hack"}, format="json"
        )
        assert resp.status_code == 404
        resp = client_operativo.delete(f"/api/v1/rooms/{mondo_b.room.id}/")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# ContractViewSet
# ---------------------------------------------------------------------------


class TestContractCrud:
    def test_create_atterra_su_immobile_attivo(self, client_operativo, immobile):
        resp = client_operativo.post(
            "/api/v1/contracts/",
            {
                "nome": "Contratto 2026",
                "data_stipula": "2026-01-15",
                "data_decorrenza": "2026-02-01",
                "durata_anni": 4,
                "regime_fiscale": "cedolare_10",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        contratto = Contract.objects.get(pk=resp.json()["id"])
        assert contratto.property_id == immobile.id
        assert contratto.nome == "Contratto 2026"

    def test_update(self, client_operativo, contract):
        resp = client_operativo.patch(
            f"/api/v1/contracts/{contract.id}/",
            {"asseverato": True, "termine": "2027-06-30"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        contract.refresh_from_db()
        assert contract.asseverato is True
        assert contract.termine == datetime.date(2027, 6, 30)

    def test_delete(self, client_operativo, contract):
        resp = client_operativo.delete(f"/api/v1/contracts/{contract.id}/")
        assert resp.status_code == 204
        assert not Contract.objects.filter(pk=contract.id).exists()

    def test_pagatore_bollette_altrui_400(self, client_operativo, contract, mondo_b):
        resp = client_operativo.patch(
            f"/api/v1/contracts/{contract.id}/",
            {"default_pagatore_bollette": mondo_b.owner.id},
            format="json",
        )
        assert resp.status_code == 400

    def test_sola_lettura_non_scrive(self, client_sola_lettura, contract):
        resp = client_sola_lettura.patch(
            f"/api/v1/contracts/{contract.id}/", {"asseverato": True}, format="json"
        )
        assert resp.status_code == 403

    def test_inquilino_non_accede(self, client_inquilino, contract):
        resp = client_inquilino.post(
            "/api/v1/contracts/",
            {"data_stipula": "2026-01-15", "data_decorrenza": "2026-02-01",
             "durata_anni": 4},
            format="json",
        )
        assert resp.status_code == 403

    def test_contratto_altrui_404(self, client_operativo, mondo_b):
        resp = client_operativo.delete(f"/api/v1/contracts/{mondo_b.contract.id}/")
        assert resp.status_code == 404
        assert Contract.objects.filter(pk=mondo_b.contract.id).exists()


# ---------------------------------------------------------------------------
# RoomAssignmentViewSet
# ---------------------------------------------------------------------------


class TestRoomAssignmentCrud:
    def test_create_felice(self, client_operativo, room, tenant):
        resp = client_operativo.post(
            "/api/v1/room-assignments/",
            {
                "room": room.id,
                "tenant": tenant.id,
                "valid_from": "2025-01-01",
                "canone_mensile": "420.00",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        creato = RoomAssignment.objects.get(pk=resp.json()["id"])
        assert creato.room_id == room.id
        assert creato.canone_mensile == Decimal("420.00")

    def test_create_overlap_400(self, client_operativo, room, tenant2, assignment):
        # assignment aperto dal 2025-01-01: qualunque nuovo periodo si sovrappone.
        resp = client_operativo.post(
            "/api/v1/room-assignments/",
            {
                "room": room.id,
                "tenant": tenant2.id,
                "valid_from": "2025-06-01",
                "canone_mensile": "450.00",
            },
            format="json",
        )
        assert resp.status_code == 400
        assert "Sovrapposizione" in str(resp.json())

    def test_create_room_altrui_400(self, client_operativo, tenant, mondo_b):
        resp = client_operativo.post(
            "/api/v1/room-assignments/",
            {
                "room": mondo_b.room.id,
                "tenant": tenant.id,
                "valid_from": "2030-01-01",
                "canone_mensile": "400.00",
            },
            format="json",
        )
        assert resp.status_code == 400
        assert "room" in resp.json()

    def test_create_tenant_altrui_400(self, client_operativo, room, mondo_b):
        resp = client_operativo.post(
            "/api/v1/room-assignments/",
            {
                "room": room.id,
                "tenant": mondo_b.tenant.id,
                "valid_from": "2030-01-01",
                "canone_mensile": "400.00",
            },
            format="json",
        )
        assert resp.status_code == 400
        assert "tenant" in resp.json()

    def test_update_chiusura(self, client_operativo, assignment):
        resp = client_operativo.patch(
            f"/api/v1/room-assignments/{assignment.id}/",
            {"valid_to": "2026-06-30"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        assignment.refresh_from_db()
        assert assignment.valid_to == datetime.date(2026, 6, 30)

    def test_update_valid_to_prima_di_valid_from_400(self, client_operativo, assignment):
        resp = client_operativo.patch(
            f"/api/v1/room-assignments/{assignment.id}/",
            {"valid_to": "2024-01-01"},
            format="json",
        )
        assert resp.status_code == 400

    def test_delete_con_receivable_409(self, client_operativo, assignment):
        Receivable.objects.create(
            assignment=assignment,
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(2025, 2, 1),
            competenza_a=datetime.date(2025, 2, 28),
            importo_dovuto=Decimal("400"),
            scadenza=datetime.date(2025, 2, 1),
        )
        resp = client_operativo.delete(f"/api/v1/room-assignments/{assignment.id}/")
        assert resp.status_code == 409
        assert RoomAssignment.objects.filter(pk=assignment.id).exists()

    def test_delete_felice(self, client_operativo, assignment):
        resp = client_operativo.delete(f"/api/v1/room-assignments/{assignment.id}/")
        assert resp.status_code == 204

    def test_sola_lettura_non_scrive(self, client_sola_lettura, room, tenant):
        resp = client_sola_lettura.post(
            "/api/v1/room-assignments/",
            {"room": room.id, "tenant": tenant.id,
             "valid_from": "2025-01-01", "canone_mensile": "400.00"},
            format="json",
        )
        assert resp.status_code == 403

    def test_inquilino_non_scrive(self, client_inquilino, assignment):
        resp = client_inquilino.patch(
            f"/api/v1/room-assignments/{assignment.id}/",
            {"canone_mensile": "1.00"},
            format="json",
        )
        assert resp.status_code == 403

    def test_assignment_altrui_404(self, client_operativo, mondo_b):
        resp = client_operativo.patch(
            f"/api/v1/room-assignments/{mondo_b.assignment.id}/",
            {"canone_mensile": "1.00"},
            format="json",
        )
        assert resp.status_code == 404


class TestCessione:
    def _cessione(self, client, assignment, **extra):
        payload = {
            "data_fine": "2026-06-30",
            "canone_mensile": "450.00",
        }
        payload.update(extra)
        return client.post(
            f"/api/v1/room-assignments/{assignment.id}/cessione/",
            payload,
            format="json",
        )

    def test_chiusura_e_apertura(
        self, client_operativo, immobile, owner_profile, assignment, tenant2
    ):
        # Configura l'anticipante per far scattare anche l'Expense 50%.
        immobile.owner_anticipa_cessioni = owner_profile
        immobile.save()

        resp = self._cessione(
            client_operativo, assignment,
            nuovo_tenant=tenant2.id,
            costo_cessione="200.00",
            data_atto_cessione="2026-06-15",
        )
        assert resp.status_code == 201, resp.content
        data = resp.json()

        assignment.refresh_from_db()
        assert assignment.valid_to == datetime.date(2026, 6, 30)
        assert data["chiuso"]["id"] == assignment.id

        nuovo = RoomAssignment.objects.get(pk=data["nuovo"]["id"])
        assert nuovo.room_id == assignment.room_id
        assert nuovo.tenant_id == tenant2.id
        assert nuovo.valid_from == datetime.date(2026, 7, 1)  # giorno dopo
        assert nuovo.valid_to is None
        assert nuovo.canone_mensile == Decimal("450.00")
        assert nuovo.costo_cessione == Decimal("200.00")
        assert nuovo.data_atto_cessione == datetime.date(2026, 6, 15)

        # Side-effect del costo_cessione (signal): Receivable registrazione 50%.
        reg = Receivable.objects.get(
            assignment=nuovo, causale=Receivable.Causale.REGISTRAZIONE
        )
        assert reg.importo_dovuto == Decimal("100.00")
        assert reg.scadenza == nuovo.valid_from

    def test_senza_costo_cessione_nessun_side_effect(
        self, client_operativo, assignment, tenant2
    ):
        resp = self._cessione(client_operativo, assignment, nuovo_tenant=tenant2.id)
        assert resp.status_code == 201, resp.content
        nuovo_id = resp.json()["nuovo"]["id"]
        assert not Receivable.objects.filter(
            assignment_id=nuovo_id, causale=Receivable.Causale.REGISTRAZIONE
        ).exists()

    def test_nuovo_tenant_altrui_400(self, client_operativo, assignment, mondo_b):
        resp = self._cessione(
            client_operativo, assignment, nuovo_tenant=mondo_b.tenant.id
        )
        assert resp.status_code == 400
        assignment.refresh_from_db()
        assert assignment.valid_to is None  # nulla è stato chiuso

    def test_overlap_rifiutato_e_rollback(
        self, client_operativo, room, tenant, tenant2, assignment
    ):
        # Un assignment successivo già presente sulla stessa stanza:
        # il nuovo (dal 1/7/2026, aperto) si sovrapporrebbe.
        assignment.valid_to = datetime.date(2026, 6, 30)
        assignment.save()
        successivo = RoomAssignment.objects.create(
            room=room, tenant=tenant2,
            valid_from=datetime.date(2026, 8, 1),
            canone_mensile=Decimal("500"),
        )
        # Riapro il corrente per il wizard (fine prima del successivo).
        assignment.valid_to = None
        assignment.save()

        resp = self._cessione(client_operativo, assignment, nuovo_tenant=tenant2.id)
        assert resp.status_code == 400
        assert "Sovrapposizione" in str(resp.json())
        # Rollback: il corrente NON deve risultare chiuso.
        assignment.refresh_from_db()
        assert assignment.valid_to is None
        assert successivo.pk is not None

    def test_data_fine_incoerente_400(self, client_operativo, assignment, tenant2):
        resp = self._cessione(
            client_operativo, assignment,
            nuovo_tenant=tenant2.id, data_fine="2024-01-01",
        )
        assert resp.status_code == 400
        assignment.refresh_from_db()
        assert assignment.valid_to is None

    def test_sola_lettura_403(self, client_sola_lettura, assignment, tenant2):
        resp = self._cessione(client_sola_lettura, assignment, nuovo_tenant=tenant2.id)
        assert resp.status_code == 403

    def test_cessione_su_assignment_altrui_404(self, client_operativo, mondo_b, tenant2):
        resp = self._cessione(client_operativo, mondo_b.assignment, nuovo_tenant=tenant2.id)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TenantProfileViewSet (create/update gestione + invita)
# ---------------------------------------------------------------------------


class TestTenantCrud:
    PAYLOAD = {
        "nominativo": "Mario Rossi",
        "email": "mario.rossi@example.com",
        "telefono": "3331234567",
        "giorno_pagamento_affitto": 5,
        "frequenza_conguagli": "mensile",
        "ciclo_fatturazione": "ingresso",
    }

    def test_create_genera_user(self, client_operativo, immobile):
        resp = client_operativo.post("/api/v1/tenants/", self.PAYLOAD, format="json")
        assert resp.status_code == 201, resp.content
        creato = TenantProfile.objects.get(pk=resp.json()["id"])
        assert creato.property_id == immobile.id
        assert creato.nominativo == "Mario Rossi"
        assert creato.giorno_pagamento_affitto == 5
        assert creato.ciclo_fatturazione == "ingresso"
        user = creato.user
        assert user.username == "mario-rossi"
        assert user.email == "mario.rossi@example.com"
        assert not user.has_usable_password()
        assert user.groups.filter(name="inquilini").exists()

    def test_create_username_con_suffisso_se_occupato(self, client_operativo):
        r1 = client_operativo.post("/api/v1/tenants/", self.PAYLOAD, format="json")
        payload2 = {**self.PAYLOAD, "email": "altro@example.com"}
        r2 = client_operativo.post("/api/v1/tenants/", payload2, format="json")
        assert r1.status_code == 201 and r2.status_code == 201, r2.content
        assert TenantProfile.objects.get(pk=r1.json()["id"]).user.username == "mario-rossi"
        assert TenantProfile.objects.get(pk=r2.json()["id"]).user.username == "mario-rossi2"

    def test_create_senza_email(self, client_operativo):
        payload = {k: v for k, v in self.PAYLOAD.items() if k != "email"}
        resp = client_operativo.post("/api/v1/tenants/", payload, format="json")
        assert resp.status_code == 201, resp.content
        assert TenantProfile.objects.get(pk=resp.json()["id"]).user.email == ""

    def test_update_appena_creato(self, client_operativo):
        resp = client_operativo.post("/api/v1/tenants/", self.PAYLOAD, format="json")
        tenant_id = resp.json()["id"]
        # Senza assignment il tenant non è "attivo": il dettaglio deve
        # comunque essere raggiungibile per update.
        resp = client_operativo.patch(
            f"/api/v1/tenants/{tenant_id}/",
            {"telefono": "3400000000", "email": "nuova@example.com"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        aggiornato = TenantProfile.objects.get(pk=tenant_id)
        assert aggiornato.telefono == "3400000000"
        assert aggiornato.user.email == "nuova@example.com"

    def test_sola_lettura_non_crea(self, client_sola_lettura):
        resp = client_sola_lettura.post("/api/v1/tenants/", self.PAYLOAD, format="json")
        assert resp.status_code == 403

    def test_inquilino_non_crea_ne_modifica(self, client_inquilino, tenant):
        resp = client_inquilino.post("/api/v1/tenants/", self.PAYLOAD, format="json")
        assert resp.status_code == 403
        resp = client_inquilino.patch(
            f"/api/v1/tenants/{tenant.id}/", {"telefono": "1"}, format="json"
        )
        assert resp.status_code == 403

    def test_me_resta_self_service(self, client_inquilino, tenant):
        resp = client_inquilino.patch(
            "/api/v1/tenants/me/", {"telefono": "3479999999"}, format="json"
        )
        assert resp.status_code == 200, resp.content
        tenant.refresh_from_db()
        assert tenant.telefono == "3479999999"

    def test_update_tenant_altrui_404(self, client_operativo, mondo_b):
        resp = client_operativo.patch(
            f"/api/v1/tenants/{mondo_b.tenant.id}/", {"telefono": "1"}, format="json"
        )
        assert resp.status_code == 404


class TestTenantInvita:
    def test_crea_e_invita(self, client_operativo, mailoutbox):
        resp = client_operativo.post(
            "/api/v1/tenants/", TestTenantCrud.PAYLOAD, format="json"
        )
        assert resp.status_code == 201, resp.content
        tenant_id = resp.json()["id"]

        resp = client_operativo.post(f"/api/v1/tenants/{tenant_id}/invita/")
        assert resp.status_code == 200, resp.content
        esito = resp.json()
        assert esito["esito"] == "inviato"
        assert esito["email"] == "mario.rossi@example.com"
        assert len(mailoutbox) == 1
        msg = mailoutbox[0]
        assert msg.to == ["mario.rossi@example.com"]
        assert "mario-rossi" in msg.body
        assert "/imposta-password/" in msg.body

    def test_invita_senza_email_400(self, client_operativo, mailoutbox):
        payload = {k: v for k, v in TestTenantCrud.PAYLOAD.items() if k != "email"}
        resp = client_operativo.post("/api/v1/tenants/", payload, format="json")
        tenant_id = resp.json()["id"]
        resp = client_operativo.post(f"/api/v1/tenants/{tenant_id}/invita/")
        assert resp.status_code == 400
        assert len(mailoutbox) == 0

    def test_sola_lettura_non_invita(self, client_sola_lettura, tenant, mailoutbox):
        resp = client_sola_lettura.post(f"/api/v1/tenants/{tenant.id}/invita/")
        assert resp.status_code == 403
        assert len(mailoutbox) == 0

    def test_invita_tenant_altrui_404(self, client_operativo, mondo_b, mailoutbox):
        resp = client_operativo.post(f"/api/v1/tenants/{mondo_b.tenant.id}/invita/")
        assert resp.status_code == 404
        assert len(mailoutbox) == 0


# ---------------------------------------------------------------------------
# OwnerBankAccountViewSet
# ---------------------------------------------------------------------------


class TestOwnerBankAccountCrud:
    PAYLOAD = {
        "banca": "Banca Nuova",
        "intestatario": "Owner CRUD",
        "iban": "IT60X0542811101000000000009",
    }

    def test_create_forza_owner_richiedente(self, client_operativo, owner_profile, mondo_b):
        # Anche passando l'owner di B nel payload, il conto è del richiedente.
        resp = client_operativo.post(
            "/api/v1/bank-accounts/",
            {**self.PAYLOAD, "owner": mondo_b.owner.id},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        conto = OwnerBankAccount.objects.get(pk=resp.json()["id"])
        assert conto.owner_id == owner_profile.id

    def test_update_proprio_conto(self, client_operativo, conto):
        resp = client_operativo.patch(
            f"/api/v1/bank-accounts/{conto.id}/", {"attivo": False}, format="json"
        )
        assert resp.status_code == 200, resp.content
        conto.refresh_from_db()
        assert conto.attivo is False

    def test_delete_proprio_conto(self, client_operativo, conto):
        resp = client_operativo.delete(f"/api/v1/bank-accounts/{conto.id}/")
        assert resp.status_code == 204

    def test_delete_conto_con_movimenti_409(self, client_operativo, conto):
        BankTransaction.objects.create(
            data=datetime.date(2026, 1, 1), descrizione="Test",
            importo=Decimal("100"), owner_account=conto,
        )
        resp = client_operativo.delete(f"/api/v1/bank-accounts/{conto.id}/")
        assert resp.status_code == 409
        assert OwnerBankAccount.objects.filter(pk=conto.id).exists()

    def test_conto_di_altro_membro_non_modificabile(
        self, immobile, gruppo_proprietari, conto, user_owner
    ):
        """Un co-membro vede il conto altrui ma non può toccarlo (403)."""
        u = User.objects.create_user("crud_owner2", password="pwd123!")
        u.groups.add(gruppo_proprietari)
        PropertyMembership.objects.create(
            property=immobile, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
        )
        OwnerProfile.objects.create(user=u, nominativo="Owner Due")
        client2 = _client(u)

        resp = client2.get(f"/api/v1/bank-accounts/{conto.id}/")
        assert resp.status_code == 200  # visibilità fra co-membri

        resp = client2.patch(
            f"/api/v1/bank-accounts/{conto.id}/", {"attivo": False}, format="json"
        )
        assert resp.status_code == 403
        resp = client2.delete(f"/api/v1/bank-accounts/{conto.id}/")
        assert resp.status_code == 403
        assert OwnerBankAccount.objects.filter(pk=conto.id, attivo=True).exists()

    def test_membro_senza_owner_profile_non_crea(self, immobile, gruppo_proprietari):
        u = User.objects.create_user("crud_gestore", password="pwd123!")
        u.groups.add(gruppo_proprietari)
        PropertyMembership.objects.create(
            property=immobile, user=u, ruolo=PropertyMembership.Ruolo.GESTORE
        )
        resp = _client(u).post("/api/v1/bank-accounts/", self.PAYLOAD, format="json")
        assert resp.status_code == 403

    def test_sola_lettura_non_scrive(self, client_sola_lettura, conto):
        resp = client_sola_lettura.post(
            "/api/v1/bank-accounts/", self.PAYLOAD, format="json"
        )
        assert resp.status_code == 403

    def test_conto_altrui_404(self, client_operativo, mondo_b):
        resp = client_operativo.patch(
            f"/api/v1/bank-accounts/{mondo_b.conto.id}/", {"attivo": False},
            format="json",
        )
        assert resp.status_code == 404
