"""
Contratto sull'assegnazione (``RoomAssignment.contract``).

Il campo dice sotto quale contratto sta un'occupazione. È facoltativo: senza,
l'inquilino non vede le carte di nessun contratto (vedi i documenti immobile).
Qui si fissa il comportamento che non si legge dal modello: la proposta
automatica alla prima assegnazione, il "nessun contratto" esplicito che va
rispettato, l'eredità nel subentro e l'isolamento cross-property.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from properties.models import (
    Contract,
    PropertyMembership,
    Room,
    RoomAssignment,
    TenantProfile,
)

pytestmark = pytest.mark.django_db

PRIMA = "/api/v1/room-assignments/prima-assegnazione/"


def _client(user, immobile):
    c = APIClient(enforce_csrf_checks=False)
    c.force_login(user)
    c.defaults["HTTP_X_PROPERTY_ID"] = str(immobile.pk)
    return c


@pytest.fixture
def scena(immobile):
    """Immobile con una stanza, un inquilino e due contratti: uno chiuso nel
    2024, uno in vigore dal 2025."""
    stanza = Room.objects.create(property=immobile, nome="Camera 1")
    tenant = TenantProfile.objects.create(
        user=User.objects.create_user(username="inq-contract"),
        nominativo="Rossi Mario",
        property=immobile,
        giorno_pagamento_affitto=5,
    )
    vecchio = Contract.objects.create(
        property=immobile,
        nome="Collettivo 2024",
        data_stipula=datetime.date(2024, 1, 1),
        data_decorrenza=datetime.date(2024, 1, 1),
        termine=datetime.date(2024, 12, 31),
        durata_anni=4,
    )
    attuale = Contract.objects.create(
        property=immobile,
        nome="Collettivo 2025",
        data_stipula=datetime.date(2025, 2, 15),
        data_decorrenza=datetime.date(2025, 2, 15),
        durata_anni=4,
    )
    proprietario = User.objects.create_user(username="prop-contract")
    PropertyMembership.objects.create(
        property=immobile, user=proprietario, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    return {
        "immobile": immobile,
        "stanza": stanza,
        "tenant": tenant,
        "vecchio": vecchio,
        "attuale": attuale,
        "client": _client(proprietario, immobile),
    }


class TestPrimaAssegnazione:
    def _payload(self, scena, **extra):
        return {
            "tenant": scena["tenant"].id,
            "room": scena["stanza"].id,
            "valid_from": "2026-03-01",
            "canone_mensile": "450.00",
            "ciclo_fatturazione": "solare",
            **extra,
        }

    def test_senza_contratto_propone_quello_in_vigore(self, scena):
        resp = scena["client"].post(PRIMA, self._payload(scena), format="json")
        assert resp.status_code == 201, resp.content
        assegnazione = RoomAssignment.objects.get(tenant=scena["tenant"])
        assert assegnazione.contract_id == scena["attuale"].pk

    def test_contratto_null_esplicito_resta_senza(self, scena):
        """Chi svuota il campo sta dicendo "non deve vedere quelle carte":
        la proposta automatica non deve scavalcarlo."""
        resp = scena["client"].post(
            PRIMA, self._payload(scena, contract=None), format="json"
        )
        assert resp.status_code == 201, resp.content
        assert RoomAssignment.objects.get(tenant=scena["tenant"]).contract_id is None

    def test_contratto_indicato_vince_sulla_proposta(self, scena):
        resp = scena["client"].post(
            PRIMA, self._payload(scena, contract=scena["vecchio"].id), format="json"
        )
        assert resp.status_code == 201, resp.content
        assegnazione = RoomAssignment.objects.get(tenant=scena["tenant"])
        assert assegnazione.contract_id == scena["vecchio"].pk

    def test_contratto_di_un_altro_immobile_400(self, scena, immobile2):
        estraneo = Contract.objects.create(
            property=immobile2,
            data_stipula=datetime.date(2025, 1, 1),
            data_decorrenza=datetime.date(2025, 1, 1),
            durata_anni=4,
        )
        resp = scena["client"].post(
            PRIMA, self._payload(scena, contract=estraneo.id), format="json"
        )
        assert resp.status_code == 400, resp.content
        assert "contract" in resp.json()


class TestModificaAssegnazione:
    def test_patch_cambia_contratto(self, scena):
        a = RoomAssignment.objects.create(
            room=scena["stanza"],
            tenant=scena["tenant"],
            valid_from=datetime.date(2026, 3, 1),
            canone_mensile=Decimal("450"),
        )
        resp = scena["client"].patch(
            f"/api/v1/room-assignments/{a.pk}/",
            {"contract": scena["attuale"].id},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        a.refresh_from_db()
        assert a.contract_id == scena["attuale"].pk

    def test_patch_contratto_estraneo_400(self, scena, immobile2):
        estraneo = Contract.objects.create(
            property=immobile2,
            data_stipula=datetime.date(2025, 1, 1),
            data_decorrenza=datetime.date(2025, 1, 1),
            durata_anni=4,
        )
        a = RoomAssignment.objects.create(
            room=scena["stanza"],
            tenant=scena["tenant"],
            valid_from=datetime.date(2026, 3, 1),
            canone_mensile=Decimal("450"),
        )
        resp = scena["client"].patch(
            f"/api/v1/room-assignments/{a.pk}/",
            {"contract": estraneo.id},
            format="json",
        )
        assert resp.status_code == 400, resp.content

    def test_eliminare_il_contratto_non_cancella_l_assegnazione(self, scena):
        """SET_NULL: si perde il legame, non l'occupazione né i suoi addebiti."""
        a = RoomAssignment.objects.create(
            room=scena["stanza"],
            tenant=scena["tenant"],
            contract=scena["attuale"],
            valid_from=datetime.date(2026, 3, 1),
            canone_mensile=Decimal("450"),
        )
        scena["attuale"].delete()
        a.refresh_from_db()
        assert a.contract_id is None


class TestCessione:
    def test_il_subentrante_eredita_il_contratto(self, scena):
        corrente = RoomAssignment.objects.create(
            room=scena["stanza"],
            tenant=scena["tenant"],
            contract=scena["attuale"],
            valid_from=datetime.date(2025, 3, 1),
            canone_mensile=Decimal("450"),
        )
        subentrante = TenantProfile.objects.create(
            user=User.objects.create_user(username="inq-subentro"),
            nominativo="Bianchi Luca",
            property=scena["immobile"],
            giorno_pagamento_affitto=5,
        )
        resp = scena["client"].post(
            f"/api/v1/room-assignments/{corrente.pk}/cessione/",
            {
                "data_fine": "2026-06-30",
                "nuovo_tenant": subentrante.id,
                "canone_mensile": "450.00",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        nuovo = RoomAssignment.objects.get(tenant=subentrante)
        assert nuovo.contract_id == scena["attuale"].pk
