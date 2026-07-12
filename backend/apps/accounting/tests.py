"""
Test per l'app accounting.

Coprono:
- OwnerLedgerEntry: creazione e __str__, FK BT/settlement, tipo=anticipo,
  vincoli di idempotenza (receivable+owner+tipo, expense+owner+tipo),
  comportamento SET_NULL su delete della BT.
- OwnerSettlement: snapshot JSON
- InterOwnerLoan + InterOwnerEntry: prestito bilaterale, FK BT
- WithholdingRule: trattenuta mensile
- properties.quote_attive_at: helper quote pro-quota di un immobile a una
  data, con fallback proporzionale se la somma non chiude a 1.0.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction

from accounting.models import InterOwnerEntry, InterOwnerLoan, OwnerLedgerEntry, OwnerSettlement, WithholdingRule
from billing.models import Expense, ExpenseCategory, Receivable, StatoPagamento
from billing.models.payments import BankTransaction
from properties.models import (
    OwnerBankAccount,
    OwnerProfile,
    OwnershipShare,
    Room,
    RoomAssignment,
    TenantProfile,
    quote_attive_at,
)


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


@pytest.fixture
def bank_account_bruna(db, bruna):
    return OwnerBankAccount.objects.create(
        owner=bruna,
        banca="Intesa",
        intestatario="Bruna Dentella",
        iban="IT60X0542811101000000123456",
    )


@pytest.fixture
def bt_inter_owner(db, bank_account_bruna):
    return BankTransaction.objects.create(
        data=datetime.date(2025, 12, 30),
        descrizione="CONGUAGLIO 2025",
        importo=Decimal("1707.00"),
        owner_account=bank_account_bruna,
    )


@pytest.fixture
def assignment(db, immobile):
    user_inq = User.objects.create_user("arun_acc", email="arun_acc@v.it", password="pwd")
    tenant = TenantProfile.objects.create(
        user=user_inq, property=immobile, nominativo="Arun", giorno_pagamento_affitto=1,
    )
    room = Room.objects.create(property=immobile, nome="Camera Acc", ordinamento=99)
    return RoomAssignment.objects.create(
        room=room,
        tenant=tenant,
        valid_from=datetime.date(2024, 9, 1),
        canone_mensile=Decimal("420"),
    )


@pytest.fixture
def receivable_pagato(db, assignment, bruna):
    return Receivable.objects.create(
        assignment=assignment,
        causale=Receivable.Causale.AFFITTO,
        competenza_da=datetime.date(2025, 4, 1),
        competenza_a=datetime.date(2025, 4, 30),
        scadenza=datetime.date(2025, 4, 5),
        importo_dovuto=Decimal("420.00"),
        importo_pagato=Decimal("420.00"),
        data_pagamento=datetime.date(2025, 4, 4),
        stato=StatoPagamento.PAGATO,
        incassato_da_owner=bruna,
    )


@pytest.fixture
def expense_imu(db, immobile, sandro):
    cat = ExpenseCategory.objects.create(property=immobile, nome="IMU", codice="imu")
    return Expense.objects.create(
        property=immobile,
        data=datetime.date(2025, 6, 16),
        category=cat,
        importo=Decimal("1200.00"),
        descrizione="IMU acconto 2025",
        anticipata_da_owner=sandro,
    )


@pytest.fixture
def settlement_2024(db, immobile):
    return OwnerSettlement.objects.create(
        property=immobile,
        data=datetime.date(2024, 12, 31),
        periodo_da=datetime.date(2024, 1, 1),
        periodo_a=datetime.date(2024, 12, 31),
        descrizione="Chiusura 2024",
        snapshot={},
    )


# ---------------------------------------------------------------------------
# Test OwnerLedgerEntry
# ---------------------------------------------------------------------------


class TestOwnerLedgerEntry:
    def test_creazione_incasso_affitto(self, db, immobile, bruna):
        entry = OwnerLedgerEntry.objects.create(
            property=immobile,
            owner=bruna,
            data=datetime.date(2024, 10, 5),
            descrizione="Affitto ottobre Mariasevera",
            importo=Decimal("420.00"),
            tipo="incasso_affitto",
        )
        assert entry.pk is not None
        assert "+420.00" in str(entry)
        assert "Bruna" in str(entry)

    def test_importo_negativo_spesa(self, db, immobile, sandro):
        """Una spesa è rappresentata con importo negativo."""
        entry = OwnerLedgerEntry.objects.create(
            property=immobile,
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
    def test_creazione_con_snapshot(self, db, immobile, sandro, bruna, fabio):
        snapshot = {
            str(sandro.pk): "500.00",
            str(bruna.pk): "1200.00",
            str(fabio.pk): "-300.00",
        }
        settlement = OwnerSettlement.objects.create(
            property=immobile,
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
    def test_loan_aperto(self, db, immobile, sandro, fabio):
        """Prestito da Sandro a Fabio — aperto."""
        loan = InterOwnerLoan.objects.create(
            property=immobile,
            owner_da=sandro,
            owner_a=fabio,
            data_apertura=datetime.date(2022, 3, 1),
            importo_originale=Decimal("2000.00"),
            descrizione="Prestito personale 2022",
        )
        assert loan.chiuso is False
        assert "aperto" in str(loan)

    def test_entry_bilaterale_positiva(self, db, immobile, bruna, fabio):
        """Bruna paga IMU di Fabio: voce bilaterale positiva (Fabio deve a Bruna)."""
        entry = InterOwnerEntry.objects.create(
            property=immobile,
            owner_da=bruna,
            owner_a=fabio,
            data=datetime.date(2024, 6, 17),
            importo=Decimal("450.00"),
            descrizione="IMU 2024 quota Fabio pagata da Bruna",
        )
        assert entry.importo > 0
        assert "Bruna" in str(entry)
        assert "Fabio" in str(entry)

    def test_entry_con_riferimento_loan(self, db, immobile, sandro, fabio):
        """Una restituzione parziale è collegata al prestito."""
        loan = InterOwnerLoan.objects.create(
            property=immobile,
            owner_da=sandro,
            owner_a=fabio,
            data_apertura=datetime.date(2022, 3, 1),
            importo_originale=Decimal("2000.00"),
            descrizione="Prestito",
        )
        entry = InterOwnerEntry.objects.create(
            property=immobile,
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
    def test_creazione_regola_attiva(self, db, immobile, bruna, fabio):
        """Bruna trattiene €100/mese dalla distribuzione a Fabio."""
        rule = WithholdingRule.objects.create(
            property=immobile,
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

    def test_disattivazione_regola(self, db, immobile, bruna, fabio):
        """Una regola può essere disattivata."""
        rule = WithholdingRule.objects.create(
            property=immobile,
            owner_da=bruna,
            owner_a=fabio,
            importo_mensile=Decimal("100.00"),
            descrizione="Trattenuta",
            valid_from=datetime.date(2024, 1, 1),
            attiva=False,
        )
        assert "inattiva" in str(rule)


# ---------------------------------------------------------------------------
# Test estensione schema (FK BT/settlement, tipo=anticipo, vincoli)
# ---------------------------------------------------------------------------


class TestOwnerLedgerEntryFKBankTransaction:
    def test_voce_collegata_a_bt(self, db, immobile, bruna, bt_inter_owner):
        entry = OwnerLedgerEntry.objects.create(
            property=immobile,
            owner=bruna,
            data=bt_inter_owner.data,
            descrizione="Conguaglio 2025 da Fabio",
            importo=Decimal("853.50"),
            tipo=OwnerLedgerEntry.TipoVoce.INCASSO_CONGUAGLIO,
            bank_transaction=bt_inter_owner,
        )
        assert entry.bank_transaction == bt_inter_owner
        assert bt_inter_owner.ledger_entries.count() == 1

    def test_set_null_su_delete_bt(self, db, immobile, bruna, bt_inter_owner):
        """SET_NULL: cancellare la BT non distrugge la voce ledger."""
        entry = OwnerLedgerEntry.objects.create(
            property=immobile,
            owner=bruna,
            data=bt_inter_owner.data,
            descrizione="Conguaglio",
            importo=Decimal("100"),
            tipo=OwnerLedgerEntry.TipoVoce.INCASSO_CONGUAGLIO,
            bank_transaction=bt_inter_owner,
        )
        bt_inter_owner.delete()
        entry.refresh_from_db()
        assert entry.bank_transaction is None


class TestOwnerLedgerEntryFKSettlement:
    def test_voce_anticipo_collegata_a_settlement(self, db, immobile, sandro, settlement_2024):
        """tipo=anticipo è il credito che Sandro vanta avendo speso di tasca."""
        entry = OwnerLedgerEntry.objects.create(
            property=immobile,
            owner=sandro,
            data=settlement_2024.data,
            descrizione="Anticipo IMU 2024",
            importo=Decimal("800.00"),
            tipo=OwnerLedgerEntry.TipoVoce.ANTICIPO,
            riferimento_settlement=settlement_2024,
        )
        assert entry.tipo == "anticipo"
        assert entry.riferimento_settlement == settlement_2024
        assert settlement_2024.ledger_entries.count() == 1


class TestOwnerLedgerEntryConstraints:
    def test_unique_per_receivable_owner_tipo(self, db, immobile, bruna, receivable_pagato):
        """Un solo incasso_affitto per (Receivable, owner, tipo)."""
        OwnerLedgerEntry.objects.create(
            property=immobile,
            owner=bruna,
            data=receivable_pagato.data_pagamento,
            descrizione="Affitto aprile",
            importo=Decimal("140"),
            tipo=OwnerLedgerEntry.TipoVoce.INCASSO_AFFITTO,
            riferimento_receivable=receivable_pagato,
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            OwnerLedgerEntry.objects.create(
                property=immobile,
                owner=bruna,
                data=receivable_pagato.data_pagamento,
                descrizione="Affitto aprile (duplicato)",
                importo=Decimal("140"),
                tipo=OwnerLedgerEntry.TipoVoce.INCASSO_AFFITTO,
                riferimento_receivable=receivable_pagato,
            )

    def test_unique_consente_owner_diversi(self, db, immobile, sandro, bruna, receivable_pagato):
        """Lo stesso Receivable può avere incassi pro-quota per fratelli diversi."""
        OwnerLedgerEntry.objects.create(
            property=immobile,
            owner=sandro,
            data=receivable_pagato.data_pagamento,
            descrizione="Affitto aprile (Sandro)",
            importo=Decimal("140"),
            tipo=OwnerLedgerEntry.TipoVoce.INCASSO_AFFITTO,
            riferimento_receivable=receivable_pagato,
        )
        OwnerLedgerEntry.objects.create(
            property=immobile,
            owner=bruna,
            data=receivable_pagato.data_pagamento,
            descrizione="Affitto aprile (Bruna)",
            importo=Decimal("140"),
            tipo=OwnerLedgerEntry.TipoVoce.INCASSO_AFFITTO,
            riferimento_receivable=receivable_pagato,
        )
        assert receivable_pagato.ledger_entries.count() == 2

    def test_unique_per_expense_owner_tipo(self, db, immobile, sandro, expense_imu):
        """Un solo voce 'spesa' per (Expense, owner, tipo) — back-fill idempotente."""
        OwnerLedgerEntry.objects.create(
            property=immobile,
            owner=sandro,
            data=expense_imu.data,
            descrizione="IMU pro-quota Sandro",
            importo=Decimal("-400"),
            tipo=OwnerLedgerEntry.TipoVoce.SPESA,
            riferimento_expense=expense_imu,
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            OwnerLedgerEntry.objects.create(
                property=immobile,
                owner=sandro,
                data=expense_imu.data,
                descrizione="IMU duplicata",
                importo=Decimal("-400"),
                tipo=OwnerLedgerEntry.TipoVoce.SPESA,
                riferimento_expense=expense_imu,
            )

    def test_constraint_non_blocca_voci_senza_riferimento(self, db, immobile, sandro):
        """Le voci manuali (senza riferimento_*) non sono soggette al vincolo."""
        for _ in range(3):
            OwnerLedgerEntry.objects.create(
                property=immobile,
                owner=sandro,
                data=datetime.date(2025, 1, 1),
                descrizione="Aggiustamento manuale",
                importo=Decimal("10"),
                tipo=OwnerLedgerEntry.TipoVoce.AGGIUSTAMENTO,
            )
        assert OwnerLedgerEntry.objects.count() == 3


class TestInterOwnerEntryFKBankTransaction:
    def test_voce_bilaterale_collegata_a_bt(self, db, immobile, bruna, fabio, bank_account_bruna):
        bt = BankTransaction.objects.create(
            data=datetime.date(2025, 7, 10),
            descrizione="FABIO RESO",
            importo=Decimal("300.00"),
            owner_account=bank_account_bruna,
        )
        entry = InterOwnerEntry.objects.create(
            property=immobile,
            owner_da=fabio,
            owner_a=bruna,
            data=bt.data,
            importo=Decimal("300.00"),
            descrizione="Restituzione Fabio→Bruna",
            bank_transaction=bt,
        )
        assert entry.bank_transaction == bt
        assert bt.inter_owner_entries.count() == 1


# ---------------------------------------------------------------------------
# Test helper quote_attive_at
# ---------------------------------------------------------------------------


class TestQuoteAttiveAt:
    def test_quote_terzi_uguali(self, db, immobile, sandro, bruna, fabio):
        for owner in (sandro, bruna, fabio):
            OwnershipShare.objects.create(
                property=immobile,
                owner=owner,
                valid_from=datetime.date(2020, 1, 1),
                quota=Decimal("0.3333"),
            )
        # Compensa il residuo di arrotondamento ribilanciando proporzionalmente.
        quote = quote_attive_at(immobile, datetime.date(2025, 6, 1))
        assert set(quote.keys()) == {sandro, bruna, fabio}
        assert sum(quote.values()) == pytest.approx(Decimal("1"), abs=Decimal("0.001"))

    def test_quote_vuote_se_data_anteriore_a_valid_from(self, db, immobile, sandro):
        OwnershipShare.objects.create(
            property=immobile,
            owner=sandro,
            valid_from=datetime.date(2024, 1, 1),
            quota=Decimal("1.0"),
        )
        assert quote_attive_at(immobile, datetime.date(2023, 12, 31)) == {}

    def test_quote_escluse_dopo_valid_to(self, db, immobile, sandro, bruna):
        OwnershipShare.objects.create(
            property=immobile,
            owner=sandro,
            valid_from=datetime.date(2020, 1, 1),
            valid_to=datetime.date(2024, 12, 31),
            quota=Decimal("0.5"),
        )
        OwnershipShare.objects.create(
            property=immobile,
            owner=bruna,
            valid_from=datetime.date(2020, 1, 1),
            valid_to=datetime.date(2024, 12, 31),
            quota=Decimal("0.5"),
        )
        OwnershipShare.objects.create(
            property=immobile,
            owner=sandro,
            valid_from=datetime.date(2025, 1, 1),
            quota=Decimal("1.0"),
        )
        quote = quote_attive_at(immobile, datetime.date(2025, 6, 1))
        assert quote == {sandro: Decimal("1.0")}

    def test_riproporziona_se_somma_diversa_da_uno(self, db, immobile, sandro, bruna):
        """Se i dati storici hanno somma != 1.0 (buchi/refusi), il helper
        ribilancia proporzionalmente."""
        OwnershipShare.objects.create(
            property=immobile,
            owner=sandro,
            valid_from=datetime.date(2020, 1, 1),
            quota=Decimal("0.6"),
        )
        OwnershipShare.objects.create(
            property=immobile,
            owner=bruna,
            valid_from=datetime.date(2020, 1, 1),
            quota=Decimal("0.2"),
        )
        # Somma 0.8 → riproporzionate a 0.75 / 0.25
        quote = quote_attive_at(immobile, datetime.date(2025, 1, 1))
        assert sum(quote.values()) == pytest.approx(Decimal("1"), abs=Decimal("0.001"))
        assert quote[sandro] == pytest.approx(Decimal("0.75"), abs=Decimal("0.001"))
        assert quote[bruna] == pytest.approx(Decimal("0.25"), abs=Decimal("0.001"))
