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
from properties.models import (
    OwnerProfile,
    PropertyMembership,
    Room,
    RoomAssignment,
    TenantProfile,
)


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
    u = User.objects.create_user("bp_prop", email="prop@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
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
def tenant_1(db, user_inq_1, immobile):
    return TenantProfile.objects.create(
        property=immobile,
        user=user_inq_1, nominativo="Inquilino Billing 1", giorno_pagamento_affitto=1
    )


@pytest.fixture
def tenant_2(db, user_inq_2, immobile):
    return TenantProfile.objects.create(
        property=immobile,
        user=user_inq_2, nominativo="Inquilino Billing 2", giorno_pagamento_affitto=5
    )


@pytest.fixture
def room_1(db, immobile):
    return Room.objects.create(property=immobile, nome="Camera Billing A", ordinamento=20)


@pytest.fixture
def room_2(db, immobile):
    return Room.objects.create(property=immobile, nome="Camera Billing B", ordinamento=21)


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
def period(db, immobile):
    return UtilityChargePeriod.objects.create(
        property=immobile,
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
def period_maggio(db, immobile):
    return UtilityChargePeriod.objects.create(
        property=immobile,
        periodo_da=datetime.date(2026, 5, 1),
        periodo_a=datetime.date(2026, 5, 31),
        stato="inviato",
        tot_luce=Decimal("180.00"),
        tot_gas=Decimal("22.00"),
        tot_tari=Decimal("44.00"),
        giorni_totali=139,
    )


@pytest.fixture
def charge_maggio(db, period_maggio, assignment_1):
    # Quota dell'inquilino GIÀ ripartita sui suoi 15 giorni di presenza:
    # il conguaglio deve sommarla per intero, senza ulteriore pro-rata.
    return Receivable.objects.create(
        utility_period=period_maggio,
        assignment=assignment_1,
        causale=Receivable.Causale.UTENZE,
        competenza_da=period_maggio.periodo_da,
        competenza_a=period_maggio.periodo_a,
        importo_dovuto=Decimal("26.69"),
        giorni_presenza=15,
        scadenza=datetime.date(2026, 6, 5),
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

    def test_da_pagare_espone_dovuto_pagato_residuo(
        self, client_inq_1, tenant_1, rent_payment_1
    ):
        """Ogni voce 'da pagare' espone dovuto/pagato/residuo/parziale."""
        resp = client_inq_1.get("/api/v1/dashboard/inquilino/")
        item = resp.json()["da_pagare"][0]
        assert item["importo_dovuto"] == 400.0
        assert item["importo_pagato"] == 0.0
        assert item["residuo"] == 400.0
        assert item["parziale"] is False

    def test_da_pagare_parziale(self, client_inq_1, tenant_1, rent_payment_1):
        """Un addebito con versamento parziale espone residuo e flag parziale."""
        rent_payment_1.importo_pagato = Decimal("250")
        rent_payment_1.save(update_fields=["importo_pagato"])
        resp = client_inq_1.get("/api/v1/dashboard/inquilino/")
        item = resp.json()["da_pagare"][0]
        assert item["importo_pagato"] == 250.0
        assert item["residuo"] == 150.0
        assert item["parziale"] is True

    def test_da_pagare_allocazioni_vuote_default(
        self, client_inq_1, tenant_1, rent_payment_1
    ):
        """Senza bonifici abbinati, ogni voce espone `allocazioni` come lista vuota."""
        resp = client_inq_1.get("/api/v1/dashboard/inquilino/")
        item = resp.json()["da_pagare"][0]
        assert item["allocazioni"] == []

    def test_da_pagare_allocazioni_da_bonifico(
        self, client_inq_1, tenant_1, rent_payment_1, owner_account
    ):
        """Un bonifico parzialmente imputato compare in `allocazioni` con
        data, quota e importo lordo del bonifico."""
        from billing.models import BankTransaction, BankTransactionAllocation

        rent_payment_1.importo_pagato = Decimal("250")
        rent_payment_1.save(update_fields=["importo_pagato"])
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 5, 3),
            descrizione="Bonifico inquilino",
            importo=Decimal("300"),
            owner_account=owner_account,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=rent_payment_1, importo=Decimal("250")
        )

        resp = client_inq_1.get("/api/v1/dashboard/inquilino/")
        item = resp.json()["da_pagare"][0]
        assert len(item["allocazioni"]) == 1
        alloc = item["allocazioni"][0]
        assert alloc["data"] == "2026-05-03"
        assert alloc["quota"] == 250.0
        assert alloc["bonifico_totale"] == 300.0

    def test_pagamento_none_senza_conto(self, client_inq_1, tenant_1, rent_payment_1):
        """Senza proprietà/conto configurato il blocco pagamento è None."""
        resp = client_inq_1.get("/api/v1/dashboard/inquilino/")
        item = resp.json()["da_pagare"][0]
        assert item["pagamento"] is None

    def test_pagamento_qr_con_conto_valido(
        self, client_inq_1, tenant_1, charge_1, room_1, owner_prop, immobile
    ):
        """Con proprietà + conto a IBAN valido, le utenze espongono i dati QR."""
        from properties.models import OwnerBankAccount

        conto = OwnerBankAccount.objects.create(
            owner=owner_prop, banca="Webank",
            intestatario="Alessandro Dentella",
            iban="IT72I0503401799000000081536",
        )
        immobile.bank_account_utenze = conto
        immobile.save(update_fields=["bank_account_utenze"])

        resp = client_inq_1.get("/api/v1/dashboard/inquilino/")
        util = next(
            i for i in resp.json()["da_pagare"] if i["tipo"] == "utility_charge"
        )
        assert util["pagamento"] is not None
        assert util["pagamento"]["iban"] == "IT72I0503401799000000081536"
        assert util["pagamento"]["beneficiario"] == "Alessandro Dentella"
        assert tenant_1.nominativo in util["pagamento"]["causale"]

        # Saldo totale cumulativo: importo = somma residui, conto utenze immobile.
        saldo = resp.json()["saldo_totale"]
        assert saldo["importo"] > 0
        assert saldo["pagamento"]["iban"] == "IT72I0503401799000000081536"
        assert tenant_1.nominativo in saldo["pagamento"]["causale"]


def test_iban_valido():
    """Validazione IBAN: reali validi, placeholder/checksum errati rifiutati."""
    from billing._payments import iban_valido

    assert iban_valido("IT72I0503401799000000081536")
    assert iban_valido("IT72 I050 3401 7990 0000 0081 536")  # con spazi
    assert not iban_valido(None)
    assert not iban_valido("1234")
    assert not iban_valido("BRUNA-PLACEHOLDER")
    assert not iban_valido("IT00X0000000000000000000000")  # checksum errato

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
        self, client_prop, owner_alessandro, user_inq_2, immobile
    ):
        from billing.models import Expense, ExpenseCategory
        anno = datetime.date.today().year
        cat = ExpenseCategory.objects.create(property=immobile, nome="Spese condominiali")
        altro = OwnerProfile.objects.create(user=user_inq_2, nominativo="Altro")
        Expense.objects.create(
            property=immobile,
            data=datetime.date(anno, 3, 23),
            category=cat,
            importo=Decimal("1000"),
            descrizione="Rata 3",
            anticipata_da_owner=owner_alessandro,
        )
        Expense.objects.create(
            property=immobile,
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

    def test_situazione_inquilino_accede_al_proprio(self, client_inq_1, tenant_1):
        resp = client_inq_1.get(f"/api/v1/tenants/{tenant_1.id}/situazione/")
        assert resp.status_code == 200
        assert resp.json()["tenant"]["id"] == tenant_1.id

    def test_situazione_inquilino_non_accede_ad_altri_403(
        self, client_inq_1, tenant_2
    ):
        resp = client_inq_1.get(f"/api/v1/tenants/{tenant_2.id}/situazione/")
        assert resp.status_code == 403

    def test_situazione_tenant_inesistente_404(self, client_prop):
        resp = client_prop.get("/api/v1/tenants/99999/situazione/")
        assert resp.status_code == 404

    def test_situazione_anno_invalido_400(self, client_prop, tenant_1):
        resp = client_prop.get(f"/api/v1/tenants/{tenant_1.id}/situazione/?anno=abc")
        assert resp.status_code == 400

    def test_situazione_versamento_deposito_sempre_visibile(
        self, client_prop, tenant_1, assignment_1
    ):
        # Senza data di restituzione il versamento compare comunque nel suo
        # anno di competenza, ma NON entra nei totali dell'anno.
        tenant_1.deposito_versato = Decimal("1500")
        tenant_1.data_versamento_deposito = datetime.date(2024, 9, 1)
        tenant_1.save()
        resp = client_prop.get(f"/api/v1/tenants/{tenant_1.id}/situazione/?anno=2024")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["deposito"]["righe"]) == 1
        assert data["deposito"]["righe"][0]["importo"] == 1500.0
        assert data["deposito"]["dovuto_anno"] == 1500.0
        # Il deposito è escluso dai totali dell'anno.
        assert data["totali_anno"]["dovuto"] == 0.0

    def test_situazione_restituzione_nascosta_senza_data(
        self, client_prop, tenant_1, assignment_1
    ):
        # Versamento 2024, nessuna data di restituzione: nel 2026 non c'è
        # nessuna riga deposito (la restituzione non è ancora contabilizzata).
        tenant_1.deposito_versato = Decimal("1500")
        tenant_1.data_versamento_deposito = datetime.date(2024, 9, 1)
        tenant_1.save()
        resp = client_prop.get(f"/api/v1/tenants/{tenant_1.id}/situazione/?anno=2026")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deposito"]["righe"] == []
        assert data["deposito"]["dovuto_anno"] == 0.0

    def test_situazione_deposito_presente_dopo_restituzione(
        self, client_prop, tenant_1, assignment_1
    ):
        tenant_1.deposito_versato = Decimal("1500")
        tenant_1.data_versamento_deposito = datetime.date(2024, 9, 1)
        tenant_1.deposito_da_restituire = Decimal("1500")
        tenant_1.data_restituzione_prevista = datetime.date(2026, 4, 30)
        tenant_1.save()
        resp = client_prop.get(f"/api/v1/tenants/{tenant_1.id}/situazione/?anno=2026")
        assert resp.status_code == 200
        data = resp.json()
        # Solo la restituzione cade nell'anno 2026 (il versamento è del 2024).
        assert len(data["deposito"]["righe"]) == 1
        assert data["deposito"]["righe"][0]["importo"] == -1500.0
        assert data["deposito"]["dovuto_anno"] == -1500.0
        # Il deposito (anche la restituzione) è escluso dai totali dell'anno.
        assert data["totali_anno"]["dovuto"] == 0.0


