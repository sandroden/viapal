"""Collegamento in blocco delle occupazioni al loro contratto.

Finché ``RoomAssignment.contract`` è vuoto l'inquilino non vede nessuna carta
di contratto (vedi ``test_documenti_contratto.py``). Il command collega quelle
**iniziate dalla decorrenza in poi** e si ferma dove servirebbe una decisione:
chi c'era già prima, e chi un contratto ce l'ha già.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError

from properties.models import Contract, Room, RoomAssignment, TenantProfile

pytestmark = pytest.mark.django_db

DECORRENZA = datetime.date(2025, 2, 15)


@pytest.fixture
def contratto(immobile):
    return Contract.objects.create(
        property=immobile,
        nome="Collettivo 2025",
        data_stipula=DECORRENZA,
        data_decorrenza=DECORRENZA,
        durata_anni=4,
    )


def _assegna(immobile, nome, dal, al=None, contract=None):
    tenant = TenantProfile.objects.create(
        user=User.objects.create_user(nome),
        property=immobile,
        nominativo=nome,
        giorno_pagamento_affitto=5,
    )
    return RoomAssignment.objects.create(
        room=Room.objects.create(property=immobile, nome=f"C-{nome}"),
        tenant=tenant,
        contract=contract,
        valid_from=dal,
        valid_to=al,
        canone_mensile=Decimal("400"),
    )


class TestCollegaAssegnazioni:
    def test_collega_dalla_decorrenza_in_poi(self, immobile, contratto):
        dopo = _assegna(immobile, "dopo", datetime.date(2025, 7, 1))
        stesso_giorno = _assegna(immobile, "stesso-giorno", DECORRENZA)

        call_command("collega_assegnazioni_contratto", contratto="Collettivo 2025", apply=True)

        for a in (dopo, stesso_giorno):
            a.refresh_from_db()
            assert a.contract_id == contratto.pk

    def test_non_tocca_chi_c_era_gia(self, immobile, contratto):
        """A cavallo della decorrenza serve una decisione, non una regola."""
        prima = _assegna(
            immobile, "prima", datetime.date(2024, 9, 1), datetime.date(2026, 6, 30)
        )
        call_command("collega_assegnazioni_contratto", contratto="Collettivo 2025", apply=True)
        prima.refresh_from_db()
        assert prima.contract_id is None

    def test_non_sovrascrive_un_contratto_gia_indicato(self, immobile, contratto):
        altro = Contract.objects.create(
            property=immobile,
            nome="Suo",
            data_stipula=DECORRENZA,
            data_decorrenza=DECORRENZA,
            durata_anni=4,
        )
        a = _assegna(immobile, "suo", datetime.date(2025, 8, 1), contract=altro)
        call_command("collega_assegnazioni_contratto", contratto="Collettivo 2025", apply=True)
        a.refresh_from_db()
        assert a.contract_id == altro.pk

    def test_non_tocca_un_altro_immobile(self, immobile, immobile2, contratto):
        estranea = _assegna(immobile2, "estranea", datetime.date(2025, 8, 1))
        call_command("collega_assegnazioni_contratto", contratto="Collettivo 2025", apply=True)
        estranea.refresh_from_db()
        assert estranea.contract_id is None

    def test_dry_run_non_scrive(self, immobile, contratto):
        a = _assegna(immobile, "dryrun", datetime.date(2025, 8, 1))
        call_command("collega_assegnazioni_contratto", contratto="Collettivo 2025")
        a.refresh_from_db()
        assert a.contract_id is None

    def test_soglia_esplicita(self, immobile, contratto):
        """--dal sposta la soglia: serve quando la decorrenza non è la data
        da cui vale davvero il collegamento."""
        a = _assegna(immobile, "gennaio", datetime.date(2025, 1, 10))
        call_command(
            "collega_assegnazioni_contratto",
            contratto="Collettivo 2025",
            dal="2025-01-01",
            apply=True,
        )
        a.refresh_from_db()
        assert a.contract_id == contratto.pk

    def test_nome_ambiguo_si_ferma(self, immobile, contratto):
        Contract.objects.create(
            property=immobile,
            nome="Collettivo 2025",  # omonimo
            data_stipula=DECORRENZA,
            data_decorrenza=DECORRENZA,
            durata_anni=4,
        )
        with pytest.raises(CommandError):
            call_command("collega_assegnazioni_contratto", contratto="Collettivo 2025")

    def test_idempotente(self, immobile, contratto):
        a = _assegna(immobile, "due-volte", datetime.date(2025, 8, 1))
        call_command("collega_assegnazioni_contratto", contratto="Collettivo 2025", apply=True)
        call_command("collega_assegnazioni_contratto", contratto="Collettivo 2025", apply=True)
        a.refresh_from_db()
        assert a.contract_id == contratto.pk
