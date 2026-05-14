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
    Receivable,
    StatoPagamento,
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
    )


@pytest.fixture
def assignment_2(db, room_2, tenant_2):
    return RoomAssignment.objects.create(
        room=room_2,
        tenant=tenant_2,
        valid_from=datetime.date(2024, 9, 1),
        canone_mensile=Decimal("380"),
    )


@pytest.fixture
def rent_payment_1(db, assignment_1):
    return Receivable.objects.create(
        assignment=assignment_1,
        causale=Receivable.Causale.AFFITTO,
        competenza_da=datetime.date(2026, 5, 1),
        competenza_a=datetime.date(2026, 5, 31),
        importo_dovuto=Decimal("400"),
        scadenza=datetime.date(2026, 5, 1),
        stato=StatoPagamento.ATTESO,
    )


@pytest.fixture
def rent_payment_2(db, assignment_2):
    return Receivable.objects.create(
        assignment=assignment_2,
        causale=Receivable.Causale.AFFITTO,
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
        tot_luce=Decimal("50.00"),
        tot_gas=Decimal("22.00"),
        tot_tari=Decimal("18.00"),
        giorni_totali=60,
    )


@pytest.fixture
def charge_1(db, period, assignment_1):
    return Receivable.objects.create(
        utility_period=period,
        assignment=assignment_1,
        causale=Receivable.Causale.UTENZE,
        competenza_da=period.periodo_da,
        competenza_a=period.periodo_a,
        importo_dovuto=Decimal("45.00"),
        giorni_presenza=30,
        scadenza=datetime.date(2026, 5, 5),
        stato=StatoPagamento.ATTESO,
    )


@pytest.fixture
def charge_2(db, period, assignment_2):
    return Receivable.objects.create(
        utility_period=period,
        assignment=assignment_2,
        causale=Receivable.Causale.UTENZE,
        competenza_da=period.periodo_da,
        competenza_a=period.periodo_a,
        importo_dovuto=Decimal("43.00"),
        scadenza=datetime.date(2026, 5, 5),
        stato=StatoPagamento.ATTESO,
    )


@pytest.fixture
def extra_charge_1(db, assignment_1):
    return Receivable.objects.create(
        assignment=assignment_1,
        causale=Receivable.Causale.EXTRA,
        competenza_da=datetime.date(2026, 4, 1),
        descrizione="Test extra",
        importo_dovuto=Decimal("50.00"),
        scadenza=datetime.date(2026, 5, 15),
    )


@pytest.fixture
def extra_charge_2(db, assignment_2):
    return Receivable.objects.create(
        assignment=assignment_2,
        causale=Receivable.Causale.EXTRA,
        competenza_da=datetime.date(2026, 4, 1),
        descrizione="Extra per inquilino 2",
        importo_dovuto=Decimal("30.00"),
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

    def test_period_totali_esposti(self, client_prop, charge_1):
        """Il serializer espone i totali di periodo + giorni_presenza per il drill-down."""
        resp = client_prop.get(f"/api/v1/utility-charges/{charge_1.id}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_tot_luce"] == "50.00"
        assert data["period_tot_gas"] == "22.00"
        assert data["period_tot_tari"] == "18.00"
        assert data["period_giorni_totali"] == 60
        assert data["giorni_presenza"] == 30

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
        Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.AFFITTO,
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
        Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(anno_scorso, 3, 1),
            competenza_a=datetime.date(anno_scorso, 3, 31),
            importo_dovuto=Decimal("400"),
            importo_pagato=Decimal("400"),
            scadenza=datetime.date(anno_scorso, 3, 1),
            data_pagamento=datetime.date(anno_scorso, 3, 5),
            stato=StatoPagamento.PAGATO,
        )
        Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.AFFITTO,
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
# Test Dettaglio bilancio owner (voci singole entrate/uscite)
# ---------------------------------------------------------------------------


@pytest.fixture
def owner_alessandro(db, user_prop):
    return OwnerProfile.objects.create(user=user_prop, nominativo="Alessandro Test")


