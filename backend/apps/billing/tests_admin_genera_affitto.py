"""
Test della pagina admin "Genera Receivable affitto": tendina dipendente
(endpoint tenants JSON) e validazione tenant-nel-mese del form.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from billing.admin_views import (
    GeneraReceivableAffittoForm,
    _tenants_attivi_nel_mese,
)
from properties.models import Room, RoomAssignment, TenantProfile


@pytest.fixture
def make_tenant(db, immobile):
    counter = [0]

    def _make(nominativo):
        counter[0] += 1
        u = User.objects.create_user(
            username=f"tenant_ga_{counter[0]}",
            email=f"tenant_ga_{counter[0]}@v.it",
            password="pwd",
        )
        return TenantProfile.objects.create(
            property=immobile,
            user=u,
            nominativo=nominativo,
            giorno_pagamento_affitto=1,
        )

    return _make


@pytest.fixture
def make_assignment(db, immobile, make_tenant):
    counter = [0]

    def _make(nominativo, valid_from, valid_to=None):
        counter[0] += 1
        room = Room.objects.create(
            property=immobile,
            nome=f"Camera GA {counter[0]}",
            ordinamento=counter[0],
        )
        tenant = make_tenant(nominativo)
        RoomAssignment.objects.create(
            room=room,
            tenant=tenant,
            valid_from=valid_from,
            valid_to=valid_to,
            canone_mensile=Decimal("400.00"),
        )
        return tenant

    return _make


class TestTenantsAttiviNelMese:
    def test_filtra_per_overlap_col_mese(self, make_tenant, make_assignment):
        attivo = make_assignment("Attivo", datetime.date(2026, 7, 23))
        futuro = make_assignment("Futuro", datetime.date(2026, 9, 1))
        uscito = make_assignment(
            "Uscito", datetime.date(2026, 1, 1), valid_to=datetime.date(2026, 6, 30)
        )
        orfano = make_tenant("Orfano")

        agosto = _tenants_attivi_nel_mese(2026, 8)
        assert attivo in agosto
        assert futuro not in agosto
        assert uscito not in agosto
        assert orfano not in agosto

        settembre = _tenants_attivi_nel_mese(2026, 9)
        assert futuro in settembre

    def test_ingresso_e_uscita_infra_mese_contano(self, make_assignment):
        parziale = make_assignment(
            "Parziale",
            datetime.date(2026, 8, 20),
            valid_to=datetime.date(2026, 8, 25),
        )
        assert parziale in _tenants_attivi_nel_mese(2026, 8)
        assert parziale not in _tenants_attivi_nel_mese(2026, 9)


class TestEndpointTenantsJson:
    url = reverse("admin:billing_receivable_genera_affitto_tenants")

    def test_ritorna_solo_tenant_attivi(self, admin_client, make_tenant, make_assignment):
        attivo = make_assignment("Attivo", datetime.date(2026, 7, 23))
        make_tenant("Orfano")

        resp = admin_client.get(self.url, {"anno": 2026, "mese": 8})
        assert resp.status_code == 200
        tenants = resp.json()["tenants"]
        assert tenants == [{"id": attivo.pk, "nominativo": "Attivo"}]

    def test_parametri_non_validi(self, admin_client):
        resp = admin_client.get(self.url, {"anno": "x", "mese": 8})
        assert resp.status_code == 400
        resp = admin_client.get(self.url, {"anno": 2026, "mese": 13})
        assert resp.status_code == 400

    def test_richiede_staff(self, client, db):
        resp = client.get(self.url, {"anno": 2026, "mese": 8})
        assert resp.status_code == 302


class TestFormValidazioneTenant:
    def _dati(self, tenant, anno=2026, mese=8):
        return {"anno": anno, "mese": mese, "tenant": tenant.pk}

    def test_rifiuta_tenant_senza_assignment_nel_mese(self, make_tenant):
        orfano = make_tenant("Orfano")
        form = GeneraReceivableAffittoForm(self._dati(orfano))
        assert not form.is_valid()
        assert "tenant" in form.errors

    def test_accetta_tenant_attivo_nel_mese(self, make_assignment):
        attivo = make_assignment("Attivo", datetime.date(2026, 7, 23))
        form = GeneraReceivableAffittoForm(self._dati(attivo))
        assert form.is_valid(), form.errors
