"""
Test per l'app accounting.

Coprono:
- OwnerLedgerEntry: creazione e __str__
- OwnerSettlement: snapshot JSON
- InterOwnerLoan + InterOwnerEntry: prestito bilaterale
- WithholdingRule: trattenuta mensile
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from accounting.models import InterOwnerEntry, InterOwnerLoan, OwnerLedgerEntry, OwnerSettlement, WithholdingRule
from properties.models import OwnerProfile


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def user_sandro(db):
    return User.objects.create_user("sandro", email="s@v.it", password="pwd")


@pytest.fixture
def user_bruna(db):
    return User.objects.create_user("bruna", email="b@v.it", password="pwd")


@pytest.fixture
def user_fabio(db):
    return User.objects.create_user("fabio", email="f@v.it", password="pwd")


@pytest.fixture
def sandro(db, user_sandro):
    return OwnerProfile.objects.create(user=user_sandro, nominativo="Sandro")


@pytest.fixture
def bruna(db, user_bruna):
    return OwnerProfile.objects.create(user=user_bruna, nominativo="Bruna")


@pytest.fixture
def fabio(db, user_fabio):
    return OwnerProfile.objects.create(user=user_fabio, nominativo="Fabio")


# ---------------------------------------------------------------------------
# Test OwnerLedgerEntry
# ---------------------------------------------------------------------------


class TestOwnerLedgerEntry:
    def test_creazione_incasso_affitto(self, db, bruna):
        entry = OwnerLedgerEntry.objects.create(
            owner=bruna,
            data=datetime.date(2024, 10, 5),
            descrizione="Affitto ottobre Mariasevera",
            importo=Decimal("420.00"),
            tipo="incasso_affitto",
        )
        assert entry.pk is not None
        assert "+420.00" in str(entry)
        assert "Bruna" in str(entry)

    def test_importo_negativo_spesa(self, db, sandro):
        """Una spesa è rappresentata con importo negativo."""
        entry = OwnerLedgerEntry.objects.create(
            owner=sandro,
            data=datetime.date(2024, 6, 17),
            descrizione="IMU anticipata",
            importo=Decimal("-1200.00"),
            tipo="spesa",
        )
        assert entry.importo < 0
        assert "-1200.00" in str(entry)


# ---------------------------------------------------------------------------
# Test OwnerSettlement
# ---------------------------------------------------------------------------


class TestOwnerSettlement:
    def test_creazione_con_snapshot(self, db, sandro, bruna, fabio):
        snapshot = {
            str(sandro.pk): "500.00",
            str(bruna.pk): "1200.00",
            str(fabio.pk): "-300.00",
        }
        settlement = OwnerSettlement.objects.create(
            data=datetime.date(2024, 12, 31),
            periodo_da=datetime.date(2024, 1, 1),
            periodo_a=datetime.date(2024, 12, 31),
            descrizione="Chiusura 2024",
            snapshot=snapshot,
        )
        assert settlement.pk is not None
        assert settlement.snapshot[str(sandro.pk)] == "500.00"
        assert "2024" in str(settlement)


# ---------------------------------------------------------------------------
# Test InterOwnerLoan + InterOwnerEntry
# ---------------------------------------------------------------------------


class TestInterOwnerBilateral:
    def test_loan_aperto(self, db, sandro, fabio):
        """Prestito da Sandro a Fabio — aperto."""
        loan = InterOwnerLoan.objects.create(
            owner_da=sandro,
            owner_a=fabio,
            data_apertura=datetime.date(2022, 3, 1),
            importo_originale=Decimal("2000.00"),
            descrizione="Prestito personale 2022",
        )
        assert loan.chiuso is False
        assert "aperto" in str(loan)

    def test_entry_bilaterale_positiva(self, db, bruna, fabio):
        """Bruna paga IMU di Fabio: voce bilaterale positiva (Fabio deve a Bruna)."""
        entry = InterOwnerEntry.objects.create(
            owner_da=bruna,
            owner_a=fabio,
            data=datetime.date(2024, 6, 17),
            importo=Decimal("450.00"),
            descrizione="IMU 2024 quota Fabio pagata da Bruna",
        )
        assert entry.importo > 0
        assert "Bruna" in str(entry)
        assert "Fabio" in str(entry)

    def test_entry_con_riferimento_loan(self, db, sandro, fabio):
        """Una restituzione parziale è collegata al prestito."""
        loan = InterOwnerLoan.objects.create(
            owner_da=sandro,
            owner_a=fabio,
            data_apertura=datetime.date(2022, 3, 1),
            importo_originale=Decimal("2000.00"),
            descrizione="Prestito",
        )
        entry = InterOwnerEntry.objects.create(
            owner_da=fabio,
            owner_a=sandro,
            data=datetime.date(2024, 1, 1),
            importo=Decimal("-200.00"),  # Fabio restituisce 200 a Sandro
            descrizione="Restituzione parziale",
            riferimento_loan=loan,
        )
        assert entry.riferimento_loan == loan


# ---------------------------------------------------------------------------
# Test WithholdingRule
# ---------------------------------------------------------------------------


class TestWithholdingRule:
    def test_creazione_regola_attiva(self, db, bruna, fabio):
        """Bruna trattiene €100/mese dalla distribuzione a Fabio."""
        rule = WithholdingRule.objects.create(
            owner_da=bruna,
            owner_a=fabio,
            importo_mensile=Decimal("100.00"),
            descrizione="Trattenuta €100/mese restituzione debiti Fabio",
            valid_from=datetime.date(2024, 1, 1),
        )
        assert rule.attiva is True
        assert "100" in str(rule)
        assert "Bruna" in str(rule)
        assert "Fabio" in str(rule)

    def test_disattivazione_regola(self, db, bruna, fabio):
        """Una regola può essere disattivata."""
        rule = WithholdingRule.objects.create(
            owner_da=bruna,
            owner_a=fabio,
            importo_mensile=Decimal("100.00"),
            descrizione="Trattenuta",
            valid_from=datetime.date(2024, 1, 1),
            attiva=False,
        )
        assert "inattiva" in str(rule)
