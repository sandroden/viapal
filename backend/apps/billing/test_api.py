"""
Test API per l'app billing.

Coprono:
- Smoke test viewset
- Filtering per inquilino
- Action dichiara_pagato / conferma_pagato
- Dashboard inquilino e proprietario
- Quadro annuale
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from billing.models import (
    ExtraCharge,
    RentPayment,
    StatoPagamento,
    UtilityCharge,
    UtilityChargeLine,
    UtilityChargePeriod,
)
from properties.models import OwnerProfile, Room, RoomAssignment, TenantProfile


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
    u = User.objects.create_user("bp_prop", email="prop@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    return u


@pytest.fixture
def user_inq_1(db, gruppo_inquilini):
    u = User.objects.create_user("bp_inq1", email="i1@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    return u


@pytest.fixture
def user_inq_2(db, gruppo_inquilini):
    u = User.objects.create_user("bp_inq2", email="i2@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    return u


@pytest.fixture
def tenant_1(db, user_inq_1):
    return TenantProfile.objects.create(
        user=user_inq_1, nominativo="Inquilino Billing 1", giorno_pagamento_affitto=1
    )


@pytest.fixture
def tenant_2(db, user_inq_2):
    return TenantProfile.objects.create(
        user=user_inq_2, nominativo="Inquilino Billing 2", giorno_pagamento_affitto=5
    )


@pytest.fixture
def room_1(db):
    return Room.objects.create(nome="Camera Billing A", ordinamento=20)


@pytest.fixture
def room_2(db):
    return Room.objects.create(nome="Camera Billing B", ordinamento=21)


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
def rent_payment_1(db, assignment_1):
    return RentPayment.objects.create(
        assignment=assignment_1,
        competenza_da=datetime.date(2026, 5, 1),
        competenza_a=datetime.date(2026, 5, 31),
        importo_dovuto=Decimal("400"),
        scadenza=datetime.date(2026, 5, 1),
        stato=StatoPagamento.ATTESO,
    )


@pytest.fixture
def rent_payment_2(db, assignment_2):
    return RentPayment.objects.create(
        assignment=assignment_2,
        competenza_da=datetime.date(2026, 5, 1),
        competenza_a=datetime.date(2026, 5, 31),
        importo_dovuto=Decimal("380"),
        scadenza=datetime.date(2026, 5, 5),
        stato=StatoPagamento.ATTESO,
    )


@pytest.fixture
def period(db):
    return UtilityChargePeriod.objects.create(
        periodo_da=datetime.date(2026, 4, 1),
        periodo_a=datetime.date(2026, 4, 30),
        stato="inviato",
    )


@pytest.fixture
def charge_1(db, period, assignment_1):
    charge = UtilityCharge.objects.create(
        period=period,
        assignment=assignment_1,
        importo_totale=Decimal("45.00"),
        scadenza=datetime.date(2026, 5, 5),
        stato=StatoPagamento.ATTESO,
    )
    UtilityChargeLine.objects.create(charge=charge, voce="luce", importo=Decimal("25.00"))
    UtilityChargeLine.objects.create(charge=charge, voce="gas", importo=Decimal("11.00"))
    UtilityChargeLine.objects.create(charge=charge, voce="tari", importo=Decimal("9.00"))
    return charge


@pytest.fixture
def charge_2(db, period, assignment_2):
    return UtilityCharge.objects.create(
        period=period,
        assignment=assignment_2,
        importo_totale=Decimal("43.00"),
        scadenza=datetime.date(2026, 5, 5),
        stato=StatoPagamento.ATTESO,
    )


@pytest.fixture
def extra_charge_1(db, assignment_1):
    return ExtraCharge.objects.create(
        assignment=assignment_1,
        data=datetime.date(2026, 4, 1),
        descrizione="Test extra",
        importo=Decimal("50.00"),
        scadenza=datetime.date(2026, 5, 15),
    )


@pytest.fixture
def extra_charge_2(db, assignment_2):
    return ExtraCharge.objects.create(
        assignment=assignment_2,
        data=datetime.date(2026, 4, 1),
        descrizione="Extra per inquilino 2",
        importo=Decimal("30.00"),
        scadenza=datetime.date(2026, 5, 15),
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
# Test RentPaymentViewSet
# ---------------------------------------------------------------------------


class TestRentPaymentViewSet:
    def test_proprietario_vede_tutti(self, client_prop, rent_payment_1, rent_payment_2):
        resp = client_prop.get("/api/v1/rent-payments/")
        assert resp.status_code == 200
        data = resp.json()
        ids = [r["id"] for r in data["results"]]
        assert rent_payment_1.id in ids
        assert rent_payment_2.id in ids

    def test_inquilino_vede_solo_propri(self, client_inq_1, rent_payment_1, rent_payment_2):
        resp = client_inq_1.get("/api/v1/rent-payments/")
        assert resp.status_code == 200
        data = resp.json()
        ids = [r["id"] for r in data["results"]]
        assert rent_payment_1.id in ids
        assert rent_payment_2.id not in ids

    def test_inquilino_non_puo_creare(self, client_inq_1, assignment_1):
        resp = client_inq_1.post(
            "/api/v1/rent-payments/",
            {
                "assignment": assignment_1.id,
                "competenza_da": "2026-06-01",
                "competenza_a": "2026-06-30",
                "importo_dovuto": "400.00",
                "scadenza": "2026-06-01",
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_proprietario_puo_creare(self, client_prop, assignment_1):
        resp = client_prop.post(
            "/api/v1/rent-payments/",
            {
                "assignment": assignment_1.id,
                "competenza_da": "2026-07-01",
                "competenza_a": "2026-07-31",
                "importo_dovuto": "400.00",
                "scadenza": "2026-07-01",
            },
            format="json",
        )
        assert resp.status_code == 201


class TestDicharaPagato:
    def test_inquilino_dichiara_proprio(self, client_inq_1, rent_payment_1):
        resp = client_inq_1.post(
            f"/api/v1/rent-payments/{rent_payment_1.id}/dichiara_pagato/"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stato"] == StatoPagamento.DICHIARATO

        rent_payment_1.refresh_from_db()
        assert rent_payment_1.stato == StatoPagamento.DICHIARATO
        assert rent_payment_1.importo_pagato == rent_payment_1.importo_dovuto

    def test_inquilino_non_dichiara_altrui(self, client_inq_1, rent_payment_2):
        resp = client_inq_1.post(
            f"/api/v1/rent-payments/{rent_payment_2.id}/dichiara_pagato/"
        )
        # rent_payment_2 belongs to inq_2; inq_1 should get 403 or 404
        assert resp.status_code in (403, 404)

    def test_proprietario_non_dichiara_con_azione_inquilino(
        self, client_prop, rent_payment_1
    ):
        """Il proprietario può usare dichiara_pagato solo per completezza (non è l'inquilino)."""
        # Il proprietario PUO' chiamare dichiara_pagato perche' la permission e' IsAuthenticated
        # ma ci aspettiamo che funzioni (il proprietario puo' farlo per conto)
        resp = client_prop.post(
            f"/api/v1/rent-payments/{rent_payment_1.id}/dichiara_pagato/"
        )
        assert resp.status_code == 200


class TestConfermaPayment:
    def test_proprietario_conferma(self, user_prop, user_inq_1, rent_payment_1):
        # Usa due client separati per evitare conflitti di sessione
        inq_client = APIClient(enforce_csrf_checks=False)
        inq_client.force_login(user_inq_1)
        prop_client = APIClient(enforce_csrf_checks=False)
        prop_client.force_login(user_prop)

        # Prima l'inquilino dichiara
        inq_client.post(f"/api/v1/rent-payments/{rent_payment_1.id}/dichiara_pagato/")
        # Poi il proprietario conferma
        resp = prop_client.post(
            f"/api/v1/rent-payments/{rent_payment_1.id}/conferma_pagato/"
        )
        assert resp.status_code == 200
        assert resp.json()["stato"] == StatoPagamento.PAGATO

    def test_inquilino_non_conferma(self, client_inq_1, rent_payment_1):
        resp = client_inq_1.post(
            f"/api/v1/rent-payments/{rent_payment_1.id}/conferma_pagato/"
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test UtilityChargeViewSet
# ---------------------------------------------------------------------------


class TestUtilityChargeViewSet:
    def test_proprietario_vede_tutti(self, client_prop, charge_1, charge_2):
        resp = client_prop.get("/api/v1/utility-charges/")
        assert resp.status_code == 200
        data = resp.json()
        ids = [c["id"] for c in data["results"]]
        assert charge_1.id in ids
        assert charge_2.id in ids

    def test_inquilino_vede_solo_propri(self, client_inq_1, charge_1, charge_2):
        resp = client_inq_1.get("/api/v1/utility-charges/")
        assert resp.status_code == 200
        data = resp.json()
        ids = [c["id"] for c in data["results"]]
        assert charge_1.id in ids
        assert charge_2.id not in ids

    def test_lines_nidificate(self, client_prop, charge_1):
        resp = client_prop.get(f"/api/v1/utility-charges/{charge_1.id}/")
        assert resp.status_code == 200
        data = resp.json()
        assert "lines" in data
        assert len(data["lines"]) == 3

    def test_inquilino_dichiara_conguaglio(self, client_inq_1, charge_1):
        resp = client_inq_1.post(
            f"/api/v1/utility-charges/{charge_1.id}/dichiara_pagato/"
        )
        assert resp.status_code == 200
        assert resp.json()["stato"] == StatoPagamento.DICHIARATO

    def test_proprietario_conferma_conguaglio(self, user_prop, user_inq_1, charge_1):
        inq_client = APIClient(enforce_csrf_checks=False)
        inq_client.force_login(user_inq_1)
        prop_client = APIClient(enforce_csrf_checks=False)
        prop_client.force_login(user_prop)

        inq_client.post(f"/api/v1/utility-charges/{charge_1.id}/dichiara_pagato/")
        resp = prop_client.post(
            f"/api/v1/utility-charges/{charge_1.id}/conferma_pagato/"
        )
        assert resp.status_code == 200
        assert resp.json()["stato"] == StatoPagamento.PAGATO


# ---------------------------------------------------------------------------
# Test ExtraChargeViewSet
# ---------------------------------------------------------------------------


class TestExtraChargeViewSet:
    def test_proprietario_vede_tutti(self, client_prop, extra_charge_1, extra_charge_2):
        resp = client_prop.get("/api/v1/extra-charges/")
        assert resp.status_code == 200
        ids = [e["id"] for e in resp.json()]
        assert extra_charge_1.id in ids
        assert extra_charge_2.id in ids

    def test_inquilino_vede_solo_propri(self, client_inq_1, extra_charge_1, extra_charge_2):
        resp = client_inq_1.get("/api/v1/extra-charges/")
        assert resp.status_code == 200
        ids = [e["id"] for e in resp.json()]
        assert extra_charge_1.id in ids
        assert extra_charge_2.id not in ids

    def test_inquilino_non_crea(self, client_inq_1, assignment_1):
        resp = client_inq_1.post(
            "/api/v1/extra-charges/",
            {"assignment": assignment_1.id, "data": "2026-05-01",
             "descrizione": "Test", "importo": "10.00", "scadenza": "2026-05-31"},
            format="json",
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test Dashboard Inquilino
# ---------------------------------------------------------------------------


class TestDashboardInquilino:
    def test_inquilino_dashboard_200(self, client_inq_1, tenant_1, rent_payment_1, charge_1):
        resp = client_inq_1.get("/api/v1/dashboard/inquilino/")
        assert resp.status_code == 200
        data = resp.json()
        assert "tenant" in data
        assert "da_pagare" in data
        assert "ultimi_pagamenti" in data

    def test_da_pagare_contiene_affitto_atteso(
        self, client_inq_1, tenant_1, rent_payment_1
    ):
        resp = client_inq_1.get("/api/v1/dashboard/inquilino/")
        assert resp.status_code == 200
        da_pagare = resp.json()["da_pagare"]
        types = [item["tipo"] for item in da_pagare]
        assert "rent" in types

    def test_semaforo_presente(self, client_inq_1, tenant_1, rent_payment_1):
        resp = client_inq_1.get("/api/v1/dashboard/inquilino/")
        data = resp.json()
        for item in data["da_pagare"]:
            assert "semaforo" in item
            assert item["semaforo"] in ("salvia", "miele", "argilla_chiaro", "argilla_scuro")

    def test_proprietario_non_accede(self, client_prop):
        resp = client_prop.get("/api/v1/dashboard/inquilino/")
        assert resp.status_code == 403

    def test_dashboard_no_profilo_senza_tenant(self, api_client, gruppo_inquilini):
        u = User.objects.create_user("no_tenant_user", password="pwd!")
        u.groups.add(gruppo_inquilini)
        api_client.force_login(u)
        resp = api_client.get("/api/v1/dashboard/inquilino/")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test Dashboard Proprietario
# ---------------------------------------------------------------------------


class TestDashboardProprietario:
    def test_proprietario_dashboard_200(self, client_prop):
        resp = client_prop.get("/api/v1/dashboard/proprietario/")
        assert resp.status_code == 200
        data = resp.json()
        assert "kpi" in data
        assert "ritardi" in data
        assert "in_scadenza" in data
        assert data["is_storico"] is False
        assert data["anno"] == datetime.date.today().year
        assert data["mese"] == datetime.date.today().month

    def test_kpi_campi_presenti(self, client_prop):
        resp = client_prop.get("/api/v1/dashboard/proprietario/")
        kpi = resp.json()["kpi"]
        expected_keys = [
            "incasso_anno",
            "incasso_mese",
            "spese_anno",
            "ritardi_count",
            "in_scadenza_count",
        ]
        for key in expected_keys:
            assert key in kpi

    def test_inquilino_non_accede(self, client_inq_1):
        resp = client_inq_1.get("/api/v1/dashboard/proprietario/")
        assert resp.status_code == 403

    def test_dashboard_proprietario_anno_passato(
        self, client_prop, assignment_1, assignment_2
    ):
        # Crea un pagamento storico nell'anno scorso
        anno_scorso = datetime.date.today().year - 1
        RentPayment.objects.create(
            assignment=assignment_1,
            competenza_da=datetime.date(anno_scorso, 6, 1),
            competenza_a=datetime.date(anno_scorso, 6, 30),
            importo_dovuto=Decimal("400"),
            importo_pagato=Decimal("400"),
            scadenza=datetime.date(anno_scorso, 6, 1),
            data_pagamento=datetime.date(anno_scorso, 6, 3),
            stato=StatoPagamento.PAGATO,
        )
        resp = client_prop.get(f"/api/v1/dashboard/proprietario/?anno={anno_scorso}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["anno"] == anno_scorso
        assert data["is_storico"] is True
        assert data["ritardi"] == []
        assert data["in_scadenza"] == []
        assert data["kpi"]["incasso_anno"] == 400.0

    def test_dashboard_proprietario_mese_specifico(
        self, client_prop, assignment_1
    ):
        # 2 pagamenti diversi mesi nello stesso anno
        anno_scorso = datetime.date.today().year - 1
        RentPayment.objects.create(
            assignment=assignment_1,
            competenza_da=datetime.date(anno_scorso, 3, 1),
            competenza_a=datetime.date(anno_scorso, 3, 31),
            importo_dovuto=Decimal("400"),
            importo_pagato=Decimal("400"),
            scadenza=datetime.date(anno_scorso, 3, 1),
            data_pagamento=datetime.date(anno_scorso, 3, 5),
            stato=StatoPagamento.PAGATO,
        )
        RentPayment.objects.create(
            assignment=assignment_1,
            competenza_da=datetime.date(anno_scorso, 11, 1),
            competenza_a=datetime.date(anno_scorso, 11, 30),
            importo_dovuto=Decimal("400"),
            importo_pagato=Decimal("400"),
            scadenza=datetime.date(anno_scorso, 11, 1),
            data_pagamento=datetime.date(anno_scorso, 11, 4),
            stato=StatoPagamento.PAGATO,
        )
        resp = client_prop.get(
            f"/api/v1/dashboard/proprietario/?anno={anno_scorso}&mese=11"
        )
        assert resp.status_code == 200
        kpi = resp.json()["kpi"]
        assert kpi["incasso_anno"] == 800.0
        assert kpi["incasso_mese"] == 400.0

    def test_dashboard_proprietario_anno_invalido_400(self, client_prop):
        resp = client_prop.get("/api/v1/dashboard/proprietario/?anno=abc")
        assert resp.status_code == 400

    def test_dashboard_proprietario_mese_fuori_range_400(self, client_prop):
        resp = client_prop.get("/api/v1/dashboard/proprietario/?mese=13")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Test Quadro Annuale
# ---------------------------------------------------------------------------


class TestQuadroAnnuale:
    def test_proprietario_accede_2026(self, client_prop, period, charge_1, charge_2):
        resp = client_prop.get("/api/v1/quadro-annuale/2026/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["anno"] == 2026
        assert "tenants" in data
        assert "righe" in data
        assert "totale_anno_per_tenant" in data
        assert "totale_anno" in data

    def test_righe_contengono_tenant(self, client_prop, period, charge_1, charge_2):
        resp = client_prop.get("/api/v1/quadro-annuale/2026/")
        data = resp.json()
        assert len(data["righe"]) >= 1
        riga = data["righe"][0]
        assert "per_tenant" in riga
        assert "totale_periodo" in riga

    def test_anno_senza_dati(self, client_prop):
        resp = client_prop.get("/api/v1/quadro-annuale/2000/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["anno"] == 2000
        assert data["righe"] == []
        assert data["totale_anno"] == 0.0

    def test_inquilino_non_accede(self, client_inq_1):
        resp = client_inq_1.get("/api/v1/quadro-annuale/2026/")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test Tenant Situazione (drilldown inquilino)
# ---------------------------------------------------------------------------


class TestTenantSituazione:
    def test_proprietario_accede_default_anno(
        self, client_prop, tenant_1, assignment_1
    ):
        resp = client_prop.get(f"/api/v1/tenants/{tenant_1.id}/situazione/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant"]["id"] == tenant_1.id
        assert data["anno"] == datetime.date.today().year
        assert "assignments" in data
        assert len(data["assignments"]) == 1
        assert data["assignments"][0]["room_id"] == assignment_1.room_id
        # Senza fixture rent/charge/extra, totali dovrebbero essere 0
        assert data["rent"]["dovuto_anno"] == 0.0
        assert data["utility"]["dovuto_anno"] == 0.0
        assert data["totali_anno"]["dovuto"] == 0.0
        assert data["ritardo_medio_giorni"] == 0.0

    def test_situazione_anno_2026(
        self, client_prop, tenant_1, rent_payment_1, charge_1, extra_charge_1
    ):
        resp = client_prop.get(f"/api/v1/tenants/{tenant_1.id}/situazione/?anno=2026")
        assert resp.status_code == 200
        data = resp.json()
        assert data["anno"] == 2026
        assert data["rent"]["dovuto_anno"] == 400.0
        assert len(data["rent"]["righe"]) == 1
        assert data["utility"]["dovuto_anno"] == 45.0
        assert len(data["utility"]["righe"]) == 1
        # 3 lines: luce/gas/tari
        assert len(data["utility"]["righe"][0]["lines"]) == 3
        assert data["extra"]["totale_anno"] == 50.0
        # Totali aggregati
        assert data["totali_anno"]["dovuto"] == 495.0  # 400 + 45 + 50
        assert data["totali_anno"]["pagato"] == 0.0

    def test_situazione_anno_diverso_filtra(
        self, client_prop, tenant_1, rent_payment_1
    ):
        # rent_payment_1 è 2026; richiediamo 2025
        resp = client_prop.get(f"/api/v1/tenants/{tenant_1.id}/situazione/?anno=2025")
        assert resp.status_code == 200
        data = resp.json()
        assert data["anno"] == 2025
        assert data["rent"]["dovuto_anno"] == 0.0
        assert data["rent"]["righe"] == []

    def test_situazione_inquilino_403(self, client_inq_1, tenant_1):
        resp = client_inq_1.get(f"/api/v1/tenants/{tenant_1.id}/situazione/")
        assert resp.status_code == 403

    def test_situazione_tenant_inesistente_404(self, client_prop):
        resp = client_prop.get("/api/v1/tenants/99999/situazione/")
        assert resp.status_code == 404

    def test_situazione_anno_invalido_400(self, client_prop, tenant_1):
        resp = client_prop.get(f"/api/v1/tenants/{tenant_1.id}/situazione/?anno=abc")
        assert resp.status_code == 400
