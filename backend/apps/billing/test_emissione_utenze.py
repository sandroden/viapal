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


def _proprietario(immobile):
    from properties.models import PropertyMembership

    user = User.objects.create_user(username="propr_em", password="x")
    grp, _ = Group.objects.get_or_create(name="proprietari")
    user.groups.add(grp)
    PropertyMembership.objects.create(
        property=immobile, user=user, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    return user


def _assignment_attivo(immobile, email="mario@example.com"):
    """Inquilino con assegnazione stanza attiva da inizio 2024 (no scadenza).

    Allineato alle fixture del conftest: ``Room`` senza ``Building`` né
    ``Contract`` (il calcolo utenze usa solo l'overlap di RoomAssignment).
    """
    from properties.models import Room, RoomAssignment, TenantProfile

    room = Room.objects.create(property=immobile, nome="Camera Emissione", ordinamento=30)
    tenant_user = User.objects.create_user(
        username="tenant_em", password="x", email=email
    )
    tenant = TenantProfile.objects.create(
        property=immobile, user=tenant_user, nominativo="Mario Rossi", giorno_pagamento_affitto=1
    )
    assignment = RoomAssignment.objects.create(
        tenant=tenant,
        room=room,
        valid_from=datetime.date(2024, 1, 1),
        canone_mensile=Decimal("400.00"),
    )
    return tenant, assignment


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
        numero_fattura=f"{prodotto}-{da}",
        data_emissione=a,
        periodo_da=da,
        periodo_a=a,
        importo_totale=Decimal(importo),
    )


def _client(immobile):
    c = APIClient()
    c.force_authenticate(user=_proprietario(immobile))
    return c


