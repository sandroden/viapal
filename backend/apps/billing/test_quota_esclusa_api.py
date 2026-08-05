"""
Test API per la quota esclusa dalla ripartizione utenze (voci a carico
proprietà: canone RAI, aumento potenza, allacci).

Coprono: PATCH bolletta (validazione), anteprima con totale_escluso, nota
esclusioni negli avvisi (dry-run), vista inquilino (lordo + netto) e
statistiche al netto.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()


def _proprietario(immobile):
    from properties.models import PropertyMembership

    user = User.objects.create_user(username="propr_qe", password="x")
    grp, _ = Group.objects.get_or_create(name="proprietari")
    user.groups.add(grp)
    PropertyMembership.objects.create(
        property=immobile, user=user, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    return user


def _assignment_attivo(immobile, email="mario@example.com"):
    from properties.models import Room, RoomAssignment, TenantProfile

    room = Room.objects.create(property=immobile, nome="Camera QE", ordinamento=40)
    tenant_user = User.objects.create_user(
        username="tenant_qe", password="x", email=email
    )
    grp, _ = Group.objects.get_or_create(name="inquilini")
    tenant_user.groups.add(grp)
    tenant = TenantProfile.objects.create(
        property=immobile,
        user=tenant_user,
        nominativo="Mario Rossi",
        giorno_pagamento_affitto=1,
    )
    assignment = RoomAssignment.objects.create(
        tenant=tenant,
        room=room,
        valid_from=datetime.date(2024, 1, 1),
        canone_mensile=Decimal("400.00"),
    )
    return tenant, assignment


def _bolletta(immobile, prodotto, importo, da, a, quota_esclusa="0", motivo=""):
    from billing.models import Supplier, UtilityBill

    supplier, _ = Supplier.objects.get_or_create(
        property=immobile,
        nome=f"Forn-{prodotto}",
        defaults={"tipo": Supplier.TipoFornitore.ALTRO},
    )
    return UtilityBill.objects.create(
        immobile=immobile,
        supplier=supplier,
        prodotto=prodotto,
        numero_fattura=f"{prodotto}-{da}-qe",
        data_emissione=a,
        periodo_da=da,
        periodo_a=a,
        importo_totale=Decimal(importo),
        quota_esclusa=Decimal(quota_esclusa),
        motivo_esclusione=motivo,
    )


def _client(immobile):
    c = APIClient()
    c.force_authenticate(user=_proprietario(immobile))
    return c


class TestPatchQuotaEsclusa:
    def test_patch_valido(self, immobile):
        c = _client(immobile)
        bill = _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
        )
        resp = c.patch(
            f"/api/v1/utility-bills/{bill.id}/",
            {"quota_esclusa": "12.50", "motivo_esclusione": "Canone RAI"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        bill.refresh_from_db()
        assert bill.quota_esclusa == Decimal("12.50")
        assert bill.motivo_esclusione == "Canone RAI"

    def test_patch_quota_superiore_importo(self, immobile):
        c = _client(immobile)
        bill = _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
        )
        resp = c.patch(
            f"/api/v1/utility-bills/{bill.id}/",
            {"quota_esclusa": "150.00"},
            format="json",
        )
        assert resp.status_code == 400
        assert "quota_esclusa" in resp.json()

    def test_patch_quota_negativa(self, immobile):
        c = _client(immobile)
        bill = _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
        )
        resp = c.patch(
            f"/api/v1/utility-bills/{bill.id}/",
            {"quota_esclusa": "-5.00"},
            format="json",
        )
        assert resp.status_code == 400

    def test_patch_importo_sotto_quota_esistente(self, immobile):
        """Abbassare l'importo sotto la quota già salvata deve fallire."""
        c = _client(immobile)
        bill = _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
            quota_esclusa="40.00", motivo="Allaccio",
        )
        resp = c.patch(
            f"/api/v1/utility-bills/{bill.id}/",
            {"importo_totale": "30.00"},
            format="json",
        )
        assert resp.status_code == 400