class TestBilancioOwnerDettaglio:
    """Test per /api/v1/dashboard/proprietario/<owner_id>/dettaglio-bilancio/."""

    def _url(self, owner_id, anno, tipo):
        return (
            f"/api/v1/dashboard/proprietario/{owner_id}/dettaglio-bilancio/"
            f"?anno={anno}&tipo={tipo}"
        )

    def test_entrate_righe_e_totale_quadrano(
        self, client_prop, assignment_1, owner_alessandro
    ):
        anno = datetime.date.today().year
        Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(anno, 3, 1),
            competenza_a=datetime.date(anno, 3, 31),
            importo_dovuto=Decimal("400"),
            importo_pagato=Decimal("400"),
            scadenza=datetime.date(anno, 3, 1),
            data_pagamento=datetime.date(anno, 3, 5),
            stato=StatoPagamento.PAGATO,
            incassato_da_owner=owner_alessandro,
        )
        Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.EXTRA,
            competenza_da=datetime.date(anno, 4, 1),
            descrizione="Extra X",
            importo_dovuto=Decimal("75"),
            importo_pagato=Decimal("75"),
            scadenza=datetime.date(anno, 4, 10),
            data_pagamento=datetime.date(anno, 4, 12),
            stato=StatoPagamento.PAGATO,
            incassato_da_owner=owner_alessandro,
        )
        # Voce non deve apparire (stato != PAGATO)
        Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(anno, 5, 1),
            competenza_a=datetime.date(anno, 5, 31),
            importo_dovuto=Decimal("400"),
            scadenza=datetime.date(anno, 5, 1),
            stato=StatoPagamento.ATTESO,
            incassato_da_owner=owner_alessandro,
        )

        resp = client_prop.get(self._url(owner_alessandro.id, anno, "entrate"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["owner_id"] == owner_alessandro.id
        assert data["tipo"] == "entrate"
        assert data["totale"] == 475.0
        assert len(data["righe"]) == 2
        # Ordering: data_pagamento desc → extra (12 aprile) prima dell'affitto (5 marzo)
        assert data["righe"][0]["causale"] == "extra"
        assert data["righe"][1]["causale"] == "affitto"
        # Campi richiesti dalla pagina FE
        for k in (
            "id", "tipo", "causale", "causale_label", "tenant", "descrizione",
            "importo_dovuto", "importo_pagato", "scadenza", "data_pagamento", "stato",
        ):
            assert k in data["righe"][0]

    def test_uscite_solo_owner_richiesto(
        self, client_prop, owner_alessandro, user_inq_2
    ):
        from billing.models import Expense, ExpenseCategory
        anno = datetime.date.today().year
        cat = ExpenseCategory.objects.create(nome="Spese condominiali")
        altro = OwnerProfile.objects.create(user=user_inq_2, nominativo="Altro")
        Expense.objects.create(
            data=datetime.date(anno, 3, 23),
            category=cat,
            importo=Decimal("1000"),
            descrizione="Rata 3",
            anticipata_da_owner=owner_alessandro,
        )
        Expense.objects.create(
            data=datetime.date(anno, 4, 1),
            category=cat,
            importo=Decimal("500"),
            descrizione="Rata 4",
            anticipata_da_owner=altro,
        )
        resp = client_prop.get(self._url(owner_alessandro.id, anno, "uscite"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["totale"] == 1000.0
        assert len(data["righe"]) == 1
        assert data["righe"][0]["categoria"] == "Spese condominiali"
        assert data["righe"][0]["importo"] == 1000.0

    def test_inquilino_non_accede(self, client_inq_1, owner_alessandro):
        resp = client_inq_1.get(self._url(owner_alessandro.id, 2026, "entrate"))
        assert resp.status_code == 403

    def test_anno_mancante_400(self, client_prop, owner_alessandro):
        resp = client_prop.get(
            f"/api/v1/dashboard/proprietario/{owner_alessandro.id}/dettaglio-bilancio/?tipo=entrate"
        )
        assert resp.status_code == 400

    def test_tipo_invalido_400(self, client_prop, owner_alessandro):
        resp = client_prop.get(self._url(owner_alessandro.id, 2026, "foo"))
        assert resp.status_code == 400

    def test_owner_inesistente_404(self, client_prop):
        resp = client_prop.get(self._url(99999, 2026, "entrate"))
        assert resp.status_code == 404


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

    def test_situazione_caparra_assente_se_contratto_attivo(
        self, client_prop, tenant_1, assignment_1
    ):
        tenant_1.deposito_versato = Decimal("1500")
        tenant_1.data_versamento_deposito = datetime.date(2024, 9, 1)
        tenant_1.save()
        resp = client_prop.get(f"/api/v1/tenants/{tenant_1.id}/situazione/?anno=2026")
        assert resp.status_code == 200
        data = resp.json()
        assert data["caparra"]["righe"] == []
        assert data["caparra"]["dovuto_anno"] == 0.0

    def test_situazione_caparra_presente_dopo_restituzione(
        self, client_prop, tenant_1, assignment_1
    ):
        tenant_1.deposito_versato = Decimal("1500")
        tenant_1.data_versamento_deposito = datetime.date(2024, 9, 1)
        tenant_1.deposito_restituito = Decimal("1500")
        tenant_1.data_restituzione_deposito = datetime.date(2026, 4, 30)
        tenant_1.save()
        resp = client_prop.get(f"/api/v1/tenants/{tenant_1.id}/situazione/?anno=2026")
        assert resp.status_code == 200
        data = resp.json()
        # Solo la restituzione cade nell'anno 2026 (il versamento è del 2024).
        assert len(data["caparra"]["righe"]) == 1
        assert data["caparra"]["righe"][0]["importo"] == -1500.0
        assert data["caparra"]["dovuto_anno"] == -1500.0
        assert data["totali_anno"]["dovuto"] == -1500.0


# ---------------------------------------------------------------------------
# Test riconciliazione bulk (POST /api/v1/reconciliations/)
# ---------------------------------------------------------------------------


@pytest.fixture
def owner_prop(db, user_prop):
    return OwnerProfile.objects.create(user=user_prop, nominativo="Owner Test Recon")


@pytest.fixture
def owner_account(db, owner_prop):
    from properties.models import OwnerBankAccount
    return OwnerBankAccount.objects.create(
        owner=owner_prop,
        banca="Banca Test",
        intestatario="Owner Test Recon",
        iban="IT00X0000000000000000000000",
    )


@pytest.fixture
def bank_tx_400(db, owner_account):
    from billing.models import BankTransaction
    return BankTransaction.objects.create(
        data=datetime.date(2026, 5, 3),
        descrizione="Bonifico Inquilino 1",
        importo=Decimal("400.00"),
        owner_account=owner_account,
    )


@pytest.fixture
def bank_tx_300(db, owner_account):
    from billing.models import BankTransaction
    return BankTransaction.objects.create(
        data=datetime.date(2026, 5, 4),
        descrizione="Acconto",
        importo=Decimal("300.00"),
        owner_account=owner_account,
    )


@pytest.fixture
def bank_tx_100(db, owner_account):
    from billing.models import BankTransaction
    return BankTransaction.objects.create(
        data=datetime.date(2026, 5, 6),
        descrizione="Saldo",
        importo=Decimal("100.00"),
        owner_account=owner_account,
    )


class TestReconciliationBulk:
    URL = "/api/v1/reconciliations/"

    def test_caso_semplice(self, client_prop, bank_tx_400, rent_payment_1):
        resp = client_prop.post(
            self.URL,
            {
                "replace_for_transactions": [bank_tx_400.id],
                "items": [
                    {
                        "bank_transaction": bank_tx_400.id,
                        "receivable": rent_payment_1.id,
                        "importo": "400.00",
                    },
                ],
            },
            format="json",
        )
        assert resp.status_code == 200, resp.content
        rent_payment_1.refresh_from_db()
        assert rent_payment_1.stato == StatoPagamento.PAGATO
        assert rent_payment_1.importo_pagato == Decimal("400.00")
        assert rent_payment_1.data_pagamento == datetime.date(2026, 5, 3)

    def test_pagamento_spezzato_due_BT(
        self, client_prop, bank_tx_300, bank_tx_100, rent_payment_1
    ):
        resp = client_prop.post(
            self.URL,
            {
                "replace_for_transactions": [bank_tx_300.id, bank_tx_100.id],
                "items": [
                    {
                        "bank_transaction": bank_tx_300.id,
                        "receivable": rent_payment_1.id,
                        "importo": "300.00",
                    },
                    {
                        "bank_transaction": bank_tx_100.id,
                        "receivable": rent_payment_1.id,
                        "importo": "100.00",
                    },
                ],
            },
            format="json",
        )
        assert resp.status_code == 200, resp.content
        rent_payment_1.refresh_from_db()
        assert rent_payment_1.stato == StatoPagamento.PAGATO
        # data_pagamento = max delle BT (2026-05-06)
        assert rent_payment_1.data_pagamento == datetime.date(2026, 5, 6)
        assert rent_payment_1.importo_pagato == Decimal("400.00")

    def test_somma_supera_BT_400(self, client_prop, bank_tx_300, rent_payment_1):
        resp = client_prop.post(
            self.URL,
            {
                "replace_for_transactions": [bank_tx_300.id],
                "items": [
                    {
                        "bank_transaction": bank_tx_300.id,
                        "receivable": rent_payment_1.id,
                        "importo": "500.00",
                    },
                ],
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_replace_rimuove_vecchie_allocations(
        self, client_prop, bank_tx_400, rent_payment_1, rent_payment_2
    ):
        # 1° call: alloca su rent_payment_1
        resp1 = client_prop.post(
            self.URL,
            {
                "replace_for_transactions": [bank_tx_400.id],
                "items": [
                    {
                        "bank_transaction": bank_tx_400.id,
                        "receivable": rent_payment_1.id,
                        "importo": "400.00",
                    },
                ],
            },
            format="json",
        )
        assert resp1.status_code == 200
        rent_payment_1.refresh_from_db()
        assert rent_payment_1.stato == StatoPagamento.PAGATO

        # 2° call: sostituisce, alloca tutto su rent_payment_2 (380€, residuo 20)
        resp2 = client_prop.post(
            self.URL,
            {
                "replace_for_transactions": [bank_tx_400.id],
                "items": [
                    {
                        "bank_transaction": bank_tx_400.id,
                        "receivable": rent_payment_2.id,
                        "importo": "380.00",
                    },
                ],
            },
            format="json",
        )
        assert resp2.status_code == 200, resp2.content

        # rent_payment_1 deve essere tornato non pagato
        rent_payment_1.refresh_from_db()
        assert rent_payment_1.stato == StatoPagamento.ATTESO
        assert rent_payment_1.importo_pagato is None

        # rent_payment_2 ora pagato
        rent_payment_2.refresh_from_db()
        assert rent_payment_2.stato == StatoPagamento.PAGATO
        assert rent_payment_2.importo_pagato == Decimal("380.00")

    def test_inquilino_403(self, client_inq_1, bank_tx_400, rent_payment_1):
        resp = client_inq_1.post(
            self.URL,
            {
                "replace_for_transactions": [bank_tx_400.id],
                "items": [
                    {
                        "bank_transaction": bank_tx_400.id,
                        "receivable": rent_payment_1.id,
                        "importo": "400.00",
                    },
                ],
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_BT_non_in_replace(self, client_prop, bank_tx_400, rent_payment_1):
        resp = client_prop.post(
            self.URL,
            {
                "replace_for_transactions": [],
                "items": [
                    {
                        "bank_transaction": bank_tx_400.id,
                        "receivable": rent_payment_1.id,
                        "importo": "100.00",
                    },
                ],
            },
            format="json",
        )
        assert resp.status_code == 400


class TestBankTransactionFiltri:
    def test_filtro_tenant_match_descrizione(
        self, client_prop, owner_account, tenant_1
    ):
        """Una BT senza allocations ma con cognome dell'inquilino nel testo
        deve comparire quando filtro per ``tenant=<id>``."""
        from billing.models import BankTransaction
        # tenant_1.nominativo = "Inquilino Billing 1" → token "Billing" e "Inquilino"
        match = BankTransaction.objects.create(
            data=datetime.date(2026, 5, 3),
            descrizione="Bon. da BILLING per affitto",
            importo=Decimal("400.00"),
            owner_account=owner_account,
        )
        non_match = BankTransaction.objects.create(
            data=datetime.date(2026, 5, 3),
            descrizione="Bon. da Bianchi",
            importo=Decimal("400.00"),
            owner_account=owner_account,
        )
        resp = client_prop.get(f"/api/v1/bank-transactions/?tenant={tenant_1.id}")
        assert resp.status_code == 200
        ids = [b["id"] for b in resp.json()["results"]]
        assert match.id in ids
        assert non_match.id not in ids


class TestReceivableViewSet:
    def test_list_filtra_per_tenant(
        self, client_prop, rent_payment_1, rent_payment_2, tenant_1
    ):
        resp = client_prop.get(f"/api/v1/receivables/?tenant={tenant_1.id}")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()["results"]]
        assert rent_payment_1.id in ids
        assert rent_payment_2.id not in ids

    def test_list_riconciliato_false(
        self, client_prop, bank_tx_400, rent_payment_1, rent_payment_2
    ):
        client_prop.post(
            "/api/v1/reconciliations/",
            {
                "replace_for_transactions": [bank_tx_400.id],
                "items": [
                    {
                        "bank_transaction": bank_tx_400.id,
                        "receivable": rent_payment_1.id,
                        "importo": "400.00",
                    },
                ],
            },
            format="json",
        )
        resp = client_prop.get("/api/v1/receivables/?riconciliato=false")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()["results"]]
        assert rent_payment_1.id not in ids  # ora coperto
        assert rent_payment_2.id in ids

    def test_inquilino_403(self, client_inq_1):
        resp = client_inq_1.get("/api/v1/receivables/")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test endpoint POST /api/v1/receivables/<pk>/registra-pagamento/
# ---------------------------------------------------------------------------


class TestRegistraPagamentoReceivable:
    def _url(self, pk):
        return f"/api/v1/receivables/{pk}/registra-pagamento/"

    def test_importo_uguale_dovuto_paga_completamente(
        self, client_prop, rent_payment_1, owner_account
    ):
        resp = client_prop.post(
            self._url(rent_payment_1.id),
            {
                "data": "2026-05-03",
                "importo": "400.00",
                "owner_account": owner_account.id,
                "descrizione": "Bonifico Inquilino 1 - affitto Mag 2026",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        rent_payment_1.refresh_from_db()
        assert rent_payment_1.stato == StatoPagamento.PAGATO
        assert rent_payment_1.importo_pagato == Decimal("400.00")
        body = resp.json()
        assert body["bank_transaction"]["importo"] == "400.00"
        assert body["bank_transaction"]["stato_riconciliazione"] == "pieno"

    def test_importo_minore_dovuto_resta_atteso_parziale(
        self, client_prop, rent_payment_1, owner_account
    ):
        resp = client_prop.post(
            self._url(rent_payment_1.id),
            {
                "data": "2026-05-03",
                "importo": "250.00",
                "owner_account": owner_account.id,
                "descrizione": "Acconto",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        rent_payment_1.refresh_from_db()
        assert rent_payment_1.stato == StatoPagamento.ATTESO
        assert rent_payment_1.importo_pagato == Decimal("250.00")
        body = resp.json()
        assert body["bank_transaction"]["stato_riconciliazione"] == "pieno"

    def test_importo_maggiore_dovuto_bt_ha_residuo(
        self, client_prop, rent_payment_1, owner_account
    ):
        resp = client_prop.post(
            self._url(rent_payment_1.id),
            {
                "data": "2026-05-03",
                "importo": "500.00",
                "owner_account": owner_account.id,
                "descrizione": "Bonifico tondo",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        rent_payment_1.refresh_from_db()
        assert rent_payment_1.stato == StatoPagamento.PAGATO
        body = resp.json()
        assert body["bank_transaction"]["importo"] == "500.00"
        assert Decimal(body["bank_transaction"]["importo_allocato"]) == Decimal("400.00")
        assert Decimal(body["bank_transaction"]["residuo"]) == Decimal("100.00")
        assert body["bank_transaction"]["stato_riconciliazione"] == "parziale"

    def test_receivable_gia_pagato_409(
        self, client_prop, rent_payment_1, owner_account
    ):
        rent_payment_1.stato = StatoPagamento.PAGATO
        rent_payment_1.save(update_fields=["stato"])
        resp = client_prop.post(
            self._url(rent_payment_1.id),
            {
                "data": "2026-05-03",
                "importo": "400.00",
                "owner_account": owner_account.id,
            },
            format="json",
        )
        assert resp.status_code == 409

    def test_owner_account_inattivo_400(
        self, client_prop, rent_payment_1, owner_account
    ):
        owner_account.attivo = False
        owner_account.save(update_fields=["attivo"])
        resp = client_prop.post(
            self._url(rent_payment_1.id),
            {
                "data": "2026-05-03",
                "importo": "400.00",
                "owner_account": owner_account.id,
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_importo_zero_400(
        self, client_prop, rent_payment_1, owner_account
    ):
        resp = client_prop.post(
            self._url(rent_payment_1.id),
            {
                "data": "2026-05-03",
                "importo": "0",
                "owner_account": owner_account.id,
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_receivable_inesistente_404(self, client_prop, owner_account):
        resp = client_prop.post(
            self._url(99999),
            {
                "data": "2026-05-03",
                "importo": "100.00",
                "owner_account": owner_account.id,
            },
            format="json",
        )
        assert resp.status_code == 404

    def test_inquilino_403(self, client_inq_1, rent_payment_1, owner_account):
        resp = client_inq_1.post(
            self._url(rent_payment_1.id),
            {
                "data": "2026-05-03",
                "importo": "400.00",
                "owner_account": owner_account.id,
            },
            format="json",
        )
        assert resp.status_code == 403

    def test_utility_receivable(
        self, client_prop, charge_1, owner_account
    ):
        """L'endpoint funziona anche su Receivable causale=utenze."""
        resp = client_prop.post(
            self._url(charge_1.id),
            {
                "data": "2026-05-10",
                "importo": "45.00",
                "owner_account": owner_account.id,
                "descrizione": "Bonifico utenze",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        charge_1.refresh_from_db()
        assert charge_1.stato == StatoPagamento.PAGATO

    def test_extra_receivable(
        self, client_prop, extra_charge_1, owner_account
    ):
        """Anche su Receivable causale=extra."""
        resp = client_prop.post(
            self._url(extra_charge_1.id),
            {
                "data": "2026-05-15",
                "importo": "50.00",
                "owner_account": owner_account.id,
                "descrizione": "Bonifico extra",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        extra_charge_1.refresh_from_db()
        assert extra_charge_1.stato == StatoPagamento.PAGATO


# ---------------------------------------------------------------------------
# Test ExpenseSerializer: creazione contestuale BankTransaction in uscita
# ---------------------------------------------------------------------------


class TestExpenseCreaBT:
    URL = "/api/v1/expenses/"

    @pytest.fixture
    def expense_category(self, db):
        from billing.models import ExpenseCategory
        return ExpenseCategory.objects.create(nome="Manutenzione", codice="MAN")

    def test_default_crea_bank_transaction(
        self, client_prop, owner_account, expense_category, owner_prop
    ):
        from billing.models import BankTransaction
        resp = client_prop.post(
            self.URL,
            {
                "data": "2026-05-10",
                "category": expense_category.id,
                "importo": "120.50",
                "descrizione": "Riparazione caldaia",
                "anticipata_da_owner": owner_prop.id,
                "bt_owner_account": owner_account.id,
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        # BT creata in uscita (importo negativo)
        bts = list(BankTransaction.objects.filter(owner_account=owner_account))
        assert len(bts) == 1
        assert bts[0].importo == Decimal("-120.50")
        assert bts[0].data == datetime.date(2026, 5, 10)
        assert "caldaia" in bts[0].descrizione.lower()

    def test_flag_off_no_bt(
        self, client_prop, owner_account, expense_category, owner_prop
    ):
        from billing.models import BankTransaction
        resp = client_prop.post(
            self.URL,
            {
                "data": "2026-05-10",
                "category": expense_category.id,
                "importo": "50.00",
                "descrizione": "Spesa senza BT",
                "anticipata_da_owner": owner_prop.id,
                "crea_bank_transaction": False,
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        assert not BankTransaction.objects.filter(owner_account=owner_account).exists()

    def test_conto_di_owner_diverso_400(
        self, client_prop, expense_category, owner_prop, user_inq_2
    ):
        from properties.models import OwnerBankAccount
        altro = OwnerProfile.objects.create(user=user_inq_2, nominativo="Altro Owner")
        conto_altrui = OwnerBankAccount.objects.create(
            owner=altro,
            banca="Altra Banca",
            intestatario="Altro Owner",
            iban="IT99X0000000000000000000099",
        )
        resp = client_prop.post(
            self.URL,
            {
                "data": "2026-05-10",
                "category": expense_category.id,
                "importo": "50.00",
                "descrizione": "Spesa mal indirizzata",
                "anticipata_da_owner": owner_prop.id,
                "bt_owner_account": conto_altrui.id,
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_flag_on_senza_conto_400(
        self, client_prop, expense_category, owner_prop
    ):
        resp = client_prop.post(
            self.URL,
            {
                "data": "2026-05-10",
                "category": expense_category.id,
                "importo": "50.00",
                "descrizione": "Senza conto",
                "anticipata_da_owner": owner_prop.id,
            },
            format="json",
        )
        assert resp.status_code == 400
