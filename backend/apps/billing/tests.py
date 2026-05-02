"""
Test per l'app billing.

Coprono:
- RentPayment: smoke test creazione e transizione di stato
- UtilityCharge: relazione con UtilityChargePeriod e UtilityChargeLine
- ExtraCharge: importo negativo (accredito) valido
- Supplier + ExpenseCategory + Expense: creazione
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from billing.models import (
    AnnualUtilityCost,
    Expense,
    ExpenseCategory,
    ExtraCharge,
    RentPayment,
    Supplier,
    UtilityBill,
    UtilityCharge,
    UtilityChargeLine,
    UtilityChargePeriod,
)
from billing.models import StatoPagamento
from properties.models import OwnerProfile, Room, RoomAssignment, TenantProfile


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def user_owner(db):
    return User.objects.create_user("bruna", email="bruna@v.it", password="pwd")


@pytest.fixture
def user_tenant(db):
    return User.objects.create_user("arun", email="arun@v.it", password="pwd")


@pytest.fixture
def owner(db, user_owner):
    return OwnerProfile.objects.create(user=user_owner, nominativo="Bruna Dentella")


@pytest.fixture
def tenant(db, user_tenant):
    return TenantProfile.objects.create(
        user=user_tenant,
        nominativo="Arun",
        giorno_pagamento_affitto=1,
    )


@pytest.fixture
def room(db):
    return Room.objects.create(nome="Camera 3", ordinamento=3)


@pytest.fixture
def assignment(db, room, tenant):
    return RoomAssignment.objects.create(
        room=room,
        tenant=tenant,
        valid_from=datetime.date(2024, 9, 1),
        canone_mensile=Decimal("420"),
        deposito_versato=Decimal("840"),
    )


@pytest.fixture
def supplier_luce(db):
    return Supplier.objects.create(nome="Enel Energia", tipo="energia")


# ---------------------------------------------------------------------------
# Test RentPayment
# ---------------------------------------------------------------------------


class TestRentPayment:
    """Smoke test per RentPayment + transizione di stato."""

    def test_creazione(self, db, assignment):
        """Crea un pagamento affitto in stato 'atteso'."""
        payment = RentPayment.objects.create(
            assignment=assignment,
            competenza_da=datetime.date(2024, 10, 1),
            competenza_a=datetime.date(2024, 10, 31),
            importo_dovuto=Decimal("420"),
            scadenza=datetime.date(2024, 10, 5),
        )
        assert payment.pk is not None
        assert payment.stato == StatoPagamento.ATTESO
        assert payment.importo_pagato is None

    def test_str(self, db, assignment):
        payment = RentPayment.objects.create(
            assignment=assignment,
            competenza_da=datetime.date(2024, 10, 1),
            competenza_a=datetime.date(2024, 10, 31),
            importo_dovuto=Decimal("420"),
            scadenza=datetime.date(2024, 10, 5),
        )
        assert "Arun" in str(payment)
        assert "2024/10" in str(payment)

    def test_transizione_dichiarato(self, db, assignment):
        """L'inquilino dichiara il pagamento: stato passa a 'dichiarato'."""
        payment = RentPayment.objects.create(
            assignment=assignment,
            competenza_da=datetime.date(2024, 10, 1),
            competenza_a=datetime.date(2024, 10, 31),
            importo_dovuto=Decimal("420"),
            scadenza=datetime.date(2024, 10, 5),
        )
        payment.stato = StatoPagamento.DICHIARATO
        payment.importo_pagato = Decimal("420")
        payment.data_pagamento = datetime.date(2024, 10, 3)
        payment.save()

        payment.refresh_from_db()
        assert payment.stato == StatoPagamento.DICHIARATO

    def test_transizione_pagato(self, db, assignment, owner):
        """Il proprietario conferma: stato diventa 'pagato'."""
        payment = RentPayment.objects.create(
            assignment=assignment,
            competenza_da=datetime.date(2024, 10, 1),
            competenza_a=datetime.date(2024, 10, 31),
            importo_dovuto=Decimal("420"),
            scadenza=datetime.date(2024, 10, 5),
            stato=StatoPagamento.DICHIARATO,
        )
        payment.stato = StatoPagamento.PAGATO
        payment.incassato_da_owner = owner
        payment.save()

        payment.refresh_from_db()
        assert payment.stato == StatoPagamento.PAGATO

    def test_is_aggiustamento(self, db, assignment):
        """Pagamento pro-rata per ingresso a metà mese."""
        payment = RentPayment.objects.create(
            assignment=assignment,
            competenza_da=datetime.date(2024, 9, 15),
            competenza_a=datetime.date(2024, 9, 30),
            importo_dovuto=Decimal("210"),  # metà mese
            scadenza=datetime.date(2024, 9, 20),
            is_aggiustamento=True,
        )
        assert payment.is_aggiustamento is True


# ---------------------------------------------------------------------------
# Test UtilityCharge + UtilityChargeLine
# ---------------------------------------------------------------------------