class TestAnteprimaConEsclusioni:
    def test_anteprima_espone_totale_escluso(self, immobile):
        _assignment_attivo(immobile)
        _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
            quota_esclusa="30.00", motivo="Canone RAI",
        )
        _bolletta(
            immobile, "gas", "60.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
        )
        c = _client(immobile)
        pid = c.get(
            "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6}
        ).json()["period"]["id"]

        ant = c.get(f"/api/v1/utility-periods/{pid}/anteprima/").json()
        assert Decimal(str(ant["totale_escluso"])) == Decimal("30.00")
        assert ant["esclusioni"][0]["motivo"] == "Canone RAI"
        # Totali netti: luce 70 + gas 60
        assert Decimal(str(ant["totali_per_voce"]["luce"])) == Decimal("70.00")
        assert Decimal(str(ant["totale_periodo"])) == Decimal("130.00")


class TestAvvisiConEsclusioni:
    def _emetti(self, c, immobile, quota_esclusa="0", motivo=""):
        _assignment_attivo(immobile)
        _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 28),
            quota_esclusa=quota_esclusa, motivo=motivo,
        )
        _bolletta(
            immobile, "gas", "60.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 28),
        )
        pid = c.get(
            "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6}
        ).json()["period"]["id"]
        c.post(f"/api/v1/utility-periods/{pid}/emetti/")
        return pid

    def test_corpo_con_nota_esclusioni(self, immobile):
        c = _client(immobile)
        pid = self._emetti(c, immobile, quota_esclusa="12.50", motivo="Canone RAI")
        resp = c.post(
            f"/api/v1/utility-periods/{pid}/invia-avvisi/",
            {"dry_run": True},
            format="json",
        )
        avviso = resp.json()["avvisi"][0]
        assert "esclusi 12,50 € a carico della proprietà" in avviso["corpo"]
        assert "Canone RAI" in avviso["corpo"]
        assert "a carico della proprietà" in avviso["corpo_html"]

    def test_corpo_senza_nota_se_niente_esclusioni(self, immobile):
        c = _client(immobile)
        pid = self._emetti(c, immobile)
        resp = c.post(
            f"/api/v1/utility-periods/{pid}/invia-avvisi/",
            {"dry_run": True},
            format="json",
        )
        avviso = resp.json()["avvisi"][0]
        assert "a carico della proprietà" not in avviso["corpo"]
        assert "a carico della proprietà" not in avviso["corpo_html"]


class TestVistaInquilino:
    def test_dettaglio_espone_lordo_ed_escluso(self, immobile):
        tenant, _ = _assignment_attivo(immobile)
        _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
            quota_esclusa="30.00", motivo="Canone RAI",
        )
        _bolletta(
            immobile, "gas", "60.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
        )
        c = _client(immobile)
        pid = c.get(
            "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6}
        ).json()["period"]["id"]
        c.post(f"/api/v1/utility-periods/{pid}/emetti/")

        ci = APIClient()
        ci.force_authenticate(user=tenant.user)
        resp = ci.get(f"/api/v1/utenze-inquilino/{pid}/")
        assert resp.status_code == 200, resp.content
        body = resp.json()

        luce = next(b for b in body["bollette"] if b["prodotto"] == "luce")
        assert Decimal(str(luce["importo_totale"])) == Decimal("100.00")
        assert Decimal(str(luce["quota_esclusa"])) == Decimal("30.00")
        assert Decimal(str(luce["importo_ripartibile"])) == Decimal("70.00")
        assert luce["motivo_esclusione"] == "Canone RAI"

        assert Decimal(str(body["totale_periodo"])) == Decimal("130.00")
        assert Decimal(str(body["totale_escluso"])) == Decimal("30.00")


class TestStatisticheNetto:
    def test_prezzo_unitario_al_netto(self, immobile):
        from billing.models import UtilityBill

        bill = _bolletta(
            immobile, "luce", "110.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
            quota_esclusa="10.00", motivo="Canone RAI",
        )
        UtilityBill.objects.filter(pk=bill.pk).update(consumo=Decimal("100"))
        c = _client(immobile)
        resp = c.get("/api/v1/utility-bills/statistiche/")
        assert resp.status_code == 200, resp.content
        row = resp.json()[0]
        # (110 - 10) / 100 = 1.0, non 1.1
        assert row["luce_importo"] == 100.0
        assert row["luce_prezzo_unitario"] == 1.0
