"""
Test per il flusso di emissione utenze esposto da UtilityChargePeriodViewSet:
``per-mese`` (trova-o-crea), ``anteprima`` (dry-run) e ``emetti`` (persist).
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()


def _proprietario():
    user = User.objects.create_user(username="propr_em", password="x")
    grp, _ = Group.objects.get_or_create(name="proprietari")
    user.groups.add(grp)
    return user


def _assignment_attivo():
    """Inquilino con assegnazione stanza attiva da inizio 2024 (no scadenza).

    Allineato alle fixture del conftest: ``Room`` senza ``Building`` né
    ``Contract`` (il calcolo utenze usa solo l'overlap di RoomAssignment).
    """
    from properties.models import Room, RoomAssignment, TenantProfile

    room = Room.objects.create(nome="Camera Emissione", ordinamento=30)
    tenant_user = User.objects.create_user(username="tenant_em", password="x")
    tenant = TenantProfile.objects.create(
        user=tenant_user, nominativo="Mario Rossi", giorno_pagamento_affitto=1
    )
    assignment = RoomAssignment.objects.create(
        tenant=tenant,
        room=room,
        valid_from=datetime.date(2024, 1, 1),
        canone_mensile=Decimal("400.00"),
    )
    return tenant, assignment


def _bolletta(prodotto, importo, da, a):
    from billing.models import Supplier, UtilityBill

    supplier, _ = Supplier.objects.get_or_create(
        nome=f"Forn-{prodotto}",
        defaults={"tipo": Supplier.TipoFornitore.ALTRO},
    )
    return UtilityBill.objects.create(
        supplier=supplier,
        prodotto=prodotto,
        numero_fattura=f"{prodotto}-{da}",
        data_emissione=a,
        periodo_da=da,
        periodo_a=a,
        importo_totale=Decimal(importo),
    )


def _client():
    c = APIClient()
    c.force_authenticate(user=_proprietario())
    return c


class TestPerMese:
    def test_crea_periodo_se_assente(self):
        c = _client()
        resp = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6})
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["created"] is True
        assert body["period"]["periodo_da"] == "2025-06-01"
        assert body["period"]["periodo_a"] == "2025-06-30"
        assert body["completezza"]["completo"] is False  # nessuna bolletta

    def test_riusa_periodo_esistente(self):
        c = _client()
        first = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 7})
        second = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 7})
        assert second.json()["created"] is False
        assert first.json()["period"]["id"] == second.json()["period"]["id"]

    def test_parametri_mancanti(self):
        c = _client()
        resp = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025})
        assert resp.status_code == 400


class TestAnteprimaEmetti:
    def test_completezza_e_anteprima(self):
        _assignment_attivo()
        _bolletta("luce", "100.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        _bolletta("gas", "60.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        c = _client()

        per_mese = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6})
        body = per_mese.json()
        assert body["completezza"]["luce"] is True
        assert body["completezza"]["gas"] is True
        assert body["completezza"]["completo"] is True
        pid = body["period"]["id"]

        ant = c.get(f"/api/v1/utility-periods/{pid}/anteprima/")
        assert ant.status_code == 200, ant.content
        quote = ant.json()["quote"]
        assert len(quote) == 1
        assert quote[0]["tenant_nominativo"] == "Mario Rossi"
        assert Decimal(str(quote[0]["quota"])) > 0

    def test_emetti_crea_receivable_e_inviato(self):
        from billing.models import Receivable

        _assignment_attivo()
        _bolletta("luce", "100.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        _bolletta("gas", "60.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        c = _client()
        pid = c.get(
            "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6}
        ).json()["period"]["id"]

        resp = c.post(f"/api/v1/utility-periods/{pid}/emetti/")
        assert resp.status_code == 200, resp.content
        assert resp.json()["period"]["stato"] == "inviato"
        rec = Receivable.objects.filter(
            causale=Receivable.Causale.UTENZE, utility_period_id=pid
        )
        assert rec.count() == 1
        assert rec.first().importo_dovuto > 0

    def test_emetti_blocca_periodo_incompleto(self):
        c = _client()
        pid = c.get(
            "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 9}
        ).json()["period"]["id"]
        resp = c.post(f"/api/v1/utility-periods/{pid}/emetti/")
        assert resp.status_code == 400
        assert resp.json()["completezza"]["completo"] is False
