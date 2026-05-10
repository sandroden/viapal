"""
Test API per l'app properties.

Coprono:
- Smoke test viewset (proprietario ottiene 200 con risultati)
- Filtering object-level per inquilino
- Accesso negato a risorse altrui
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from properties.models import Contract, OwnerBankAccount, OwnerProfile, Room, RoomAssignment, TenantProfile


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
def user_prop(db, gruppo_proprietari):
    u = User.objects.create_user("prop_test", email="p@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    return u


@pytest.fixture
def user_inq_1(db, gruppo_inquilini):
    u = User.objects.create_user("inq_test_1", email="i1@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    return u


@pytest.fixture
def user_inq_2(db, gruppo_inquilini):
    u = User.objects.create_user("inq_test_2", email="i2@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    return u


@pytest.fixture
def owner_profile(db, user_prop):
    return OwnerProfile.objects.create(user=user_prop, nominativo="Proprietario Test")


@pytest.fixture
def tenant_1(db, user_inq_1):
    return TenantProfile.objects.create(
        user=user_inq_1, nominativo="Inquilino Uno", giorno_pagamento_affitto=1
    )


@pytest.fixture
def tenant_2(db, user_inq_2):
    return TenantProfile.objects.create(
        user=user_inq_2, nominativo="Inquilino Due", giorno_pagamento_affitto=5
    )


@pytest.fixture
def room_1(db):
    return Room.objects.create(nome="Camera Test A", ordinamento=10)


@pytest.fixture
def room_2(db):
    return Room.objects.create(nome="Camera Test B", ordinamento=11)


@pytest.fixture
def assignment_1(db, room_1, tenant_1):
    return RoomAssignment.objects.create(
        room=room_1,
        tenant=tenant_1,
        valid_from=datetime.date(2024, 9, 1),
        canone_mensile=Decimal("400"),
        deposito_versato=Decimal("400"),
    )


@pytest.fixture
def assignment_2(db, room_2, tenant_2):
    return RoomAssignment.objects.create(
        room=room_2,
        tenant=tenant_2,
        valid_from=datetime.date(2024, 9, 1),
        canone_mensile=Decimal("380"),
        deposito_versato=Decimal("380"),
    )


@pytest.fixture
def contract(db):
    return Contract.objects.create(
        data_stipula=datetime.date(2024, 9, 15),
        data_decorrenza=datetime.date(2024, 9, 20),
        durata_anni=4,
    )


@pytest.fixture
def bank_account(db, owner_profile):
    return OwnerBankAccount.objects.create(
        owner=owner_profile,
        banca="Banca Test",
        intestatario="Proprietario Test",
        iban="IT60X0542811101000000000001",
    )


@pytest.fixture
def client_prop(api_client, user_prop):
    api_client.force_login(user_prop)
    return api_client


@pytest.fixture
def client_inq_1(api_client, user_inq_1):
    api_client.force_login(user_inq_1)
    return api_client


@pytest.fixture
def client_inq_2(api_client, user_inq_2):
    api_client.force_login(user_inq_2)
    return api_client


# ---------------------------------------------------------------------------
# Test OwnerProfileViewSet
# ---------------------------------------------------------------------------


class TestOwnerProfileViewSet:
    def test_proprietario_vede_lista(self, client_prop, owner_profile):
        resp = client_prop.get("/api/v1/owners/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_inquilino_non_autorizzato(self, client_inq_1):
        resp = client_inq_1.get("/api/v1/owners/")
        assert resp.status_code == 403

    def test_anonimo_non_autorizzato(self):
        client = APIClient()
        resp = client.get("/api/v1/owners/")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test TenantProfileViewSet
# ---------------------------------------------------------------------------


class TestTenantProfileViewSet:
    def test_proprietario_vede_attivi_default(
        self, client_prop, tenant_1, tenant_2, assignment_1, assignment_2
    ):
        resp = client_prop.get("/api/v1/tenants/")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.json()]
        assert tenant_1.id in ids
        assert tenant_2.id in ids

    def test_proprietario_default_esclude_storici(
        self, client_prop, tenant_1, tenant_2, assignment_1
    ):
        # tenant_2 senza assignment attivo → non deve comparire di default
        resp = client_prop.get("/api/v1/tenants/")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.json()]
        assert tenant_1.id in ids
        assert tenant_2.id not in ids

    def test_proprietario_solo_attivi_zero_include_tutti(
        self, client_prop, tenant_1, tenant_2, assignment_1
    ):
        resp = client_prop.get("/api/v1/tenants/?solo_attivi=0")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.json()]
        assert tenant_1.id in ids
        assert tenant_2.id in ids

    def test_proprietario_assignment_chiuso_non_attivo(
        self, client_prop, tenant_1, tenant_2, assignment_1, assignment_2
    ):
        # Chiudo assignment_2 nel passato → tenant_2 non più attivo
        assignment_2.valid_to = datetime.date(2024, 12, 31)
        assignment_2.save()
        resp = client_prop.get("/api/v1/tenants/")
        ids = [t["id"] for t in resp.json()]
        assert tenant_1.id in ids
        assert tenant_2.id not in ids

    def test_proprietario_filtra_per_anno(
        self, client_prop, tenant_1, tenant_2, room_1, room_2
    ):
        # tenant_1: assignment chiuso nel 2024 → presente solo nel 2024
        RoomAssignment.objects.create(
            room=room_1,
            tenant=tenant_1,
            valid_from=datetime.date(2024, 3, 1),
            valid_to=datetime.date(2024, 12, 31),
            canone_mensile=Decimal("400"),
            deposito_versato=Decimal("400"),
        )
        # tenant_2: assignment aperto dal 2025 → presente solo dal 2025
        RoomAssignment.objects.create(
            room=room_2,
            tenant=tenant_2,
            valid_from=datetime.date(2025, 6, 1),
            canone_mensile=Decimal("380"),
            deposito_versato=Decimal("380"),
        )

        resp_2024 = client_prop.get("/api/v1/tenants/?anno=2024")
        ids_2024 = [t["id"] for t in resp_2024.json()]
        assert tenant_1.id in ids_2024
        assert tenant_2.id not in ids_2024

        resp_2025 = client_prop.get("/api/v1/tenants/?anno=2025")
        ids_2025 = [t["id"] for t in resp_2025.json()]
        assert tenant_1.id not in ids_2025
        assert tenant_2.id in ids_2025

    def test_proprietario_anno_invalido_fallback_a_solo_attivi(
        self, client_prop, tenant_1, assignment_1
    ):
        # Anno non parsabile → comportamento default (solo attivi oggi)
        resp = client_prop.get("/api/v1/tenants/?anno=pippo")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.json()]
        assert tenant_1.id in ids

    def test_inquilino_vede_solo_se_stesso(self, client_inq_1, tenant_1, tenant_2):
        resp = client_inq_1.get("/api/v1/tenants/")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.json()]
        assert tenant_1.id in ids
        assert tenant_2.id not in ids

    def test_inquilino_detail_se_stesso(self, client_inq_1, tenant_1):
        resp = client_inq_1.get(f"/api/v1/tenants/{tenant_1.id}/")
        assert resp.status_code == 200

    def test_inquilino_non_vede_altro(self, client_inq_1, tenant_2):
        resp = client_inq_1.get(f"/api/v1/tenants/{tenant_2.id}/")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test RoomViewSet
# ---------------------------------------------------------------------------


class TestRoomViewSet:
    def test_proprietario_vede_tutte(self, client_prop, room_1, room_2):
        resp = client_prop.get("/api/v1/rooms/")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert room_1.id in ids
        assert room_2.id in ids

    def test_inquilino_vede_solo_propria(self, client_inq_1, assignment_1, room_1, room_2):
        resp = client_inq_1.get("/api/v1/rooms/")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert room_1.id in ids
        assert room_2.id not in ids


# ---------------------------------------------------------------------------
# Test RoomAssignmentViewSet
# ---------------------------------------------------------------------------


class TestRoomAssignmentViewSet:
    def test_proprietario_vede_tutti(self, client_prop, assignment_1, assignment_2):
        resp = client_prop.get("/api/v1/room-assignments/")
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()]
        assert assignment_1.id in ids
        assert assignment_2.id in ids

    def test_inquilino_vede_solo_propri(self, client_inq_1, assignment_1, assignment_2):
        resp = client_inq_1.get("/api/v1/room-assignments/")
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()]
        assert assignment_1.id in ids
        assert assignment_2.id not in ids


# ---------------------------------------------------------------------------
# Test ContractViewSet
# ---------------------------------------------------------------------------


class TestContractViewSet:
    def test_proprietario_vede_contratto(self, client_prop, contract):
        resp = client_prop.get("/api/v1/contracts/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_inquilino_non_autorizzato(self, client_inq_1):
        resp = client_inq_1.get("/api/v1/contracts/")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test OwnerBankAccountViewSet
# ---------------------------------------------------------------------------


class TestOwnerBankAccountViewSet:
    def test_proprietario_vede_conti(self, client_prop, bank_account):
        resp = client_prop.get("/api/v1/bank-accounts/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_inquilino_non_autorizzato(self, client_inq_1):
        resp = client_inq_1.get("/api/v1/bank-accounts/")
        assert resp.status_code == 403
