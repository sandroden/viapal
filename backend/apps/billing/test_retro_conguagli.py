"""
Test dell'attribuzione v3 day-based (docs/piano-utenze-configurabili.md §8):

- una bolletta a cavallo di due mesi non perde la coda se i periodi si
  emettono in ordine sparso (fix dell'esclusione binaria ``consumed_ids``);
- un conguaglio arrivato DOPO l'emissione dei mesi che copre si ribalta tutto
  sul periodo target (il primo dopo l'ultimo inviato) — caso Edison;
- le bollette storiche importate prima dei periodi non ribaltano nulla
  (guardia ``bill.created_at > periodo.created_at``).
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

    user = User.objects.create_user(username="propr_retro", password="x")
    grp, _ = Group.objects.get_or_create(name="proprietari")
    user.groups.add(grp)
    PropertyMembership.objects.create(
        property=immobile, user=user, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    return user


def _assignment_attivo(immobile):
    from properties.models import Room, RoomAssignment, TenantProfile

    room = Room.objects.create(property=immobile, nome="Camera Retro", ordinamento=40)
    tenant_user = User.objects.create_user(
        username="tenant_retro", password="x", email="retro@example.com"
    )
    tenant = TenantProfile.objects.create(
        property=immobile,
        user=tenant_user,
        nominativo="Rita Verdi",
        giorno_pagamento_affitto=1,
    )
    return RoomAssignment.objects.create(
        tenant=tenant,
        room=room,
        valid_from=datetime.date(2024, 1, 1),
        canone_mensile=Decimal("400.00"),
    )


def _bolletta(immobile, prodotto, importo, da, a, numero=None):
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
        numero_fattura=numero or f"{prodotto}-{da}",
        data_emissione=a,
        periodo_da=da,
        periodo_a=a,
        importo_totale=Decimal(importo),
    )


def _client(immobile):
    c = APIClient()
    c.force_authenticate(user=_proprietario(immobile))
    return c


def _pid(c, anno, mese):
    return c.get(
        "/api/v1/utility-periods/per-mese/", {"anno": anno, "mese": mese}
    ).json()["period"]["id"]


def _receivable(pid):
    from billing.models import Receivable

    return Receivable.objects.get(
        causale=Receivable.Causale.UTENZE, utility_period_id=pid
    )


class TestBimestraleOrdineSparso:
    def test_coda_non_persa_emettendo_prima_il_secondo_mese(self, immobile):
        """Bolletta 01/05–30/06 (61 gg): giugno emesso per primo prende 30/61,
        maggio calcolato dopo prende comunque i suoi 31/61. Somma = intero."""
        _assignment_attivo(immobile)
        _bolletta(
            immobile, "gas", "122.00",
            datetime.date(2025, 5, 1), datetime.date(2025, 6, 30),
        )
        c = _client(immobile)

        pid_giu = _pid(c, 2025, 6)
        resp = c.post(
            f"/api/v1/utility-periods/{pid_giu}/emetti/", {"forza": True}, format="json"
        )
        assert resp.status_code == 200, resp.content
        assert _receivable(pid_giu).importo_dovuto == Decimal("60.00")  # 122*30/61

        pid_mag = _pid(c, 2025, 5)
        ant = c.get(f"/api/v1/utility-periods/{pid_mag}/anteprima/").json()
        assert Decimal(str(ant["totali_per_voce"]["gas"])) == Decimal("62.00")
        # non è un retroattivo: sono i giorni PROPRI di maggio
        assert ant["arretrati"] == []

        resp = c.post(
            f"/api/v1/utility-periods/{pid_mag}/emetti/", {"forza": True}, format="json"
        )
        assert resp.status_code == 200, resp.content
        assert _receivable(pid_mag).importo_dovuto == Decimal("62.00")

        # Luglio (target dopo giugno): la bolletta è pinnata da maggio e
        # giugno, nessun ribaltamento doppio.
        pid_lug = _pid(c, 2025, 7)
        ant = c.get(f"/api/v1/utility-periods/{pid_lug}/anteprima/").json()
        assert ant.get("skipped") == "no_bollette_luce_gas"
        assert ant["arretrati"] == []


class TestConguaglioRetroattivo:
    def test_conguaglio_dopo_emissione_va_tutto_sul_target(self, immobile):
        """Caso Edison: aprile già emesso, il conguaglio che lo copre arriva
        dopo → tutto sul primo periodo dopo l'ultimo addebito (maggio)."""
        _assignment_attivo(immobile)
        _bolletta(
            immobile, "gas", "90.00",
            datetime.date(2025, 4, 1), datetime.date(2025, 4, 30),
        )
        c = _client(immobile)
        pid_apr = _pid(c, 2025, 4)
        resp = c.post(
            f"/api/v1/utility-periods/{pid_apr}/emetti/", {"forza": True}, format="json"
        )
        assert resp.status_code == 200, resp.content
        assert _receivable(pid_apr).importo_dovuto == Decimal("90.00")

        # Il conguaglio nasce DOPO l'emissione di aprile e ne copre i giorni.
        cong = _bolletta(
            immobile, "gas", "60.00",
            datetime.date(2025, 4, 1), datetime.date(2025, 4, 30),
            numero="EDISON-CONG",
        )

        pid_mag = _pid(c, 2025, 5)
        ant = c.get(f"/api/v1/utility-periods/{pid_mag}/anteprima/").json()
        assert Decimal(str(ant["totali_per_voce"]["gas"])) == Decimal("60.00")
        assert len(ant["arretrati"]) == 1
        arr = ant["arretrati"][0]
        assert arr["bill_id"] == cong.pk
        assert arr["giorni"] == 30
        assert Decimal(str(arr["importo"])) == Decimal("60.00")

        # Aprile resta congelato com'era.
        assert _receivable(pid_apr).importo_dovuto == Decimal("90.00")

        resp = c.post(
            f"/api/v1/utility-periods/{pid_mag}/emetti/", {"forza": True}, format="json"
        )
        assert resp.status_code == 200, resp.content
        assert _receivable(pid_mag).importo_dovuto == Decimal("60.00")

        # Giugno: il conguaglio è ormai pinnato da maggio, niente doppioni.
        pid_giu = _pid(c, 2025, 6)
        ant = c.get(f"/api/v1/utility-periods/{pid_giu}/anteprima/").json()
        assert ant.get("skipped") == "no_bollette_luce_gas"

    def test_conguaglio_a_cavallo_su_mese_aperto(self, immobile):
        """Conguaglio 01/04–31/05 arrivato dopo l'emissione di aprile: maggio
        (target e mese coperto) prende quota propria + retro = intero."""
        _assignment_attivo(immobile)
        _bolletta(
            immobile, "gas", "90.00",
            datetime.date(2025, 4, 1), datetime.date(2025, 4, 30),
        )
        c = _client(immobile)
        pid_apr = _pid(c, 2025, 4)
        c.post(
            f"/api/v1/utility-periods/{pid_apr}/emetti/", {"forza": True}, format="json"
        )

        _bolletta(
            immobile, "gas", "61.00",
            datetime.date(2025, 4, 1), datetime.date(2025, 5, 31),
            numero="EDISON-CONG-2",
        )  # 61 giorni: 30 retro (aprile) + 31 propri (maggio)

        pid_mag = _pid(c, 2025, 5)
        ant = c.get(f"/api/v1/utility-periods/{pid_mag}/anteprima/").json()
        assert Decimal(str(ant["totali_per_voce"]["gas"])) == Decimal("61.00")
        assert len(ant["arretrati"]) == 1
        assert ant["arretrati"][0]["giorni"] == 30
        assert Decimal(str(ant["arretrati"][0]["importo"])) == Decimal("30.00")


class TestGuardiaStorico:
    def test_bolletta_precedente_al_periodo_non_ribalta(self, immobile):
        """Bolletta nata PRIMA del periodo inviato (import storico): la sua
        quota non addebitata non si ribalta sul target."""
        from billing.models import UtilityChargePeriod

        _assignment_attivo(immobile)
        # Prima la bolletta...
        _bolletta(
            immobile, "gas", "80.00",
            datetime.date(2025, 4, 1), datetime.date(2025, 4, 30),
            numero="STORICO",
        )
        # ...poi il periodo, chiuso a mano senza pinnarla (com'era negli
        # import storici / nei periodi chiusi dall'admin).
        UtilityChargePeriod.objects.create(
            property=immobile,
            periodo_da=datetime.date(2025, 4, 1),
            periodo_a=datetime.date(2025, 4, 30),
            stato=UtilityChargePeriod.StatoPeriodo.INVIATO,
            data_invio=datetime.date(2025, 5, 1),
        )

        c = _client(immobile)
        pid_mag = _pid(c, 2025, 5)
        ant = c.get(f"/api/v1/utility-periods/{pid_mag}/anteprima/").json()
        assert ant.get("skipped") == "no_bollette_luce_gas"
        assert ant["arretrati"] == []
