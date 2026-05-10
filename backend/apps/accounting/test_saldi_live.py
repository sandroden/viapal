"""
Test per accounting.services.saldi_live.calcola_saldi_correnti.

Scenari coperti:
- 3 fratelli con quote uguali, nessun flusso → saldi tutti zero.
- Receivable pagato incassato da uno solo → gli altri vantano credito su di lui.
- Expense anticipata da uno → gli altri gli devono pro-quota; anticipi_pendenti
  riflette la fetta degli altri.
- Settlement chiuso → fa da baseline e il periodo aperto comincia dal giorno
  successivo (transazioni precedenti vengono escluse dal calcolo live).
- BT inter-owner marcata (OwnerLedgerEntry collegata a BT) → entra nel saldo.
- Quote retroattive: quote attive a at_date determinano la decomposizione.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from accounting.models import OwnerLedgerEntry, OwnerSettlement
from accounting.services.saldi_live import calcola_saldi_correnti
from billing.models import Expense, ExpenseCategory, Receivable, StatoPagamento
from billing.models.payments import BankTransaction
from properties.models import (
    OwnerBankAccount,
    OwnerProfile,
    OwnershipShare,
    Room,
    RoomAssignment,
    TenantProfile,
)


@pytest.fixture
def sandro(db):
    u = User.objects.create_user("s_sl", email="s_sl@v.it", password="pwd")
    return OwnerProfile.objects.create(user=u, nominativo="Sandro")


@pytest.fixture
def bruna(db):
    u = User.objects.create_user("b_sl", email="b_sl@v.it", password="pwd")
    return OwnerProfile.objects.create(user=u, nominativo="Bruna")


@pytest.fixture
def fabio(db):
    u = User.objects.create_user("f_sl", email="f_sl@v.it", password="pwd")
    return OwnerProfile.objects.create(user=u, nominativo="Fabio")


@pytest.fixture
def quote_terzi(db, sandro, bruna, fabio):
    # Quote esatte 1/2 / 1/4 / 1/4: somme intere e cifre stabili nei test.
    OwnershipShare.objects.create(
        owner=sandro, valid_from=datetime.date(2020, 1, 1), quota=Decimal("0.5"),
    )
    OwnershipShare.objects.create(
        owner=bruna, valid_from=datetime.date(2020, 1, 1), quota=Decimal("0.25"),
    )
    OwnershipShare.objects.create(
        owner=fabio, valid_from=datetime.date(2020, 1, 1), quota=Decimal("0.25"),
    )


@pytest.fixture
def assignment(db):
    u = User.objects.create_user("inq_sl", email="inq_sl@v.it", password="pwd")
    tenant = TenantProfile.objects.create(user=u, nominativo="Inq", giorno_pagamento_affitto=1)
    room = Room.objects.create(nome="Camera SL", ordinamento=80)
    return RoomAssignment.objects.create(
        room=room,
        tenant=tenant,
        valid_from=datetime.date(2024, 1, 1),
        canone_mensile=Decimal("400"),
    )


@pytest.fixture
def conto_bruna(db, bruna):
    return OwnerBankAccount.objects.create(
        owner=bruna, banca="Intesa", intestatario="Bruna", iban="IT60X0542811101000000000111",
    )


def test_nessun_flusso_saldi_zero(db, quote_terzi, sandro, bruna, fabio):
    saldi = calcola_saldi_correnti(datetime.date(2025, 6, 30))
    assert set(saldi.keys()) == {sandro, bruna, fabio}
    for s in saldi.values():
        assert s.totale == Decimal("0")
        assert s.baseline_settlement == Decimal("0")


def test_incasso_su_un_solo_owner(db, quote_terzi, sandro, bruna, fabio, assignment):
    """Bruna incassa 400€ di affitto: tiene i soldi pro-quota di tutti, quindi
    deve la fetta degli altri. Sandro/Fabio vantano credito su Bruna."""
    Receivable.objects.create(
        assignment=assignment,
        causale=Receivable.Causale.AFFITTO,
        competenza_da=datetime.date(2025, 4, 1),
        competenza_a=datetime.date(2025, 4, 30),
        scadenza=datetime.date(2025, 4, 5),
        importo_dovuto=Decimal("400"),
        importo_pagato=Decimal("400"),
        data_pagamento=datetime.date(2025, 4, 4),
        stato=StatoPagamento.PAGATO,
        incassato_da_owner=bruna,
    )
    saldi = calcola_saldi_correnti(datetime.date(2025, 6, 30))
    # Bruna (quota 0.25): debito -(1-0.25)*400 = -300 (deve restituire agli altri)
    assert saldi[bruna].totale == Decimal("-300.00")
    # Sandro (quota 0.5): credito 0.5*400 = 200 (sua fetta che Bruna le deve)
    assert saldi[sandro].totale == Decimal("200.00")
    # Fabio (quota 0.25): credito 0.25*400 = 100
    assert saldi[fabio].totale == Decimal("100.00")
    assert saldi[bruna].incassi_per_causale["affitto"] == Decimal("-300.00")
    assert saldi[sandro].incassi_per_causale["affitto"] == Decimal("200.00")


def test_spesa_anticipata_genera_anticipi(db, quote_terzi, sandro, bruna, fabio):
    """Sandro anticipa 1200 IMU: anticipi_pendenti = (1-0.5)*1200 = 600."""
    cat = ExpenseCategory.objects.create(nome="IMU", codice="imu")
    Expense.objects.create(
        data=datetime.date(2025, 6, 16),
        category=cat,
        importo=Decimal("1200"),
        descrizione="IMU 2025 acconto",
        anticipata_da_owner=sandro,
    )
    saldi = calcola_saldi_correnti(datetime.date(2025, 6, 30))
    assert saldi[sandro].totale == Decimal("600.00")
    assert saldi[sandro].anticipi_pendenti == Decimal("600.00")
    assert saldi[bruna].totale == Decimal("-300.00")
    assert saldi[fabio].totale == Decimal("-300.00")
    chiave = "imu|ord"
    assert saldi[sandro].spese_per_categoria[chiave] == Decimal("600.00")
    assert saldi[bruna].spese_per_categoria[chiave] == Decimal("-300.00")


def test_settlement_baseline_e_periodo_aperto(db, quote_terzi, sandro, bruna, fabio, assignment):
    """Settlement 2024 chiude i conti: i flussi precedenti non entrano nel
    calcolo live, baseline_settlement esprime la posizione di partenza."""
    OwnerSettlement.objects.create(
        data=datetime.date(2024, 12, 31),
        periodo_da=datetime.date(2024, 1, 1),
        periodo_a=datetime.date(2024, 12, 31),
        descrizione="Chiusura 2024",
        snapshot={str(sandro.pk): "100.00", str(bruna.pk): "-50.00", str(fabio.pk): "-50.00"},
    )
    # Receivable pagato a dicembre 2024: deve essere ignorato (precedente al periodo aperto)
    Receivable.objects.create(
        assignment=assignment,
        causale=Receivable.Causale.AFFITTO,
        competenza_da=datetime.date(2024, 12, 1),
        competenza_a=datetime.date(2024, 12, 31),
        scadenza=datetime.date(2024, 12, 5),
        importo_dovuto=Decimal("400"),
        importo_pagato=Decimal("400"),
        data_pagamento=datetime.date(2024, 12, 10),
        stato=StatoPagamento.PAGATO,
        incassato_da_owner=bruna,
    )
    saldi = calcola_saldi_correnti(datetime.date(2025, 6, 30))
    # Solo baseline, niente flussi nel periodo
    assert saldi[sandro].totale == Decimal("100.00")
    assert saldi[sandro].baseline_settlement == Decimal("100.00")
    assert saldi[bruna].totale == Decimal("-50.00")
    assert saldi[bruna].incassi_per_causale == {}


def test_bt_inter_owner_marcata(db, quote_terzi, sandro, bruna, fabio, conto_bruna):
    """Una BT marcata genera voci ledger A che entrano nel saldo."""
    bt = BankTransaction.objects.create(
        data=datetime.date(2025, 5, 10),
        descrizione="CONGUAGLIO",
        importo=Decimal("700"),
        owner_account=conto_bruna,
    )
    # Sandro paga 700 a Bruna come conguaglio: Bruna riceve, Sandro paga
    OwnerLedgerEntry.objects.create(
        owner=bruna,
        data=bt.data,
        descrizione="Conguaglio da Sandro",
        importo=Decimal("700"),
        tipo=OwnerLedgerEntry.TipoVoce.INCASSO_CONGUAGLIO,
        bank_transaction=bt,
    )
    OwnerLedgerEntry.objects.create(
        owner=sandro,
        data=bt.data,
        descrizione="Pagamento conguaglio a Bruna",
        importo=Decimal("-700"),
        tipo=OwnerLedgerEntry.TipoVoce.AGGIUSTAMENTO,
        bank_transaction=bt,
    )
    saldi = calcola_saldi_correnti(datetime.date(2025, 6, 30))
    assert saldi[bruna].bt_inter_owner == Decimal("700")
    assert saldi[sandro].bt_inter_owner == Decimal("-700")
    assert saldi[fabio].bt_inter_owner == Decimal("0")
    assert saldi[bruna].totale == Decimal("700")
    assert saldi[sandro].totale == Decimal("-700")


def test_at_date_anteriore_a_quote_torna_dict_vuoto(db, quote_terzi):
    """Prima del valid_from delle quote nessun saldo è calcolabile."""
    saldi = calcola_saldi_correnti(datetime.date(2019, 1, 1))
    assert saldi == {}
