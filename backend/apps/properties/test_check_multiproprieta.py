"""
Test del comando ``check_multiproprieta`` (verifica di integrità del modello
multi-proprietà).
"""
import datetime
from decimal import Decimal
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from properties.models import (
    OwnerProfile,
    OwnershipShare,
    PropertyMembership,
    Room,
    RoomAssignment,
    TenantProfile,
)

pytestmark = pytest.mark.django_db


def _run():
    """Lancia il comando catturando stdout; ritorna (exit_code, output).

    exit_code è ``None`` quando il comando NON solleva SystemExit (stato
    coerente).
    """
    out = StringIO()
    exit_code = None
    try:
        call_command("check_multiproprieta", stdout=out)
    except SystemExit as e:
        exit_code = e.code
    return exit_code, out.getvalue()


def _owner(prop, suff, quota=Decimal("1.0000"), valid_from=None):
    """Crea un proprietario (user + membership + OwnerProfile + quota) su ``prop``."""
    user = User.objects.create_user(
        f"owner_{suff}", email=f"owner_{suff}@v.it", password="pwd123!"
    )
    PropertyMembership.objects.create(
        property=prop, user=user, ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
    )
    profilo = OwnerProfile.objects.create(user=user, nominativo=f"Owner {suff}")
    OwnershipShare.objects.create(
        property=prop, owner=profilo, quota=quota,
        valid_from=valid_from or datetime.date(2024, 1, 1),
    )
    return profilo


class TestCheckStatoCoerente:
    def test_stato_coerente_esce_ok(self, immobile):
        _owner(immobile, "a")
        exit_code, output = _run()
        assert exit_code is None
        assert "integrità OK" in output


class TestCheckSommaQuote:
    def test_somma_diversa_da_uno_fallisce_citando_la_somma(self, immobile):
        # Quota unica di 0.5: la somma delle quote attive oggi non fa 1.0.
        _owner(immobile, "a", quota=Decimal("0.5000"))
        exit_code, output = _run()
        assert exit_code == 1
        assert "somma quote attive" in output
        assert "0.5000" in output

    def test_somma_corretta_non_fallisce(self, immobile, immobile2):
        _owner(immobile, "a", quota=Decimal("0.5000"))
        _owner(immobile, "b", quota=Decimal("0.5000"))
        _owner(immobile2, "c")
        exit_code, output = _run()
        assert exit_code is None
        assert "integrità OK" in output


class TestCheckOwnerDuplicato:
    def test_owner_con_due_quote_attive_stessa_data_fallisce(self, immobile):
        """Bug realistico: la prima quota non è mai stata chiusa (valid_to)
        quando ne è stata aperta una seconda per lo stesso owner — due righe
        risultano entrambe attive oggi."""
        user = User.objects.create_user(
            "owner_dup", email="owner_dup@v.it", password="pwd123!"
        )
        PropertyMembership.objects.create(
            property=immobile, user=user, ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
        )
        profilo = OwnerProfile.objects.create(user=user, nominativo="Owner Dup")
        OwnershipShare.objects.create(
            property=immobile, owner=profilo, quota=Decimal("0.5000"),
            valid_from=datetime.date(2020, 1, 1),
        )
        OwnershipShare.objects.create(
            property=immobile, owner=profilo, quota=Decimal("0.5000"),
            valid_from=datetime.date(2021, 1, 1),
        )
        exit_code, output = _run()
        assert exit_code == 1
        assert "owner duplicato" in output


class TestCheckUtenzeCrossProperty:
    def test_periodo_utenze_di_altro_immobile_fallisce(self, immobile, immobile2):
        from billing.models import Receivable, UtilityChargePeriod

        _owner(immobile, "a")
        _owner(immobile2, "b")

        user_tenant = User.objects.create_user(
            "inq_x", email="inq_x@v.it", password="pwd123!"
        )
        tenant = TenantProfile.objects.create(
            user=user_tenant, property=immobile, nominativo="Inquilino X",
            giorno_pagamento_affitto=1,
        )
        room = Room.objects.create(property=immobile, nome="Camera", ordinamento=1)
        assignment = RoomAssignment.objects.create(
            room=room, tenant=tenant, valid_from=datetime.date(2024, 9, 1),
            canone_mensile=Decimal("400"),
        )
        # Periodo utenze creato per errore sull'ALTRO immobile.
        periodo = UtilityChargePeriod.objects.create(
            property=immobile2,
            periodo_da=datetime.date(2026, 4, 1),
            periodo_a=datetime.date(2026, 4, 30),
        )
        Receivable.objects.create(
            assignment=assignment,
            causale=Receivable.Causale.UTENZE,
            utility_period=periodo,
            competenza_da=periodo.periodo_da,
            competenza_a=periodo.periodo_a,
            importo_dovuto=Decimal("50"),
            scadenza=datetime.date(2026, 5, 1),
        )
        exit_code, output = _run()
        assert exit_code == 1
        assert "periodo utenze" in output

    def test_periodo_utenze_stesso_immobile_non_fallisce(self, immobile):
        from billing.models import Receivable, UtilityChargePeriod

        _owner(immobile, "a")

        user_tenant = User.objects.create_user(
            "inq_y", email="inq_y@v.it", password="pwd123!"
        )
        tenant = TenantProfile.objects.create(
            user=user_tenant, property=immobile, nominativo="Inquilino Y",
            giorno_pagamento_affitto=1,
        )
        room = Room.objects.create(property=immobile, nome="Camera", ordinamento=1)
        assignment = RoomAssignment.objects.create(
            room=room, tenant=tenant, valid_from=datetime.date(2024, 9, 1),
            canone_mensile=Decimal("400"),
        )
        periodo = UtilityChargePeriod.objects.create(
            property=immobile,
            periodo_da=datetime.date(2026, 4, 1),
            periodo_a=datetime.date(2026, 4, 30),
        )
        Receivable.objects.create(
            assignment=assignment,
            causale=Receivable.Causale.UTENZE,
            utility_period=periodo,
            competenza_da=periodo.periodo_da,
            competenza_a=periodo.periodo_a,
            importo_dovuto=Decimal("50"),
            scadenza=datetime.date(2026, 5, 1),
        )
        exit_code, output = _run()
        assert exit_code is None
        assert "integrità OK" in output