class TestUtilityCharge:
    """Verifica la relazione UtilityChargePeriod -> UtilityCharge -> UtilityChargeLine."""

    @pytest.fixture
    def period(self, db):
        return UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2024, 10, 1),
            periodo_a=datetime.date(2024, 10, 31),
        )

    def test_creazione_charge(self, db, period, assignment):
        """Crea un UtilityCharge collegato a un periodo."""
        charge = UtilityCharge.objects.create(
            period=period,
            assignment=assignment,
            importo_totale=Decimal("58.50"),
            scadenza=datetime.date(2024, 11, 5),
        )
        assert charge.pk is not None
        assert charge.period == period

    def test_creazione_lines(self, db, period, assignment):
        """Un UtilityCharge può avere più righe di dettaglio."""
        charge = UtilityCharge.objects.create(
            period=period,
            assignment=assignment,
            importo_totale=Decimal("58.50"),
            scadenza=datetime.date(2024, 11, 5),
        )

        line_luce = UtilityChargeLine.objects.create(
            charge=charge,
            voce="luce",
            importo=Decimal("27.00"),
            dettaglio="Quota pro-rata 30 giorni",
        )
        line_gas = UtilityChargeLine.objects.create(
            charge=charge,
            voce="gas",
            importo=Decimal("22.00"),
        )
        line_tari = UtilityChargeLine.objects.create(
            charge=charge,
            voce="tari",
            importo=Decimal("9.50"),
            dettaglio="TARI 510€/anno × 30/365",
        )

        assert charge.lines.count() == 3
        assert sum(l.importo for l in charge.lines.all()) == Decimal("58.50")

    def test_unique_constraint_period_assignment(self, db, period, assignment):
        """Non possono esistere due UtilityCharge per la stessa coppia period+assignment."""
        from django.db import IntegrityError

        UtilityCharge.objects.create(
            period=period,
            assignment=assignment,
            importo_totale=Decimal("58.50"),
            scadenza=datetime.date(2024, 11, 5),
        )

        with pytest.raises(IntegrityError):
            UtilityCharge.objects.create(
                period=period,
                assignment=assignment,
                importo_totale=Decimal("60.00"),
                scadenza=datetime.date(2024, 11, 5),
            )

    def test_str_period(self, db, period):
        assert "Conguaglio" in str(period)
        assert "2024-10-01" in str(period)

    def test_charges_via_reverse_relation(self, db, period, assignment):
        """Accesso ai charges di un period tramite related_name."""
        UtilityCharge.objects.create(
            period=period,
            assignment=assignment,
            importo_totale=Decimal("58.50"),
            scadenza=datetime.date(2024, 11, 5),
        )
        assert period.charges.count() == 1


# ---------------------------------------------------------------------------
# Test AnnualUtilityCost (TARI)
# ---------------------------------------------------------------------------


class TestAnnualUtilityCost:
    def test_creazione_tari(self, db):
        tari = AnnualUtilityCost.objects.create(
            voce="tari",
            anno=2024,
            importo_annuale=Decimal("510.00"),
            valid_from=datetime.date(2024, 1, 1),
        )
        assert tari.pk is not None
        assert "TARI" in str(tari)
        assert "510.00" in str(tari)


# ---------------------------------------------------------------------------
# Test ExtraCharge
# ---------------------------------------------------------------------------


class TestExtraCharge:
    def test_importo_negativo_accredito(self, db, assignment):
        """Un addebito extra con importo negativo rappresenta un rimborso."""
        charge = ExtraCharge.objects.create(
            assignment=assignment,
            data=datetime.date(2025, 1, 10),
            descrizione="Rimborso quota condominiale",
            importo=Decimal("-45.00"),
            scadenza=datetime.date(2025, 1, 31),
        )
        assert charge.importo < 0
        assert "Rimborso" in str(charge)


# ---------------------------------------------------------------------------
# Test Expense
# ---------------------------------------------------------------------------


class TestExpense:
    def test_creazione(self, db, owner):
        cat = ExpenseCategory.objects.create(nome="IMU", codice="imu")
        expense = Expense.objects.create(
            data=datetime.date(2024, 6, 17),
            category=cat,
            importo=Decimal("1200.00"),
            descrizione="IMU 2024",
            anticipata_da_owner=owner,
        )
        assert expense.pk is not None
        assert "IMU 2024" in str(expense)

    def test_expense_con_riferimento_quota_owner(self, db):
        """Bruna paga IMU di Fabio: riferimento_quota_owner = Fabio."""
        user_bruna = User.objects.create_user("bruna2", email="b2@v.it", password="pwd")
        user_fabio = User.objects.create_user("fabio2", email="f2@v.it", password="pwd")
        bruna = OwnerProfile.objects.create(user=user_bruna, nominativo="Bruna")
        fabio = OwnerProfile.objects.create(user=user_fabio, nominativo="Fabio")

        cat = ExpenseCategory.objects.create(nome="IMU", codice="imu2")
        expense = Expense.objects.create(
            data=datetime.date(2024, 6, 17),
            category=cat,
            importo=Decimal("450.00"),
            descrizione="IMU 2024 quota Fabio",
            anticipata_da_owner=bruna,
            riferimento_quota_owner=fabio,
        )
        assert expense.riferimento_quota_owner == fabio