class TestPerMese:
    def test_crea_periodo_se_assente(self, immobile):
        c = _client(immobile)
        resp = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6})
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["created"] is True
        assert body["period"]["periodo_da"] == "2025-06-01"
        assert body["period"]["periodo_a"] == "2025-06-30"
        assert body["completezza"]["completo"] is False  # nessuna bolletta

    def test_riusa_periodo_esistente(self, immobile):
        c = _client(immobile)
        first = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 7})
        second = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 7})
        assert second.json()["created"] is False
        assert first.json()["period"]["id"] == second.json()["period"]["id"]

    def test_parametri_mancanti(self, immobile):
        # 'mese' senza 'anno' è un input parziale invalido
        c = _client(immobile)
        resp = c.get("/api/v1/utility-periods/per-mese/", {"mese": 6})
        assert resp.status_code == 400

    def test_default_senza_parametri_mese_corrente_se_vuoto(self, immobile):
        # nessun addebito utenze esistente -> default = mese corrente
        c = _client(immobile)
        resp = c.get("/api/v1/utility-periods/per-mese/")
        assert resp.status_code == 200, resp.content
        oggi = datetime.date.today()
        assert resp.json()["anno"] == oggi.year
        assert resp.json()["mese"] == oggi.month

    def test_default_resta_sul_mese_con_avvisi_pendenti(self, immobile):
        # emette giugno 2025 ma NON invia gli avvisi -> il default resta giugno
        _assignment_attivo(immobile)
        _bolletta(immobile, "luce", "100.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        _bolletta(immobile, "gas", "60.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        c = _client(immobile)
        pid = c.get(
            "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6}
        ).json()["period"]["id"]
        c.post(f"/api/v1/utility-periods/{pid}/emetti/")

        resp = c.get("/api/v1/utility-periods/per-mese/")
        assert resp.json()["anno"] == 2025
        assert resp.json()["mese"] == 6

    def test_default_mese_successivo_dopo_invio_avvisi(self, immobile):
        # emessi gli addebiti e inviati gli avvisi -> il default propone luglio
        _assignment_attivo(immobile)
        _bolletta(immobile, "luce", "100.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        _bolletta(immobile, "gas", "60.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        c = _client(immobile)
        pid = c.get(
            "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6}
        ).json()["period"]["id"]
        c.post(f"/api/v1/utility-periods/{pid}/emetti/")
        c.post(
            f"/api/v1/utility-periods/{pid}/invia-avvisi/",
            {"dry_run": False},
            format="json",
        )

        resp = c.get("/api/v1/utility-periods/per-mese/")
        assert resp.json()["anno"] == 2025
        assert resp.json()["mese"] == 7

    def test_default_dicembre_passa_a_gennaio_dopo_invio(self, immobile):
        _assignment_attivo(immobile)
        _bolletta(immobile, "luce", "100.00", datetime.date(2025, 12, 1), datetime.date(2025, 12, 31))
        _bolletta(immobile, "gas", "60.00", datetime.date(2025, 12, 1), datetime.date(2025, 12, 31))
        c = _client(immobile)
        pid = c.get(
            "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 12}
        ).json()["period"]["id"]
        c.post(f"/api/v1/utility-periods/{pid}/emetti/")
        c.post(
            f"/api/v1/utility-periods/{pid}/invia-avvisi/",
            {"dry_run": False},
            format="json",
        )

        resp = c.get("/api/v1/utility-periods/per-mese/")
        assert resp.json()["anno"] == 2026
        assert resp.json()["mese"] == 1


class TestAnteprimaEmetti:
    def test_completezza_e_anteprima(self, immobile):
        _assignment_attivo(immobile)
        _bolletta(immobile, "luce", "100.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        _bolletta(immobile, "gas", "60.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        c = _client(immobile)

        per_mese = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6})
        body = per_mese.json()
        assert body["completezza"]["luce"] is True
        assert body["completezza"]["gas"] is True
        assert body["completezza"]["completo"] is True
        pid = body["period"]["id"]

        ant = c.get(f"/api/v1/utility-periods/{pid}/anteprima/")
        assert ant.status_code == 200, ant.content
        body_ant = ant.json()
        quote = body_ant["quote"]
        assert len(quote) == 1
        assert quote[0]["tenant_nominativo"] == "Mario Rossi"
        assert Decimal(str(quote[0]["quota"])) > 0

        # i totali per voce espongono luce + gas (le 3 righe del riepilogo)
        tpv = body_ant["totali_per_voce"]
        assert Decimal(str(tpv["luce"])) > 0
        assert Decimal(str(tpv["gas"])) > 0

    def test_emetti_crea_receivable_e_inviato(self, immobile):
        from billing.models import Receivable

        _assignment_attivo(immobile)
        _bolletta(immobile, "luce", "100.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        _bolletta(immobile, "gas", "60.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        c = _client(immobile)
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

    def test_emetti_blocca_periodo_incompleto(self, immobile):
        c = _client(immobile)
        pid = c.get(
            "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 9}
        ).json()["period"]["id"]
        resp = c.post(f"/api/v1/utility-periods/{pid}/emetti/")
        assert resp.status_code == 400
        assert resp.json()["completezza"]["completo"] is False


def _setup_emesso(c, immobile, email="mario@example.com", mese=6):
    """Crea inquilino+bollette, trova il periodo del mese e lo emette."""
    _assignment_attivo(immobile, email=email)
    _bolletta(immobile, "luce", "100.00", datetime.date(2025, mese, 1), datetime.date(2025, mese, 28))
    _bolletta(immobile, "gas", "60.00", datetime.date(2025, mese, 1), datetime.date(2025, mese, 28))
    pid = c.get(
        "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": mese}
    ).json()["period"]["id"]
    c.post(f"/api/v1/utility-periods/{pid}/emetti/")
    return pid


class TestInvioAvvisi:
    def test_dry_run_non_invia(self, mailoutbox, immobile):
        c = _client(immobile)
        pid = _setup_emesso(c, immobile)
        resp = c.post(
            f"/api/v1/utility-periods/{pid}/invia-avvisi/",
            {"dry_run": True},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["dry_run"] is True
        assert body["totale"] == 1
        assert body["inviati"] == 0
        avviso = body["avvisi"][0]
        assert avviso["esito"] == "anteprima"
        assert "conguaglio utenze" in avviso["oggetto"]
        assert "Mario Rossi" in avviso["corpo"]
        assert len(mailoutbox) == 0

    def test_invio_reale(self, mailoutbox, immobile):
        from notifications.models import Notification

        c = _client(immobile)
        pid = _setup_emesso(c, immobile)
        resp = c.post(
            f"/api/v1/utility-periods/{pid}/invia-avvisi/",
            {"dry_run": False},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["inviati"] == 1
        assert body["errori"] == 0
        assert body["avvisi_inviati_at"] is not None
        assert len(mailoutbox) == 1
        msg = mailoutbox[0]
        assert msg.to == ["mario@example.com"]
        # email multipart: deve avere l'alternativa HTML con link cliccabile
        html = next(
            (c for c, mime in (msg.alternatives or []) if mime == "text/html"), ""
        )
        assert html, "manca l'alternativa text/html"
        assert "<a href=" in html
        assert "/i/utenze/" in html
        # la scadenza NON è esplicitata nella mail
        assert "scadenza" not in msg.body.lower()
        assert "scadenza" not in html.lower()
        # il periodo ha registrato la data di invio degli avvisi
        from billing.models import Receivable, UtilityChargePeriod

        period = UtilityChargePeriod.objects.get(pk=pid)
        assert period.avvisi_inviati_at is not None
        # scadenza impostata a 2 settimane dall'avviso (oggi)
        rec = Receivable.objects.get(
            causale=Receivable.Causale.UTENZE, utility_period_id=pid
        )
        assert rec.scadenza == datetime.date.today() + datetime.timedelta(days=14)
        assert Notification.objects.filter(inviata_at__isnull=False).count() == 1

    def test_senza_email(self, mailoutbox, immobile):
        c = _client(immobile)
        pid = _setup_emesso(c, immobile, email="")
        resp = c.post(
            f"/api/v1/utility-periods/{pid}/invia-avvisi/",
            {"dry_run": False},
            format="json",
        )
        body = resp.json()
        assert body["inviati"] == 0
        assert body["senza_email"] == ["Mario Rossi"]
        assert len(mailoutbox) == 0

    def test_invio_reale_con_push(self, mailoutbox, settings, immobile):
        """Inquilino con device registrato: oltre all'email parte la push."""
        from unittest import mock

        from notifications.models import Notification, PushSubscription

        # Chiavi VAPID deterministiche: in CI pytest gira con ENV=production
        # (chiavi da env, vuote) e la push sarebbe disattivata.
        settings.VAPID_PRIVATE_KEY = "test-vapid-private"
        settings.VAPID_PUBLIC_KEY = "test-vapid-public"
        settings.VAPID_CLAIMS_SUB = "mailto:test@viapal.it"

        c = _client(immobile)
        pid = _setup_emesso(c, immobile)
        tenant_user = User.objects.get(username="tenant_em")
        PushSubscription.objects.create(
            user=tenant_user,
            endpoint="https://push.example.com/tenant-em",
            p256dh="p",
            auth="a",
        )
        with mock.patch("pywebpush.webpush") as wp:
            resp = c.post(
                f"/api/v1/utility-periods/{pid}/invia-avvisi/",
                {"dry_run": False},
                format="json",
            )
        body = resp.json()
        assert body["inviati"] == 1
        assert body["push_inviate"] == 1
        assert body["avvisi"][0]["push"]["inviate"] == 1
        assert wp.call_count == 1
        # il payload push punta al dettaglio del conguaglio
        assert "/i/utenze/" in wp.call_args.kwargs["data"]
        assert len(mailoutbox) == 1
        # due Notification: una email, una push
        assert Notification.objects.filter(inviata_at__isnull=False).count() == 2
        assert (
            Notification.objects.filter(
                canale=Notification.CanaleComunicazione.PUSH
            ).count()
            == 1
        )