class TestRendiconto:
    def test_inquilino_accede_al_proprio(self, client_inq_1, tenant_1):
        resp = client_inq_1.get(
            f"/api/v1/tenants/{tenant_1.id}/rendiconto/"
        )
        assert resp.status_code == 200

    def test_inquilino_non_accede_ad_altri_403(self, client_inq_1, tenant_2):
        resp = client_inq_1.get(
            f"/api/v1/tenants/{tenant_2.id}/rendiconto/"
        )
        assert resp.status_code == 403

    def test_tenant_inesistente_404(self, client_prop):
        resp = client_prop.get("/api/v1/tenants/99999/rendiconto/")
        assert resp.status_code == 404

    def test_storico_differenze_e_chiusura(
        self, client_prop, tenant_1, assignment_1, rent_payment_1, extra_charge_1
    ):
        # rent_payment_1: 400 dovuto, non pagato → nota 'non_pagata'
        tenant_1.deposito_versato = Decimal("1000")
        tenant_1.data_versamento_deposito = datetime.date(2024, 9, 1)
        tenant_1.data_restituzione_prevista = datetime.date(2026, 6, 30)
        tenant_1.save()

        resp = client_prop.get(
            f"/api/v1/tenants/{tenant_1.id}/rendiconto/"
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["tenant"]["id"] == tenant_1.id
        causali = {s["causale"]: s for s in data["sezioni"]}
        assert "affitto" in causali
        riga_affitto = causali["affitto"]["righe"][0]
        assert riga_affitto["dovuto"] == 400.0
        assert riga_affitto["pagato"] == 0.0
        assert riga_affitto["diff"] == -400.0
        assert riga_affitto["nota"] == "non_pagata"

        # Totali e saldo (400 affitto + 50 extra, nulla pagato)
        assert data["totali"]["dovuto"] == 450.0
        assert data["totali"]["pagato"] == 0.0
        assert data["totali"]["saldo"] == -450.0

        # Chiusura: da_restituire = versato (no override) = 1000
        dep = data["deposito"]
        assert dep["versato"] == 1000.0
        assert dep["da_restituire"] == 1000.0
        assert dep["override"] is False
        assert dep["restituito_effettivo"] is False
        # netto = 1000 + (-450) = 550
        assert dep["netto_da_restituire"] == 550.0
        assert dep["residuo_debito"] == 0.0

    def test_bonifico_split_allocazioni_e_ledger(
        self, client_prop, tenant_1, assignment_1, rent_payment_1,
        extra_charge_1, owner_account,
    ):
        """Un bonifico unico (450) imputato 400 affitto + 50 extra: la riga
        affitto espone l'allocazione 'split' e il ledger la ripartizione."""
        from billing.models import BankTransaction, BankTransactionAllocation

        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 5, 10),
            descrizione="Bonifico cumulativo",
            importo=Decimal("450.00"),
            owner_account=owner_account,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=rent_payment_1,
            importo=Decimal("400.00"),
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=extra_charge_1,
            importo=Decimal("50.00"),
        )

        resp = client_prop.get(
            f"/api/v1/tenants/{tenant_1.id}/rendiconto/"
        )
        assert resp.status_code == 200
        data = resp.json()

        causali = {s["causale"]: s for s in data["sezioni"]}
        ra = causali["affitto"]["righe"][0]
        assert ra["pagato"] == 400.0
        assert len(ra["allocazioni"]) == 1
        al = ra["allocazioni"][0]
        assert al["bonifico_totale"] == 450.0
        assert al["quota"] == 400.0
        assert al["split"] is True
        # diff per mese affitti = bonifico lordo del mese − affitto dovuto
        # del mese: 450 − 400 = +50 (i 50 andati a copertura dell'extra).
        assert ra["diff_mese"] == 50.0

        # Ledger versamenti: un bonifico con 2 imputazioni
        assert len(data["versamenti"]) == 1
        v = data["versamenti"][0]
        assert v["importo"] == 450.0
        assert {i["causale"] for i in v["imputazioni"]} == {"affitto", "extra"}
        assert data["totale_versato"] == 450.0

        # Parziali per anno: 2026 con dovuto 450, pagato 450
        pa2026 = [p for p in data["parziali_anno"] if p["anno"] == 2026]
        assert pa2026 and pa2026[0]["dovuto"] == 450.0
        assert pa2026[0]["pagato"] == 450.0

    def test_resto_bonifico_in_sbilancio_reale(
        self, client_prop, tenant_1, assignment_1, rent_payment_1,
        owner_account,
    ):
        """Un bonifico che copre *di più* (450 su affitto da 400, 400
        imputati): i 50 di resto non vanno persi. Saldo-imputazioni = 0,
        ma sbilancio reale = +50, riportato per anno e nel progressivo."""
        from billing.models import BankTransaction, BankTransactionAllocation

        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 5, 10),
            descrizione="Bonifico con resto",
            importo=Decimal("450.00"),
            owner_account=owner_account,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=rent_payment_1,
            importo=Decimal("400.00"),
        )

        resp = client_prop.get(
            f"/api/v1/tenants/{tenant_1.id}/rendiconto/"
        )
        assert resp.status_code == 200
        data = resp.json()

        # saldo-imputazioni nullo (400 imputati su 400 dovuti)
        assert data["totali"]["saldo"] == 0.0
        # i 50 di resto entrano nello sbilancio reale
        assert data["totali"]["resto"] == 50.0
        assert data["totali"]["sbilancio_reale"] == 50.0

        pa = next(p for p in data["parziali_anno"] if p["anno"] == 2026)
        assert pa["saldo"] == 0.0
        assert pa["resto"] == 50.0
        assert pa["saldo_anno"] == 50.0
        assert pa["saldo_progressivo"] == 50.0

        # La voce-receivable resta ONESTA: diff = pagato − dovuto = 0.
        # Il resto è una riga propria sotto il bonifico portante
        # (allocazioni[].resto = +50), non inquina la differenza voce.
        ra = next(
            r for s in data["sezioni"] if s["causale"] == "affitto"
            for r in s["righe"]
        )
        assert ra["diff"] == 0.0
        assert "diff_tracc" not in ra
        assert "resto" not in ra
        assert ra["allocazioni"][0]["resto"] == 50.0
        # Colonna a vista (diff voci + resti bonifici) = saldo dell'anno.
        somma = 0.0
        for s in data["sezioni"]:
            for r in s["righe"]:
                if r["data"] and r["data"][:4] == "2026":
                    somma += r["diff"]
                    somma += sum(a["resto"] for a in r["allocazioni"])
        assert round(somma, 2) == pa["saldo_anno"]

    def test_situazione_saldo_e_progressivo_reale(
        self, client_prop, tenant_1, assignment_1, rent_payment_1,
        owner_account,
    ):
        """``saldi.anno`` e ``saldi.totale`` del dettaglio inquilino usano
        lo stesso sbilancio reale (con i resti) del rendiconto."""
        from billing.models import BankTransaction, BankTransactionAllocation

        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 5, 10),
            descrizione="Bonifico con resto",
            importo=Decimal("450.00"),
            owner_account=owner_account,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=rent_payment_1,
            importo=Decimal("400.00"),
        )

        resp = client_prop.get(
            f"/api/v1/tenants/{tenant_1.id}/situazione/?anno=2026"
        )
        assert resp.status_code == 200
        saldi = resp.json()["saldi"]
        assert saldi["anno"] == 50.0
        assert saldi["totale"] == 50.0

    def test_override_importo_da_restituire(
        self, client_prop, tenant_1, assignment_1
    ):
        tenant_1.deposito_versato = Decimal("400")
        tenant_1.deposito_da_restituire = Decimal("530")
        tenant_1.data_restituzione_prevista = datetime.date(2026, 6, 30)
        tenant_1.save()

        resp = client_prop.get(
            f"/api/v1/tenants/{tenant_1.id}/rendiconto/"
        )
        assert resp.status_code == 200
        dep = resp.json()["deposito"]
        assert dep["versato"] == 400.0
        assert dep["da_restituire"] == 530.0
        assert dep["override"] is True


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

    def test_restituzione_caparra(self, client_prop, owner_account, assignment_1):
        """Receivable DEPOSITO negativo + BT uscita negativa + allocation
        negativa → stato PAGATO. Caso restituzione caparra."""
        from billing.models import BankTransaction
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 6, 30),
            descrizione="Restituzione caparra inquilino X",
            importo=Decimal("-900.00"),
            owner_account=owner_account,
        )
        receivable_dep = Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.DEPOSITO,
            descrizione="Deposito (restituzione)",
            competenza_da=datetime.date(2026, 6, 30),
            scadenza=datetime.date(2026, 6, 30),
            importo_dovuto=Decimal("-900.00"),
            stato=StatoPagamento.ATTESO,
        )
        resp = client_prop.post(
            self.URL,
            {
                "replace_for_transactions": [bt.id],
                "items": [
                    {
                        "bank_transaction": bt.id,
                        "receivable": receivable_dep.id,
                        "importo": "-900.00",
                    },
                ],
            },
            format="json",
        )
        assert resp.status_code == 200, resp.content
        receivable_dep.refresh_from_db()
        assert receivable_dep.stato == StatoPagamento.PAGATO
        assert receivable_dep.importo_pagato == Decimal("-900.00")
        assert receivable_dep.data_pagamento == datetime.date(2026, 6, 30)

    def test_segni_discordi_400(self, client_prop, bank_tx_400, assignment_1):
        """alloc(+400) su Receivable -400 → segno discorde alloc/Receivable."""
        receivable_neg = Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.DEPOSITO,
            descrizione="Deposito (restituzione)",
            competenza_da=datetime.date(2026, 6, 30),
            scadenza=datetime.date(2026, 6, 30),
            importo_dovuto=Decimal("-400.00"),
            stato=StatoPagamento.ATTESO,
        )
        resp = client_prop.post(
            self.URL,
            {
                "replace_for_transactions": [bank_tx_400.id],
                "items": [
                    {
                        "bank_transaction": bank_tx_400.id,
                        "receivable": receivable_neg.id,
                        "importo": "400.00",
                    },
                ],
            },
            format="json",
        )
        assert resp.status_code == 400
        assert b"Segno discorde" in resp.content

    def test_bt_uscita_allocations_miste(
        self, client_prop, owner_account, assignment_1
    ):
        """BT -984 con alloc -1060 (Rec restituzione) + alloc +76 (Rec
        previsionale utenze): somma algebrica -984 = BT.importo, OK."""
        from billing.models import BankTransaction
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 5, 25),
            descrizione="Restituzione deposito Eshani (al netto)",
            importo=Decimal("-984.00"),
            owner_account=owner_account,
        )
        rec_restituzione = Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.DEPOSITO,
            descrizione="Deposito (restituzione)",
            competenza_da=datetime.date(2026, 5, 25),
            scadenza=datetime.date(2026, 5, 25),
            importo_dovuto=Decimal("-1060.00"),
            stato=StatoPagamento.ATTESO,
        )
        rec_previsionale = Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.EXTRA,
            descrizione="Previsionale utenze (uscita)",
            competenza_da=datetime.date(2026, 5, 25),
            scadenza=datetime.date(2026, 5, 25),
            importo_dovuto=Decimal("76.00"),
            stato=StatoPagamento.ATTESO,
        )
        resp = client_prop.post(
            self.URL,
            {
                "replace_for_transactions": [bt.id],
                "items": [
                    {
                        "bank_transaction": bt.id,
                        "receivable": rec_restituzione.id,
                        "importo": "-1060.00",
                    },
                    {
                        "bank_transaction": bt.id,
                        "receivable": rec_previsionale.id,
                        "importo": "76.00",
                    },
                ],
            },
            format="json",
        )
        assert resp.status_code == 200, resp.content
        rec_restituzione.refresh_from_db()
        rec_previsionale.refresh_from_db()
        assert rec_restituzione.stato == StatoPagamento.PAGATO
        assert rec_restituzione.importo_pagato == Decimal("-1060.00")
        assert rec_previsionale.stato == StatoPagamento.PAGATO
        assert rec_previsionale.importo_pagato == Decimal("76.00")

    def test_bt_somma_alloc_segno_opposto_400(
        self, client_prop, owner_account, assignment_1
    ):
        """BT -100 con somma allocazioni netta +50: somma di segno opposto
        alla BT non ha senso (es. due alloc +30 e +20 verso Rec positivi).
        """
        from billing.models import BankTransaction
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 5, 25),
            descrizione="BT uscita",
            importo=Decimal("-100.00"),
            owner_account=owner_account,
        )
        rec_pos = Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.EXTRA,
            descrizione="Extra inquilino",
            competenza_da=datetime.date(2026, 5, 25),
            scadenza=datetime.date(2026, 5, 25),
            importo_dovuto=Decimal("50.00"),
            stato=StatoPagamento.ATTESO,
        )
        resp = client_prop.post(
            self.URL,
            {
                "replace_for_transactions": [bt.id],
                "items": [
                    {
                        "bank_transaction": bt.id,
                        "receivable": rec_pos.id,
                        "importo": "50.00",
                    },
                ],
            },
            format="json",
        )
        assert resp.status_code == 400
        assert b"segno opposto" in resp.content

    def test_restituzione_supera_BT(self, client_prop, owner_account, assignment_1):
        """Allocation -1000 su BT -900 deve fallire: |alloc|>|BT|."""
        from billing.models import BankTransaction
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 6, 30),
            descrizione="Restituzione",
            importo=Decimal("-900.00"),
            owner_account=owner_account,
        )
        receivable_dep = Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.DEPOSITO,
            descrizione="Deposito (restituzione)",
            competenza_da=datetime.date(2026, 6, 30),
            scadenza=datetime.date(2026, 6, 30),
            importo_dovuto=Decimal("-1000.00"),
            stato=StatoPagamento.ATTESO,
        )
        resp = client_prop.post(
            self.URL,
            {
                "replace_for_transactions": [bt.id],
                "items": [
                    {
                        "bank_transaction": bt.id,
                        "receivable": receivable_dep.id,
                        "importo": "-1000.00",
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

    # Restituzione deposito: BT in uscita (importo negativo) → allocation
    # negativa sul Receivable a importo_dovuto negativo.
    @pytest.fixture
    def receivable_deposito_neg(self, db, assignment_1):
        return Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.DEPOSITO,
            descrizione="Deposito (restituzione)",
            competenza_da=datetime.date(2026, 5, 15),
            scadenza=datetime.date(2026, 5, 15),
            importo_dovuto=Decimal("-1060.00"),
            stato=StatoPagamento.ATTESO,
        )

    def test_restituzione_deposito_pagamento_parziale(
        self, client_prop, receivable_deposito_neg, owner_account
    ):
        """|importo| < |residuo|: alloca tutto l'importo, Receivable resta ATTESO."""
        resp = client_prop.post(
            self._url(receivable_deposito_neg.id),
            {
                "data": "2026-05-25",
                "importo": "-986.04",
                "owner_account": owner_account.id,
                "descrizione": "Restituzione deposito Eshani",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        receivable_deposito_neg.refresh_from_db()
        assert receivable_deposito_neg.importo_pagato == Decimal("-986.04")
        assert receivable_deposito_neg.stato == StatoPagamento.ATTESO
        body = resp.json()
        assert body["bank_transaction"]["importo"] == "-986.04"

    def test_restituzione_deposito_saldo_pieno(
        self, client_prop, receivable_deposito_neg, owner_account
    ):
        resp = client_prop.post(
            self._url(receivable_deposito_neg.id),
            {
                "data": "2026-05-25",
                "importo": "-1060.00",
                "owner_account": owner_account.id,
                "descrizione": "Restituzione deposito",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        receivable_deposito_neg.refresh_from_db()
        assert receivable_deposito_neg.stato == StatoPagamento.PAGATO
        assert receivable_deposito_neg.importo_pagato == Decimal("-1060.00")

    def test_segno_importo_positivo_su_deposito_400(
        self, client_prop, receivable_deposito_neg, owner_account
    ):
        """Receivable a dovuto negativo: importo positivo è incoerente."""
        resp = client_prop.post(
            self._url(receivable_deposito_neg.id),
            {
                "data": "2026-05-25",
                "importo": "100.00",
                "owner_account": owner_account.id,
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_segno_importo_negativo_su_affitto_400(
        self, client_prop, rent_payment_1, owner_account
    ):
        """Receivable a dovuto positivo: importo negativo è incoerente."""
        resp = client_prop.post(
            self._url(rent_payment_1.id),
            {
                "data": "2026-05-25",
                "importo": "-100.00",
                "owner_account": owner_account.id,
            },
            format="json",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Test ExpenseSerializer: creazione contestuale BankTransaction in uscita
# ---------------------------------------------------------------------------


class TestExpenseCreaBT:
    URL = "/api/v1/expenses/"

    @pytest.fixture
    def expense_category(self, db, immobile):
        from billing.models import ExpenseCategory
        return ExpenseCategory.objects.create(
            property=immobile, nome="Manutenzione", codice="MAN"
        )

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

    def test_anticipante_auto_dal_conto_bt(
        self, client_prop, owner_account, expense_category, owner_prop
    ):
        """Se la BT viene creata, l'anticipante è derivato dal conto BT
        anche se il client non lo invia."""
        from billing.models import Expense
        resp = client_prop.post(
            self.URL,
            {
                "data": "2026-05-10",
                "category": expense_category.id,
                "importo": "30.00",
                "descrizione": "Spesa senza anticipante esplicito",
                "bt_owner_account": owner_account.id,
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        exp = Expense.objects.get(pk=resp.json()["id"])
        assert exp.anticipata_da_owner_id == owner_account.owner_id == owner_prop.id

    def test_senza_categoria_400_field_error(
        self, client_prop, owner_account
    ):
        resp = client_prop.post(
            self.URL,
            {
                "data": "2026-05-10",
                "importo": "30.00",
                "descrizione": "Spesa senza categoria",
                "bt_owner_account": owner_account.id,
            },
            format="json",
        )
        assert resp.status_code == 400
        assert "category" in resp.json()


class TestExpenseCategoryEndpoint:
    URL = "/api/v1/expense-categories/"

    @pytest.fixture
    def categorie(self, db, immobile):
        from billing.models import ExpenseCategory
        return [
            ExpenseCategory.objects.create(property=immobile, nome="IMU", codice="imu"),
            ExpenseCategory.objects.create(property=immobile, nome="Manutenzione", codice="man"),
        ]

    def test_lista_per_proprietario(self, client_prop, categorie):
        resp = client_prop.get(self.URL)
        assert resp.status_code == 200, resp.content
        data = resp.json()
        nomi = sorted(c["nome"] for c in data)
        assert nomi == ["IMU", "Manutenzione"]

    def test_negato_per_inquilino(self, client_inq_1, categorie):
        resp = client_inq_1.get(self.URL)
        assert resp.status_code == 403


class TestTenantListSaldi:
    """``/api/v1/tenants/`` espone ``saldo`` (anno) e ``saldo_totale`` agli
    proprietari. Devono coincidere con ``saldi.anno`` / ``saldi.totale`` del
    dettaglio inquilino (sbilancio reale: imputazioni + resti dei bonifici)."""

    def test_saldo_lista_include_resto_bonifico(
        self, client_prop, tenant_1, assignment_1, rent_payment_1, owner_account,
    ):
        from billing.models import BankTransaction, BankTransactionAllocation

        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 5, 10),
            descrizione="Bonifico con resto",
            importo=Decimal("450.00"),
            owner_account=owner_account,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=rent_payment_1,
            importo=Decimal("400.00"),
        )

        resp = client_prop.get("/api/v1/tenants/?anno=2026")
        assert resp.status_code == 200
        riga = next(r for r in resp.json() if r["id"] == tenant_1.id)
        # Saldo-imputazioni puro = 0 (400 imputati su 400). I 50 di resto
        # devono entrare nello sbilancio reale.
        assert riga["saldo"] == 50.0
        assert riga["saldo_totale"] == 50.0

    def test_saldo_totale_senza_anno_e_totale_complessivo(
        self, client_prop, tenant_1, assignment_1, rent_payment_1, owner_account,
    ):
        from billing.models import BankTransaction, BankTransactionAllocation

        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 5, 10),
            descrizione="Bonifico con resto",
            importo=Decimal("450.00"),
            owner_account=owner_account,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=rent_payment_1,
            importo=Decimal("400.00"),
        )

        resp = client_prop.get("/api/v1/tenants/?solo_attivi=0")
        assert resp.status_code == 200
        riga = next(r for r in resp.json() if r["id"] == tenant_1.id)
        # Senza filtro anno la colonna saldo_totale è il totale complessivo.
        assert riga["saldo_totale"] == 50.0
        assert riga["saldo"] is None


class TestPrevisionaleEConguaglio:
    """Flusso: creazione previsionale utenze → conguaglio con utenze reali."""

    def _crea_previsionale(self, client_prop, tenant_1, assignment_1):
        return client_prop.post(
            f"/api/v1/tenants/{tenant_1.id}/previsionale-utenze/",
            {
                "assignment": assignment_1.id,
                "data_da": "2026-04-30",
                "data_a": "2026-05-15",
                "importo": "80.00",
            },
            format="json",
        )

    def test_post_crea_previsionale_marcato(
        self, client_prop, tenant_1, assignment_1
    ):
        resp = self._crea_previsionale(client_prop, tenant_1, assignment_1)
        assert resp.status_code == 201, resp.content
        body = resp.json()
        rec = Receivable.objects.get(pk=body["id"])
        assert rec.causale == Receivable.Causale.EXTRA
        assert rec.competenza_da == datetime.date(2026, 4, 30)
        assert rec.competenza_a == datetime.date(2026, 5, 15)
        assert rec.importo_dovuto == Decimal("80.00")
        assert "previsionale_utenze" in (rec.note or "")

    def test_post_previsionale_data_a_uguale_da_400(
        self, client_prop, tenant_1, assignment_1
    ):
        resp = client_prop.post(
            f"/api/v1/tenants/{tenant_1.id}/previsionale-utenze/",
            {
                "assignment": assignment_1.id,
                "data_da": "2026-05-15",
                "data_a": "2026-05-15",
                "importo": "50",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_conguaglio_anteprima_e_creazione(
        self, client_prop, tenant_1, assignment_1, charge_1, charge_maggio
    ):
        # Previsionale 30/4 → 15/5. charge_1 (apr, periodo_a=30/4) FINISCE su
        # data_da: è già fatturato a parte e va escluso (niente riga di bordo).
        # charge_maggio (mag, quota 26,69 già ripartita su 15 gg presenza) è
        # l'unica utenza reale del periodo: si somma per intero, senza pro-rata.
        prev_resp = self._crea_previsionale(client_prop, tenant_1, assignment_1)
        assert prev_resp.status_code == 201
        prev_id = prev_resp.json()["id"]

        # Anteprima (GET)
        ant_resp = client_prop.get(
            f"/api/v1/tenants/{tenant_1.id}/conguaglia-previsionale/?previsionale_id={prev_id}"
        )
        assert ant_resp.status_code == 200, ant_resp.content
        ant = ant_resp.json()
        assert ant["previsionale_id"] == prev_id
        assert ant["previsionale_importo"] == 80.0
        assert len(ant["utenze_reali"]) == 1
        riga = ant["utenze_reali"][0]
        assert riga["receivable_id"] == charge_maggio.id
        assert riga["giorni_presenza"] == 15
        # Nessun secondo pro-rata: quota = importo_dovuto pieno.
        assert riga["quota_nel_periodo"] == 26.69
        assert ant["somma_utenze_reali"] == 26.69
        assert ant["rettifica_proposta"] == -26.69
        assert ant["netto_a_favore_inquilino"] == 53.31

        # Salva conguaglio (POST)
        post_resp = client_prop.post(
            f"/api/v1/tenants/{tenant_1.id}/conguaglia-previsionale/",
            {"previsionale_id": prev_id},
            format="json",
        )
        assert post_resp.status_code == 201, post_resp.content
        body = post_resp.json()
        rett = Receivable.objects.get(pk=body["rettifica_id"])
        assert rett.causale == Receivable.Causale.EXTRA
        assert rett.importo_dovuto == Decimal("-26.69")
        assert f"conguaglio_previsionale:{prev_id}" in (rett.note or "")
        # Previsionale marcato come conguagliato
        prev = Receivable.objects.get(pk=prev_id)
        assert "conguaglio_previsionale" in (prev.note or "")

    def test_conguaglio_rifiuta_se_gia_conguagliato(
        self, client_prop, tenant_1, assignment_1, charge_maggio
    ):
        prev_id = self._crea_previsionale(
            client_prop, tenant_1, assignment_1
        ).json()["id"]
        ok = client_prop.post(
            f"/api/v1/tenants/{tenant_1.id}/conguaglia-previsionale/",
            {"previsionale_id": prev_id},
            format="json",
        )
        assert ok.status_code == 201
        ko = client_prop.post(
            f"/api/v1/tenants/{tenant_1.id}/conguaglia-previsionale/",
            {"previsionale_id": prev_id},
            format="json",
        )
        assert ko.status_code == 409
        assert b"gi\xc3\xa0 conguagliato" in ko.content

    def test_conguaglio_su_non_previsionale_400(
        self, client_prop, tenant_1, extra_charge_1
    ):
        """Un Receivable extra qualsiasi (non marcato previsionale) non è
        conguagliabile."""
        resp = client_prop.post(
            f"/api/v1/tenants/{tenant_1.id}/conguaglia-previsionale/",
            {"previsionale_id": extra_charge_1.id},
            format="json",
        )
        assert resp.status_code == 400

    def test_conguaglio_nessuna_utenza_409(
        self, client_prop, tenant_1, assignment_1
    ):
        """Se non ci sono utenze nel periodo, niente da conguagliare."""
        prev_id = self._crea_previsionale(
            client_prop, tenant_1, assignment_1
        ).json()["id"]
        resp = client_prop.post(
            f"/api/v1/tenants/{tenant_1.id}/conguaglia-previsionale/",
            {"previsionale_id": prev_id},
            format="json",
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Test Conto economico
# ---------------------------------------------------------------------------


class TestContoEconomico:
    @pytest.fixture
    def owner_ce(self, db, gruppo_proprietari):
        u = User.objects.create_user("ce_prop", email="ce@v.it", password="pwd123!")
        u.groups.add(gruppo_proprietari)
        return OwnerProfile.objects.create(user=u, nominativo="Owner CE")

    @pytest.fixture
    def quote_ce(self, db, owner_ce, immobile):
        from properties.models import OwnershipShare
        return OwnershipShare.objects.create(
            property=immobile,
            owner=owner_ce, valid_from=datetime.date(2020, 1, 1), quota=Decimal("1.0"),
        )

    @pytest.fixture
    def flussi_2025(self, db, assignment_1, owner_ce, immobile):
        """Affitto di dicembre 2025 pagato a gennaio 2026 + spesa ordinaria
        e straordinaria nel 2025."""
        from billing.models import Expense, ExpenseCategory
        Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(2025, 12, 1),
            competenza_a=datetime.date(2025, 12, 31),
            importo_dovuto=Decimal("400"),
            importo_pagato=Decimal("400"),
            scadenza=datetime.date(2025, 12, 5),
            data_pagamento=datetime.date(2026, 1, 8),
            stato=StatoPagamento.PAGATO,
            incassato_da_owner=owner_ce,
        )
        Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(2025, 11, 1),
            competenza_a=datetime.date(2025, 11, 30),
            importo_dovuto=Decimal("400"),
            importo_pagato=Decimal("400"),
            scadenza=datetime.date(2025, 11, 5),
            data_pagamento=datetime.date(2025, 11, 4),
            stato=StatoPagamento.PAGATO,
            incassato_da_owner=owner_ce,
        )
        cat = ExpenseCategory.objects.create(property=immobile, nome="IMU CE", codice="imu-ce")
        Expense.objects.create(
            property=immobile,
            data=datetime.date(2025, 6, 16),
            category=cat,
            importo=Decimal("300"),
            descrizione="IMU acconto",
            anticipata_da_owner=owner_ce,
        )
        Expense.objects.create(
            property=immobile,
            data=datetime.date(2025, 7, 1),
            category=cat,
            importo=Decimal("1000"),
            descrizione="Rifacimento bagno",
            anticipata_da_owner=owner_ce,
            is_straordinaria=True,
        )

    def test_cassa_vs_competenza(self, client_prop, quote_ce, flussi_2025):
        resp = client_prop.get("/api/v1/dashboard/conto-economico/?anno=2025")
        assert resp.status_code == 200
        body = resp.json()
        # Cassa 2025: solo l'affitto di novembre (quello di dicembre è
        # incassato a gennaio 2026).
        assert body["cassa"]["ricavi"]["rent"] == 400.0
        # Competenza 2025: entrambi i canoni maturano nel 2025.
        assert body["competenza"]["ricavi"]["rent"] == 800.0
        # Spese: 300 ordinarie, 1000 straordinarie in entrambe le letture.
        assert body["cassa"]["spese_ordinarie"] == 300.0
        assert body["cassa"]["spese_straordinarie"] == 1000.0
        assert body["cassa"]["margine_operativo"] == 100.0
        assert body["cassa"]["utile"] == -900.0
        assert body["competenza"]["utile"] == -500.0

    def test_utile_pro_quota_e_serie(self, client_prop, quote_ce, flussi_2025, owner_ce):
        resp = client_prop.get("/api/v1/dashboard/conto-economico/?anno=2025")
        body = resp.json()
        pq = body["utile_pro_quota"]
        assert len(pq) == 1
        assert pq[0]["owner_id"] == owner_ce.pk
        assert pq[0]["quota"] == 1.0
        assert pq[0]["utile_cassa"] == -900.0
        anni = {r["anno"]: r for r in body["serie_anni"]}
        assert anni[2025]["ricavi"] == 400.0
        assert anni[2025]["spese"] == 1300.0
        assert anni[2026]["ricavi"] == 400.0
        assert 2025 in body["anni_disponibili"] and 2026 in body["anni_disponibili"]

    def test_non_incassato_in_competenza(self, client_prop, quote_ce, assignment_1):
        Receivable.objects.create(
            assignment=assignment_1,
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(2025, 10, 1),
            competenza_a=datetime.date(2025, 10, 31),
            importo_dovuto=Decimal("400"),
            scadenza=datetime.date(2025, 10, 5),
            stato=StatoPagamento.IN_RITARDO,
        )
        resp = client_prop.get("/api/v1/dashboard/conto-economico/?anno=2025")
        body = resp.json()
        assert body["competenza"]["non_incassato"] == 400.0
        assert body["competenza"]["non_incassato_voci"] == 1

    def test_occupazione_anno_pieno(self, client_prop, quote_ce, assignment_1, room_2):
        # assignment_1: dal 2024-09-01, senza fine → camera A occupata tutto
        # il 2025; camera B mai occupata.
        resp = client_prop.get("/api/v1/dashboard/conto-economico/?anno=2025")
        body = resp.json()
        per_stanza = {o["stanza"]: o for o in body["occupazione"]["per_stanza"]}
        assert per_stanza["Camera Billing A"]["tasso"] == 1.0
        assert per_stanza["Camera Billing B"]["tasso"] == 0.0
        assert body["occupazione"]["tasso_medio"] == 0.5

    def test_inquilino_non_accede(self, client_inq_1):
        resp = client_inq_1.get("/api/v1/dashboard/conto-economico/")
        assert resp.status_code == 403

    def test_anno_invalido_400(self, client_prop):
        resp = client_prop.get("/api/v1/dashboard/conto-economico/?anno=abc")
        assert resp.status_code == 400
