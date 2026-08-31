"""
Test per la quota di TARI a carico della proprietà (``UtilityChargePeriod``).

Il caso reale: un posto resta sfitto e la sua fetta di TARI non va scaricata
sugli inquilini presenti. È l'analogo della ``quota_esclusa`` delle bollette,
ma mensile — lo sfitto cambia di mese in mese — quindi vive sul periodo.

Coprono: endpoint di salvataggio (validazioni, gate sul periodo emesso),
effetto sul calcolo (TARI netta, quote, totale_escluso) e vista inquilino.
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

    user = User.objects.create_user(username="propr_tari", password="x")
    grp, _ = Group.objects.get_or_create(name="proprietari")
    user.groups.add(grp)
    PropertyMembership.objects.create(
        property=immobile, user=user, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    return user


def _client(immobile):
    c = APIClient()
    c.force_authenticate(user=_proprietario(immobile))
    return c


def _assignment(immobile, suffisso, nominativo):
    from properties.models import Room, RoomAssignment, TenantProfile

    room = Room.objects.create(
        property=immobile, nome=f"Camera {suffisso}", ordinamento=50
    )
    user = User.objects.create_user(
        username=f"tenant_tari_{suffisso}",
        password="x",
        email=f"{suffisso}@example.com",
    )
    grp, _ = Group.objects.get_or_create(name="inquilini")
    user.groups.add(grp)
    tenant = TenantProfile.objects.create(
        property=immobile,
        user=user,
        nominativo=nominativo,
        giorno_pagamento_affitto=1,
    )
    assignment = RoomAssignment.objects.create(
        tenant=tenant,
        room=room,
        valid_from=datetime.date(2024, 1, 1),
        canone_mensile=Decimal("400.00"),
    )
    return tenant, assignment


def _tari(immobile, importo_annuale="600.00", anno=2025):
    from billing.models import AnnualUtilityCost

    return AnnualUtilityCost.objects.create(
        property=immobile,
        voce=AnnualUtilityCost.VoceAnnuale.TARI,
        anno=anno,
        importo_annuale=Decimal(importo_annuale),
        valid_from=datetime.date(anno, 1, 1),
        valid_to=datetime.date(anno, 12, 31),
    )


def _bolletta(immobile, prodotto, importo, da, a):
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
        numero_fattura=f"{prodotto}-{da}-tari",
        data_emissione=a,
        periodo_da=da,
        periodo_a=a,
        importo_totale=Decimal(importo),
    )


def _periodo(c, anno=2025, mese=6):
    return c.get(
        "/api/v1/utility-periods/per-mese/", {"anno": anno, "mese": mese}
    ).json()["period"]["id"]


class TestEndpointEsclusioneTari:
    def test_salva_quota_e_motivo(self, immobile):
        from billing.models import UtilityChargePeriod

        _tari(immobile)  # 600/anno → 50 €/mese
        c = _client(immobile)
        pid = _periodo(c)

        resp = c.post(
            f"/api/v1/utility-periods/{pid}/esclusione-tari/",
            {"quota_esclusa": "10.00", "motivo": "Stanza singola sfitta"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        assert Decimal(str(resp.json()["tari_lorda"])) == Decimal("50.00")

        period = UtilityChargePeriod.objects.get(pk=pid)
        assert period.quota_esclusa_tari == Decimal("10.00")
        assert period.motivo_esclusione_tari == "Stanza singola sfitta"

    def test_quota_azzerata_cancella_il_motivo(self, immobile):
        from billing.models import UtilityChargePeriod

        _tari(immobile)
        c = _client(immobile)
        pid = _periodo(c)
        c.post(
            f"/api/v1/utility-periods/{pid}/esclusione-tari/",
            {"quota_esclusa": "10.00", "motivo": "Stanza sfitta"},
            format="json",
        )
        resp = c.post(
            f"/api/v1/utility-periods/{pid}/esclusione-tari/",
            {"quota_esclusa": "0"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        period = UtilityChargePeriod.objects.get(pk=pid)
        assert period.quota_esclusa_tari == Decimal("0")
        assert period.motivo_esclusione_tari == ""

    def test_quota_oltre_la_tari_del_mese(self, immobile):
        _tari(immobile)  # 50 €/mese
        c = _client(immobile)
        pid = _periodo(c)
        resp = c.post(
            f"/api/v1/utility-periods/{pid}/esclusione-tari/",
            {"quota_esclusa": "60.00"},
            format="json",
        )
        assert resp.status_code == 400
        assert "quota_esclusa" in resp.json()

    def test_quota_negativa(self, immobile):
        _tari(immobile)
        c = _client(immobile)
        pid = _periodo(c)
        resp = c.post(
            f"/api/v1/utility-periods/{pid}/esclusione-tari/",
            {"quota_esclusa": "-1.00"},
            format="json",
        )
        assert resp.status_code == 400

    def test_valore_non_numerico(self, immobile):
        _tari(immobile)
        c = _client(immobile)
        pid = _periodo(c)
        resp = c.post(
            f"/api/v1/utility-periods/{pid}/esclusione-tari/",
            {"quota_esclusa": "dodici"},
            format="json",
        )
        assert resp.status_code == 400

    def test_periodo_gia_emesso_si_modifica_ma_non_tocca_gli_addebiti(self, immobile):
        """Come per le bollette: la modifica è ammessa anche dopo l'emissione,
        ma i Receivable già creati restano quelli finché non si rigenera."""
        from billing.models import Receivable

        _assignment(immobile, "a", "Anna Bianchi")
        _tari(immobile)
        _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
        )
        c = _client(immobile)
        pid = _periodo(c)
        assert c.post(
            f"/api/v1/utility-periods/{pid}/emetti/", {"forza": True}, format="json"
        ).status_code == 200
        importi_pre = sorted(
            Receivable.objects.filter(utility_period_id=pid).values_list(
                "importo_dovuto", flat=True
            )
        )

        resp = c.post(
            f"/api/v1/utility-periods/{pid}/esclusione-tari/",
            {"quota_esclusa": "10.00", "motivo": "Stanza sfitta"},
            format="json",
        )
        assert resp.status_code == 200, resp.content

        importi_post = sorted(
            Receivable.objects.filter(utility_period_id=pid).values_list(
                "importo_dovuto", flat=True
            )
        )
        assert importi_post == importi_pre

        # L'anteprima invece riflette subito la nuova esclusione.
        ant = c.get(f"/api/v1/utility-periods/{pid}/anteprima/").json()
        assert Decimal(str(ant["totale_escluso"])) == Decimal("10.00")


class TestCalcoloConEsclusioneTari:
    def test_tari_netta_e_quote_ridotte(self, immobile):
        """600/anno = 50 €/mese; con 10 € esclusi restano 40 € da dividere."""
        _assignment(immobile, "a", "Anna Bianchi")
        _assignment(immobile, "b", "Bruno Verdi")
        _tari(immobile)
        _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
        )
        c = _client(immobile)
        pid = _periodo(c)
        c.post(
            f"/api/v1/utility-periods/{pid}/esclusione-tari/",
            {"quota_esclusa": "10.00", "motivo": "Stanza sfitta"},
            format="json",
        )

        ant = c.get(f"/api/v1/utility-periods/{pid}/anteprima/").json()
        assert Decimal(str(ant["totali_per_voce"]["tari"])) == Decimal("40.00")
        assert Decimal(str(ant["totale_periodo"])) == Decimal("140.00")
        assert Decimal(str(ant["totale_escluso"])) == Decimal("10.00")

        escl = [e for e in ant["esclusioni"] if e["prodotto"] == "tari"]
        assert len(escl) == 1
        assert escl[0]["bill_id"] is None
        assert escl[0]["motivo"] == "Stanza sfitta"
        assert Decimal(str(escl[0]["quota_esclusa"])) == Decimal("10.00")

        # Due inquilini presenti tutto il mese: 20 € di TARI a testa (non 25).
        for q in ant["quote"]:
            assert Decimal(str(q["dettaglio"]["tari"])) == Decimal("20.00")

    def test_esclusione_totale_toglie_la_voce(self, immobile):
        """TARI interamente a carico proprietà: la voce sparisce dal conguaglio."""
        _assignment(immobile, "a", "Anna Bianchi")
        _tari(immobile)
        _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
        )
        c = _client(immobile)
        pid = _periodo(c)
        c.post(
            f"/api/v1/utility-periods/{pid}/esclusione-tari/",
            {"quota_esclusa": "50.00", "motivo": "Casa vuota"},
            format="json",
        )
        ant = c.get(f"/api/v1/utility-periods/{pid}/anteprima/").json()
        assert "tari" not in ant["totali_per_voce"]
        assert Decimal(str(ant["totale_periodo"])) == Decimal("100.00")
        assert Decimal(str(ant["totale_escluso"])) == Decimal("50.00")

    def test_solo_tari_tutta_esclusa_non_emette_nulla(self, immobile):
        """Niente bollette e TARI azzerata dall'esclusione: niente da ripartire.

        Deve restare uno ``skipped``, non un addebito da 0 €.
        """
        _assignment(immobile, "a", "Anna Bianchi")
        _tari(immobile)
        c = _client(immobile)
        pid = _periodo(c)
        c.post(
            f"/api/v1/utility-periods/{pid}/esclusione-tari/",
            {"quota_esclusa": "50.00", "motivo": "Casa vuota"},
            format="json",
        )
        ant = c.get(
            f"/api/v1/utility-periods/{pid}/anteprima/", {"forza": 1}
        ).json()
        assert ant["skipped"] == "nessun_importo"
        assert ant["quote"] == []

        resp = c.post(
            f"/api/v1/utility-periods/{pid}/emetti/", {"forza": True}, format="json"
        )
        assert resp.status_code == 400

    def test_periodo_bimestrale_tari_su_due_mesi(self, immobile):
        """La quota esclusa è del periodo, non del mese: su un bimestre vale una volta."""
        from billing.models import UtilityChargePeriod

        _assignment(immobile, "a", "Anna Bianchi")
        _tari(immobile)  # 100 € su due mesi
        period = UtilityChargePeriod.objects.create(
            property=immobile,
            periodo_da=datetime.date(2025, 6, 1),
            periodo_a=datetime.date(2025, 7, 31),
            quota_esclusa_tari=Decimal("25.00"),
            motivo_esclusione_tari="Una stanza sfitta",
        )
        c = _client(immobile)
        ant = c.get(
            f"/api/v1/utility-periods/{period.id}/anteprima/", {"forza": 1}
        ).json()
        assert Decimal(str(ant["totali_per_voce"]["tari"])) == Decimal("75.00")
        assert Decimal(str(ant["totale_escluso"])) == Decimal("25.00")


class TestVistaInquilinoTari:
    def test_inquilino_vede_la_quota_esclusa(self, immobile):
        tenant, _ = _assignment(immobile, "a", "Anna Bianchi")
        _tari(immobile)
        _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
        )
        c = _client(immobile)
        pid = _periodo(c)
        c.post(
            f"/api/v1/utility-periods/{pid}/esclusione-tari/",
            {"quota_esclusa": "10.00", "motivo": "Stanza sfitta"},
            format="json",
        )
        c.post(f"/api/v1/utility-periods/{pid}/emetti/", {"forza": True}, format="json")

        ci = APIClient()
        ci.force_authenticate(user=tenant.user)
        body = ci.get(f"/api/v1/utenze-inquilino/{pid}/").json()
        assert Decimal(str(body["totale_escluso"])) == Decimal("10.00")
        escl = [e for e in body["esclusioni"] if e["prodotto"] == "tari"]
        assert escl and escl[0]["motivo"] == "Stanza sfitta"
        assert Decimal(str(body["totali_per_voce"]["tari"])) == Decimal("40.00")

    def test_avviso_email_cita_l_esclusione(self, immobile):
        _assignment(immobile, "a", "Anna Bianchi")
        _tari(immobile)
        _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 6, 1), datetime.date(2025, 6, 30),
        )
        c = _client(immobile)
        pid = _periodo(c)
        c.post(
            f"/api/v1/utility-periods/{pid}/esclusione-tari/",
            {"quota_esclusa": "10.00", "motivo": "Stanza sfitta"},
            format="json",
        )
        c.post(f"/api/v1/utility-periods/{pid}/emetti/", {"forza": True}, format="json")
        resp = c.post(
            f"/api/v1/utility-periods/{pid}/invia-avvisi/",
            {"dry_run": True},
            format="json",
        )
        avviso = resp.json()["avvisi"][0]
        assert "esclusi 10,00 € a carico della proprietà" in avviso["corpo"]
        assert "Stanza sfitta" in avviso["corpo"]
