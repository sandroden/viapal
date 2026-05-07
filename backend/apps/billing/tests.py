"""
Test per l'app billing.

Coprono:
- Receivable causale=affitto: smoke test creazione e transizione di stato
- Receivable causale=utenze: relazione con UtilityChargePeriod e campi calcolo
- Receivable causale=extra: importo negativo (accredito) valido
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
    Receivable,
    StatoPagamento,
    Supplier,
    UtilityBill,  # noqa: F401
    UtilityChargePeriod,
)
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
# Test Receivable causale=affitto
# ---------------------------------------------------------------------------


class TestRentPayment:
    """Smoke test per Receivable affitto + transizione di stato."""

    def test_creazione(self, db, assignment):
        payment = Receivable.objects.create(
            assignment=assignment,
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(2024, 10, 1),
            competenza_a=datetime.date(2024, 10, 31),
            importo_dovuto=Decimal("420"),
            scadenza=datetime.date(2024, 10, 5),
        )
        assert payment.pk is not None
        assert payment.stato == StatoPagamento.ATTESO
        assert payment.importo_pagato is None

    def test_str(self, db, assignment):
        payment = Receivable.objects.create(
            assignment=assignment,
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(2024, 10, 1),
            competenza_a=datetime.date(2024, 10, 31),
            importo_dovuto=Decimal("420"),
            scadenza=datetime.date(2024, 10, 5),
        )
        assert "Arun" in str(payment)

    def test_transizione_dichiarato(self, db, assignment):
        payment = Receivable.objects.create(
            assignment=assignment,
            causale=Receivable.Causale.AFFITTO,
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
        payment = Receivable.objects.create(
            assignment=assignment,
            causale=Receivable.Causale.AFFITTO,
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
        payment = Receivable.objects.create(
            assignment=assignment,
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(2024, 9, 15),
            competenza_a=datetime.date(2024, 9, 30),
            importo_dovuto=Decimal("210"),
            scadenza=datetime.date(2024, 9, 20),
            is_aggiustamento=True,
        )
        assert payment.is_aggiustamento is True


# ---------------------------------------------------------------------------
# Test Receivable causale=utenze
# ---------------------------------------------------------------------------


class TestUtilityCharge:
    """Verifica UtilityChargePeriod (totali per voce + giorni_totali) e Receivable utenze (giorni_presenza)."""

    @pytest.fixture
    def period(self, db):
        return UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2024, 10, 1),
            periodo_a=datetime.date(2024, 10, 31),
            tot_luce=Decimal("100.00"),
            tot_gas=Decimal("50.00"),
            tot_tari=Decimal("30.00"),
            giorni_totali=150,
        )

    def test_creazione_charge(self, db, period, assignment):
        charge = Receivable.objects.create(
            utility_period=period,
            assignment=assignment,
            causale=Receivable.Causale.UTENZE,
            competenza_da=period.periodo_da,
            competenza_a=period.periodo_a,
            importo_dovuto=Decimal("36.00"),
            giorni_presenza=30,
            scadenza=datetime.date(2024, 11, 5),
        )
        assert charge.pk is not None
        assert charge.utility_period == period
        assert charge.giorni_presenza == 30

    def test_period_totale(self, db, period):
        assert period.totale_periodo == Decimal("180.00")

    def test_unique_constraint_period_assignment(self, db, period, assignment):
        """Vincolo: due Receivable utenze sullo stesso (period, assignment) non ammesso."""
        from django.db import IntegrityError

        Receivable.objects.create(
            utility_period=period,
            assignment=assignment,
            causale=Receivable.Causale.UTENZE,
            competenza_da=period.periodo_da,
            competenza_a=period.periodo_a,
            importo_dovuto=Decimal("58.50"),
            scadenza=datetime.date(2024, 11, 5),
        )

        with pytest.raises(IntegrityError):
            Receivable.objects.create(
                utility_period=period,
                assignment=assignment,
                causale=Receivable.Causale.UTENZE,
                competenza_da=period.periodo_da,
                competenza_a=period.periodo_a,
                importo_dovuto=Decimal("60.00"),
                scadenza=datetime.date(2024, 11, 5),
            )

    def test_str_period(self, db, period):
        assert "Utenze" in str(period)
        assert "2024-10-01" in str(period)

    def test_charges_via_reverse_relation(self, db, period, assignment):
        """Accesso ai receivable utenze di un period tramite related_name."""
        Receivable.objects.create(
            utility_period=period,
            assignment=assignment,
            causale=Receivable.Causale.UTENZE,
            competenza_da=period.periodo_da,
            competenza_a=period.periodo_a,
            importo_dovuto=Decimal("58.50"),
            scadenza=datetime.date(2024, 11, 5),
        )
        assert period.receivables.count() == 1


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
# Test Receivable causale=extra
# ---------------------------------------------------------------------------


class TestExtraCharge:
    def test_importo_negativo_accredito(self, db, assignment):
        """Un Receivable extra con importo negativo rappresenta un rimborso."""
        charge = Receivable.objects.create(
            assignment=assignment,
            causale=Receivable.Causale.EXTRA,
            competenza_da=datetime.date(2025, 1, 10),
            descrizione="Rimborso quota condominiale",
            importo_dovuto=Decimal("-45.00"),
            scadenza=datetime.date(2025, 1, 31),
        )
        assert charge.importo_dovuto < 0
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
