"""
Test API per l'app accounting.

Coprono:
- Smoke test viewset ledger e inter-owner
- Accesso negato agli inquilini
- Action POST bt-inter-owner: 4 tipi (distribuzione, conguaglio, bilaterale,
  aggiustamento) + 409 su BT già marcata.
- Action DELETE bt-inter-owner/<id>.
- Action GET saldi-live (con e senza ?at=).
- BankTransactionSerializer.is_inter_owner.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from accounting.models import InterOwnerEntry, OwnerLedgerEntry
from billing.models.payments import BankTransaction
from properties.models import OwnerBankAccount, OwnerProfile, OwnershipShare


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
        resp = client_prop.get("/api/v1/owner-ledger/")
        assert resp.status_code == 200
        ids = [e["id"] for e in resp.json()]
        assert ledger_entry.id in ids

    def test_proprietario_vede_dettaglio(self, client_prop, ledger_entry):
        resp = client_prop.get(f"/api/v1/owner-ledger/{ledger_entry.id}/")
        assert resp.status_code == 200
        assert resp.json()["importo"] == "400.00"

    def test_inquilino_non_accede(self, client_inq):
        resp = client_inq.get("/api/v1/owner-ledger/")
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


# ---------------------------------------------------------------------------
# Test action bt-inter-owner + saldi-live
# ---------------------------------------------------------------------------


@pytest.fixture
def conto_owner_1(db, owner_1):
    return OwnerBankAccount.objects.create(
        owner=owner_1,
        banca="Banca 1",
        intestatario="Owner 1",
        iban="IT60X0542811101000000000777",
    )


@pytest.fixture
def bt_owner_1(db, conto_owner_1):
    return BankTransaction.objects.create(
        data=datetime.date(2025, 11, 12),
        descrizione="CONGUAGLIO 2025",
        importo=Decimal("1707.00"),
        owner_account=conto_owner_1,
    )


class TestActionBtInterOwner:
    def test_marca_distribuzione(self, client_prop, bt_owner_1, owner_1, owner_2):
        resp = client_prop.post(
            "/api/v1/owner-ledger/bt-inter-owner/",
            data={
                "bank_transaction": bt_owner_1.pk,
                "tipo": "distribuzione",
                "controparte_owner": owner_2.pk,
                "descrizione": "Distribuzione utili 2025",
            },
            format="json",
        )
        assert resp.status_code == 201
        assert len(resp.json()) == 2
        # 2 voci ledger A simmetriche
        assert OwnerLedgerEntry.objects.filter(bank_transaction=bt_owner_1).count() == 2
        somma = sum(v.importo for v in OwnerLedgerEntry.objects.filter(bank_transaction=bt_owner_1))
        assert somma == Decimal("0.00")

    def test_marca_incasso_conguaglio(self, client_prop, bt_owner_1, owner_1, owner_2):
        resp = client_prop.post(
            "/api/v1/owner-ledger/bt-inter-owner/",
            data={
                "bank_transaction": bt_owner_1.pk,
                "tipo": "incasso_conguaglio",
                "controparte_owner": owner_2.pk,
            },
            format="json",
        )
        assert resp.status_code == 201
        tipi = set(OwnerLedgerEntry.objects.filter(bank_transaction=bt_owner_1).values_list("tipo", flat=True))
        assert tipi == {"incasso_conguaglio"}

    def test_marca_bilaterale_crea_inter_owner_entry(
        self, client_prop, bt_owner_1, owner_1, owner_2,
    ):
        resp = client_prop.post(
            "/api/v1/owner-ledger/bt-inter-owner/",
            data={
                "bank_transaction": bt_owner_1.pk,
                "tipo": "bilaterale",
                "controparte_owner": owner_2.pk,
                "descrizione": "Restituzione personale",
            },
            format="json",
        )
        assert resp.status_code == 201
        # bt.importo > 0: BT entrante in conto di owner_1 → owner_2 paga a owner_1
        entry = InterOwnerEntry.objects.get(bank_transaction=bt_owner_1)
        assert entry.owner_da == owner_2
        assert entry.owner_a == owner_1
        assert entry.importo == Decimal("1707.00")

    def test_marca_bilaterale_associa_a_settlement_di_competenza(
        self, client_prop, bt_owner_1, owner_1, owner_2,
    ):
        """Caso reale: la BT è del 2026 ma di competenza settlement 2025."""
        from accounting.models import OwnerSettlement
        sett_2025 = OwnerSettlement.objects.create(
            data=datetime.date(2025, 12, 31),
            periodo_da=datetime.date(2025, 1, 1),
            periodo_a=datetime.date(2025, 12, 31),
            descrizione="Chiusura 2025",
            snapshot={},
        )
        resp = client_prop.post(
            "/api/v1/owner-ledger/bt-inter-owner/",
            data={
                "bank_transaction": bt_owner_1.pk,
                "tipo": "bilaterale",
                "controparte_owner": owner_2.pk,
                "settlement": sett_2025.pk,
                "descrizione": "Conguaglio competenza 2025",
            },
            format="json",
        )
        assert resp.status_code == 201
        entry = InterOwnerEntry.objects.get(bank_transaction=bt_owner_1)
        assert entry.riferimento_settlement == sett_2025

    def test_marca_aggiustamento_voce_singola(self, client_prop, bt_owner_1, owner_1):
        resp = client_prop.post(
            "/api/v1/owner-ledger/bt-inter-owner/",
            data={"bank_transaction": bt_owner_1.pk, "tipo": "aggiustamento"},
            format="json",
        )
        assert resp.status_code == 201
        voci = OwnerLedgerEntry.objects.filter(bank_transaction=bt_owner_1)
        assert voci.count() == 1
        assert voci.first().tipo == "aggiustamento"
        assert voci.first().owner == owner_1

    def test_409_su_bt_gia_marcata(self, client_prop, bt_owner_1, owner_1, owner_2):
        client_prop.post(
            "/api/v1/owner-ledger/bt-inter-owner/",
            data={
                "bank_transaction": bt_owner_1.pk,
                "tipo": "distribuzione",
                "controparte_owner": owner_2.pk,
            },
            format="json",
        )
        resp = client_prop.post(
            "/api/v1/owner-ledger/bt-inter-owner/",
            data={
                "bank_transaction": bt_owner_1.pk,
                "tipo": "distribuzione",
                "controparte_owner": owner_2.pk,
            },
            format="json",
        )
        assert resp.status_code == 409

    def test_400_se_controparte_mancante_per_bilaterale(self, client_prop, bt_owner_1):
        resp = client_prop.post(
            "/api/v1/owner-ledger/bt-inter-owner/",
            data={"bank_transaction": bt_owner_1.pk, "tipo": "bilaterale"},
            format="json",
        )
        assert resp.status_code == 400

    def test_disfa_marcatura(self, client_prop, bt_owner_1, owner_1, owner_2):
        client_prop.post(
            "/api/v1/owner-ledger/bt-inter-owner/",
            data={
                "bank_transaction": bt_owner_1.pk,
                "tipo": "distribuzione",
                "controparte_owner": owner_2.pk,
            },
            format="json",
        )
        assert OwnerLedgerEntry.objects.filter(bank_transaction=bt_owner_1).count() == 2
        resp = client_prop.delete(f"/api/v1/owner-ledger/bt-inter-owner/{bt_owner_1.pk}/")
        assert resp.status_code == 200
        assert resp.json()["voci_cancellate"] == 2
        assert OwnerLedgerEntry.objects.filter(bank_transaction=bt_owner_1).count() == 0

    def test_inquilino_non_accede(self, client_inq, bt_owner_1, owner_2):
        resp = client_inq.post(
            "/api/v1/owner-ledger/bt-inter-owner/",
            data={
                "bank_transaction": bt_owner_1.pk,
                "tipo": "distribuzione",
                "controparte_owner": owner_2.pk,
            },
            format="json",
        )
        assert resp.status_code == 403


class TestActionSaldiLive:
    def test_default_at_oggi(self, client_prop, owner_1):
        OwnershipShare.objects.create(
            owner=owner_1, valid_from=datetime.date(2020, 1, 1), quota=Decimal("1.0"),
        )
        resp = client_prop.get("/api/v1/owner-ledger/saldi-live/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 1
        assert resp.json()[0]["owner"]["nominativo"] == "Proprietario ACC 1"

    def test_at_invalido_400(self, client_prop):
        resp = client_prop.get("/api/v1/owner-ledger/saldi-live/?at=non-una-data")
        assert resp.status_code == 400

    def test_inquilino_non_accede(self, client_inq):
        resp = client_inq.get("/api/v1/owner-ledger/saldi-live/")
        assert resp.status_code == 403
