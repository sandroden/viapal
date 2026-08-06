"""
Test per la configurazione utenze per immobile (``PropertyUtilityService``):
CRUD via ``/api/v1/utenze-config/`` e la completezza dinamica di
``UtilityChargePeriodViewSet._completezza``.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()


def _membro(immobile, ruolo, username):
    from properties.models import PropertyMembership

    user = User.objects.create_user(username=username, password="x")
    grp, _ = Group.objects.get_or_create(name="proprietari")
    user.groups.add(grp)
    PropertyMembership.objects.create(property=immobile, user=user, ruolo=ruolo)
    return user


def _proprietario(immobile, username="propr_uc"):
    from properties.models import PropertyMembership

    return _membro(immobile, PropertyMembership.Ruolo.PROPRIETARIO, username)


def _gestore(immobile, username="gest_uc"):
    from properties.models import PropertyMembership

    return _membro(immobile, PropertyMembership.Ruolo.GESTORE, username)


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


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


class TestCrudUtenzeConfig:
    def test_proprietario_crea_legge_modifica_elimina(self, immobile):
        c = _client(_proprietario(immobile))

        resp = c.post(
            "/api/v1/utenze-config/",
            {"voce": "acqua", "gestione": "proprieta", "note": "contatore condominiale"},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        body = resp.json()
        assert body["voce"] == "acqua"
        assert body["voce_display"] == "Acqua"
        assert body["gestione"] == "proprieta"
        assert body["gestione_display"] == "Gestita dalla proprietà"
        pk = body["id"]

        lst = c.get("/api/v1/utenze-config/")
        assert lst.status_code == 200
        assert len(lst.json()) == 1

        upd = c.patch(
            f"/api/v1/utenze-config/{pk}/", {"gestione": "inquilino"}, format="json"
        )
        assert upd.status_code == 200, upd.content
        assert upd.json()["gestione"] == "inquilino"
        assert upd.json()["gestione_display"] == "A carico dell'inquilino"

        dele = c.delete(f"/api/v1/utenze-config/{pk}/")
        assert dele.status_code == 204
        assert c.get("/api/v1/utenze-config/").json() == []

    def test_gestore_puo_creare_e_modificare(self, immobile):
        c = _client(_gestore(immobile))

        resp = c.post(
            "/api/v1/utenze-config/", {"voce": "tari", "gestione": "inquilino"}, format="json"
        )
        assert resp.status_code == 201, resp.content
        pk = resp.json()["id"]

        upd = c.patch(
            f"/api/v1/utenze-config/{pk}/", {"gestione": "proprieta"}, format="json"
        )
        assert upd.status_code == 200, upd.content
        assert upd.json()["gestione"] == "proprieta"

    def test_non_membro_negato(self, immobile):
        estraneo = User.objects.create_user(username="estraneo_uc", password="x")
        c = _client(estraneo)
        resp = c.get("/api/v1/utenze-config/")
        assert resp.status_code in (403, 404)

    def test_doppione_voce_400(self, immobile):
        c = _client(_proprietario(immobile))
        primo = c.post(
            "/api/v1/utenze-config/", {"voce": "luce", "gestione": "proprieta"}, format="json"
        )
        assert primo.status_code == 201, primo.content

        resp = c.post(
            "/api/v1/utenze-config/", {"voce": "luce", "gestione": "inquilino"}, format="json"
        )
        assert resp.status_code == 400
        assert "voce" in resp.json()

    def test_isolamento_per_property(self, immobile, immobile2):
        c1 = _client(_proprietario(immobile, username="propr_uc1"))
        r1 = c1.post(
            "/api/v1/utenze-config/", {"voce": "gas", "gestione": "proprieta"}, format="json"
        )
        assert r1.status_code == 201, r1.content

        c2 = _client(_proprietario(immobile2, username="propr_uc2"))
        lst2 = c2.get("/api/v1/utenze-config/")
        assert lst2.status_code == 200
        assert lst2.json() == []


class TestCompletezzaDinamica:
    def test_senza_config_fallback_storico(self, immobile):
        """Property senza nessuna riga di configurazione: comportamento
        precedente (attese luce+gas+tari, completo solo con luce+gas)."""
        c = _client(_proprietario(immobile))

        resp = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6})
        comp = resp.json()["completezza"]
        assert comp["attese"] == ["luce", "gas", "tari"]
        assert comp["completo"] is False
        assert "acqua" not in comp

        _bolletta(immobile, "luce", "100.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        _bolletta(immobile, "gas", "60.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))

        resp2 = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6})
        comp2 = resp2.json()["completezza"]
        assert comp2["luce"] is True
        assert comp2["gas"] is True
        assert comp2["completo"] is True

    def test_config_tari_inquilino_esclusa_da_attese(self, immobile):
        from billing.models import PropertyUtilityService

        PropertyUtilityService.objects.create(
            property=immobile, voce="luce", gestione="proprieta"
        )
        PropertyUtilityService.objects.create(
            property=immobile, voce="gas", gestione="proprieta"
        )
        PropertyUtilityService.objects.create(
            property=immobile, voce="tari", gestione="inquilino"
        )
        c = _client(_proprietario(immobile))

        resp = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6})
        comp = resp.json()["completezza"]
        assert comp["attese"] == ["luce", "gas"]
        assert "acqua" not in comp
        assert comp["completo"] is False  # nessuna bolletta ancora

    def test_config_solo_luce_completo_con_sola_bolletta_luce(self, immobile):
        from billing.models import PropertyUtilityService

        PropertyUtilityService.objects.create(
            property=immobile, voce="luce", gestione="proprieta"
        )
        _bolletta(immobile, "luce", "100.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        c = _client(_proprietario(immobile))

        resp = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6})
        comp = resp.json()["completezza"]
        assert comp["attese"] == ["luce"]
        assert comp["completo"] is True

    def test_config_acqua_entra_tra_le_attese(self, immobile):
        from billing.models import PropertyUtilityService

        PropertyUtilityService.objects.create(
            property=immobile, voce="luce", gestione="proprieta"
        )
        PropertyUtilityService.objects.create(
            property=immobile, voce="gas", gestione="proprieta"
        )
        PropertyUtilityService.objects.create(
            property=immobile, voce="acqua", gestione="proprieta"
        )
        _bolletta(immobile, "luce", "100.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        _bolletta(immobile, "gas", "60.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        c = _client(_proprietario(immobile))

        resp = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6})
        comp = resp.json()["completezza"]
        assert comp["attese"] == ["luce", "gas", "acqua"]
        assert comp["acqua"] is False
        assert comp["completo"] is False  # manca la bolletta acqua

        _bolletta(immobile, "acqua", "20.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))

        resp2 = c.get("/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6})
        comp2 = resp2.json()["completezza"]
        assert comp2["acqua"] is True
        assert comp2["completo"] is True

def _assignment_attivo(immobile):
    from properties.models import Room, RoomAssignment, TenantProfile

    room = Room.objects.create(property=immobile, nome="Camera Cfg", ordinamento=50)
    tenant_user = User.objects.create_user(
        username="tenant_cfg", password="x", email="cfg@example.com"
    )
    tenant = TenantProfile.objects.create(
        property=immobile,
        user=tenant_user,
        nominativo="Carla Blu",
        giorno_pagamento_affitto=1,
    )
    return RoomAssignment.objects.create(
        tenant=tenant,
        room=room,
        valid_from=datetime.date(2024, 1, 1),
        canone_mensile=Decimal("400.00"),
    )


class TestCalcoloConfigDriven:
    """Fase 2: le voci fatturabili si leggono dalla config per immobile."""

    def _config(self, immobile, **voci):
        from billing.models import PropertyUtilityService

        for voce, gestione in voci.items():
            PropertyUtilityService.objects.create(
                property=immobile, voce=voce, gestione=gestione
            )

    def test_acqua_gestita_entra_nella_ripartizione(self, immobile):
        self._config(immobile, luce="proprieta", gas="proprieta", acqua="proprieta")
        _assignment_attivo(immobile)
        _bolletta(immobile, "luce", "100.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        _bolletta(immobile, "gas", "60.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        _bolletta(immobile, "acqua", "30.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        c = _client(_proprietario(immobile))
        pid = c.get(
            "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6}
        ).json()["period"]["id"]

        ant = c.get(f"/api/v1/utility-periods/{pid}/anteprima/").json()
        assert Decimal(str(ant["totali_per_voce"]["acqua"])) == Decimal("30.00")
        assert Decimal(str(ant["totale_periodo"])) == Decimal("190.00")
        assert Decimal(str(ant["quote"][0]["dettaglio"]["acqua"])) == Decimal("30.00")

    def test_acqua_ignorata_senza_config(self, immobile):
        """Fallback storico: senza config la bolletta acqua non entra."""
        _assignment_attivo(immobile)
        _bolletta(immobile, "luce", "100.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        _bolletta(immobile, "gas", "60.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        _bolletta(immobile, "acqua", "30.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        c = _client(_proprietario(immobile))
        pid = c.get(
            "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6}
        ).json()["period"]["id"]

        ant = c.get(f"/api/v1/utility-periods/{pid}/anteprima/").json()
        assert "acqua" not in ant["totali_per_voce"]
        assert Decimal(str(ant["totale_periodo"])) == Decimal("160.00")

    def test_solo_tari_gestita_niente_forzatura(self, immobile):
        """Config esplicita senza voci a bolletta: la sola TARI si ripartisce
        senza bisogno di 'procedi comunque'."""
        from billing.models import AnnualUtilityCost

        self._config(immobile, luce="inquilino", gas="inquilino", tari="proprieta")
        AnnualUtilityCost.objects.create(
            property=immobile,
            voce=AnnualUtilityCost.VoceAnnuale.TARI,
            anno=2025,
            importo_annuale=Decimal("120.00"),
            valid_from=datetime.date(2025, 1, 1),
        )
        _assignment_attivo(immobile)
        c = _client(_proprietario(immobile))
        per_mese = c.get(
            "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6}
        ).json()
        assert per_mese["completezza"]["completo"] is True
        assert per_mese["completezza"]["attese"] == ["tari"]
        pid = per_mese["period"]["id"]

        ant = c.get(f"/api/v1/utility-periods/{pid}/anteprima/").json()
        assert "skipped" not in ant
        assert Decimal(str(ant["totali_per_voce"]["tari"])) == Decimal("10.00")

        # e l'emissione passa senza forza (completo=True)
        resp = c.post(f"/api/v1/utility-periods/{pid}/emetti/")
        assert resp.status_code == 200, resp.content

    def test_tari_inquilino_non_ripartita(self, immobile):
        """TARI configurata a carico inquilino: fuori dal conteggio anche se
        il costo annuale esiste a sistema."""
        from billing.models import AnnualUtilityCost

        self._config(immobile, luce="proprieta", gas="proprieta", tari="inquilino")
        AnnualUtilityCost.objects.create(
            property=immobile,
            voce=AnnualUtilityCost.VoceAnnuale.TARI,
            anno=2025,
            importo_annuale=Decimal("120.00"),
            valid_from=datetime.date(2025, 1, 1),
        )
        _assignment_attivo(immobile)
        _bolletta(immobile, "luce", "100.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        _bolletta(immobile, "gas", "60.00", datetime.date(2025, 6, 1), datetime.date(2025, 6, 30))
        c = _client(_proprietario(immobile))
        pid = c.get(
            "/api/v1/utility-periods/per-mese/", {"anno": 2025, "mese": 6}
        ).json()["period"]["id"]

        ant = c.get(f"/api/v1/utility-periods/{pid}/anteprima/").json()
        assert "tari" not in ant["totali_per_voce"]
        assert Decimal(str(ant["totale_periodo"])) == Decimal("160.00")
