"""
Test API per l'app accounting.

Coprono:
- Smoke test viewset ledger e inter-owner
- Accesso negato agli inquilini
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from accounting.models import InterOwnerEntry, OwnerLedgerEntry
from properties.models import OwnerProfile


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
def user_prop_1(db, gruppo_proprietari):
    u = User.objects.create_user("acc_prop1", email="ap1@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    return u


@pytest.fixture
def user_prop_2(db, gruppo_proprietari):
    u = User.objects.create_user("acc_prop2", email="ap2@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    return u


@pytest.fixture
def user_inq(db, gruppo_inquilini):
    u = User.objects.create_user("acc_inq", email="ai@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    return u


@pytest.fixture
def owner_1(db, user_prop_1):
    return OwnerProfile.objects.create(user=user_prop_1, nominativo="Proprietario ACC 1")


@pytest.fixture
def owner_2(db, user_prop_2):
    return OwnerProfile.objects.create(user=user_prop_2, nominativo="Proprietario ACC 2")


@pytest.fixture
def ledger_entry(db, owner_1):
    return OwnerLedgerEntry.objects.create(
        owner=owner_1,
        data=datetime.date(2026, 1, 15),
        descrizione="Incasso affitto gen 2026",
        importo=Decimal("400.00"),
        tipo="incasso_affitto",
    )


@pytest.fixture
def inter_entry(db, owner_1, owner_2):
    return InterOwnerEntry.objects.create(
        owner_da=owner_1,
        owner_a=owner_2,
        data=datetime.date(2026, 2, 1),
        importo=Decimal("150.00"),
        descrizione="Rimborso IMU",
    )


@pytest.fixture
def client_prop(api_client, user_prop_1):
    api_client.force_login(user_prop_1)
    return api_client


@pytest.fixture
def client_inq(api_client, user_inq):
    api_client.force_login(user_inq)
    return api_client


# ---------------------------------------------------------------------------
# Test OwnerLedgerEntryViewSet
# ---------------------------------------------------------------------------


class TestOwnerLedgerEntryViewSet:
    def test_proprietario_vede_lista(self, client_prop, ledger_entry):
        resp = client_prop.get("/api/v1/ledger-entries/")
        assert resp.status_code == 200
        ids = [e["id"] for e in resp.json()]
        assert ledger_entry.id in ids

    def test_proprietario_vede_dettaglio(self, client_prop, ledger_entry):
        resp = client_prop.get(f"/api/v1/ledger-entries/{ledger_entry.id}/")
        assert resp.status_code == 200
        assert resp.json()["importo"] == "400.00"

    def test_inquilino_non_accede(self, client_inq):
        resp = client_inq.get("/api/v1/ledger-entries/")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test InterOwnerEntryViewSet
# ---------------------------------------------------------------------------


class TestInterOwnerEntryViewSet:
    def test_proprietario_vede_lista(self, client_prop, inter_entry):
        resp = client_prop.get("/api/v1/inter-owner-entries/")
        assert resp.status_code == 200
        ids = [e["id"] for e in resp.json()]
        assert inter_entry.id in ids

    def test_proprietario_vede_dettaglio(self, client_prop, inter_entry):
        resp = client_prop.get(f"/api/v1/inter-owner-entries/{inter_entry.id}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["owner_da_nominativo"] == "Proprietario ACC 1"
        assert data["owner_a_nominativo"] == "Proprietario ACC 2"

    def test_inquilino_non_accede(self, client_inq):
        resp = client_inq.get("/api/v1/inter-owner-entries/")
        assert resp.status_code == 403
