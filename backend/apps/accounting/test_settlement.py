"""
Test per accounting.services.settlement.genera_settlement e per il command
omonimo (smoke).

Coperture:
- Cassa virtuale: somma totale voci di un settlement è zero.
- Saldi snapshot per owner coerenti con la rappresentazione cassa virtuale.
- Idempotenza: rerun senza reset solleva, con reset ricrea identicamente.
- Dry-run: nessuna scrittura persiste.
- Concatenazione settlement: il successivo eredita lo snapshot del precedente
  come baseline.
- Spese straordinarie distinte nella descrizione.
- Smoke del command.
"""
import datetime
import io
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db.models import Sum

from accounting.models import OwnerLedgerEntry, OwnerSettlement
from accounting.services.settlement import SettlementGiaEsistente, genera_settlement
from billing.models import Expense, ExpenseCategory, Receivable, StatoPagamento
from properties.models import (
    OwnerProfile,
    OwnershipShare,
    Room,
    RoomAssignment,
    TenantProfile,
)


@pytest.fixture
def sandro(db):
    u = User.objects.create_user("s_set", email="s_set@v.it", password="pwd")
    return OwnerProfile.objects.create(user=u, nominativo="Sandro")


@pytest.fixture
def bruna(db):
    u = User.objects.create_user("b_set", email="b_set@v.it", password="pwd")
    return OwnerProfile.objects.create(user=u, nominativo="Bruna")


@pytest.fixture
def fabio(db):
    u = User.objects.create_user("f_set", email="f_set@v.it", password="pwd")
    return OwnerProfile.objects.create(user=u, nominativo="Fabio")


@pytest.fixture
def quote_due_e_uno(db, immobile, sandro, bruna, fabio):
    """Quote 0.50/0.25/0.25 — somme intere e cifre stabili."""
    OwnershipShare.objects.create(
        property=immobile, owner=sandro, valid_from=datetime.date(2020, 1, 1), quota=Decimal("0.5"),
    )
    OwnershipShare.objects.create(
        property=immobile, owner=bruna, valid_from=datetime.date(2020, 1, 1), quota=Decimal("0.25"),
    )
    OwnershipShare.objects.create(
        property=immobile, owner=fabio, valid_from=datetime.date(2020, 1, 1), quota=Decimal("0.25"),
    )


@pytest.fixture
def assignment(db, immobile):
    u = User.objects.create_user("inq_set", email="inq_set@v.it", password="pwd")
    tenant = TenantProfile.objects.create(
        user=u, property=immobile, nominativo="Inq", giorno_pagamento_affitto=1,
    )
    room = Room.objects.create(property=immobile, nome="Camera Set", ordinamento=70)
    return RoomAssignment.objects.create(
        room=room,
        tenant=tenant,
        valid_from=datetime.date(2024, 1, 1),
        canone_mensile=Decimal("400"),
    )


@pytest.fixture
def receivable_aprile(db, assignment, bruna):
    return Receivable.objects.create(
        assignment=assignment,
        causale=Receivable.Causale.AFFITTO,
        competenza_da=datetime.date(2024, 4, 1),
        competenza_a=datetime.date(2024, 4, 30),
        scadenza=datetime.date(2024, 4, 5),
        importo_dovuto=Decimal("400"),
        importo_pagato=Decimal("400"),
        data_pagamento=datetime.date(2024, 4, 4),
        stato=StatoPagamento.PAGATO,
        incassato_da_owner=bruna,
    )


@pytest.fixture
def expense_imu(db, immobile, sandro):
    cat = ExpenseCategory.objects.create(property=immobile, nome="IMU", codice="imu")
    return Expense.objects.create(
        property=immobile,
        data=datetime.date(2024, 6, 16),
        category=cat,
        importo=Decimal("1200"),
        descrizione="IMU 2024 acconto",
        anticipata_da_owner=sandro,
    )


def test_cassa_virtuale_somma_zero(db, immobile, quote_due_e_uno, receivable_aprile, expense_imu):
    settlement = genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))
    totale = OwnerLedgerEntry.objects.filter(
        riferimento_settlement=settlement,
    ).aggregate(t=Sum("importo"))["t"]
    assert totale == Decimal("0.00")


def test_snapshot_saldi_coerenti(db, immobile, quote_due_e_uno, sandro, bruna, fabio,
                                  receivable_aprile, expense_imu):
    """Verifica i saldi attesi per Receivable affitto + Expense anticipata."""
    settlement = genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))
    # Receivable 400 incassato da Bruna (quota 0.25):
    #   Bruna -300, Sandro +200, Fabio +100
    # Expense 1200 anticipata da Sandro (quota 0.5):
    #   Sandro +600, Bruna -300, Fabio -300
    # Totali: Sandro +800, Bruna -600, Fabio -200
    assert Decimal(settlement.snapshot[str(sandro.pk)]) == Decimal("800.00")
    assert Decimal(settlement.snapshot[str(bruna.pk)]) == Decimal("-600.00")
    assert Decimal(settlement.snapshot[str(fabio.pk)]) == Decimal("-200.00")


def test_voci_create_per_receivable(db, immobile, quote_due_e_uno, sandro, bruna, fabio, receivable_aprile):
    settlement = genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))
    voci = OwnerLedgerEntry.objects.filter(
        riferimento_settlement=settlement,
        riferimento_receivable=receivable_aprile,
    )
    # 3 voci INCASSO_AFFITTO (una per fratello) + 1 AGGIUSTAMENTO per Bruna
    assert voci.count() == 4
    assert voci.filter(tipo=OwnerLedgerEntry.TipoVoce.INCASSO_AFFITTO).count() == 3
    aggiustamento = voci.get(tipo=OwnerLedgerEntry.TipoVoce.AGGIUSTAMENTO)
    assert aggiustamento.owner == bruna
    assert aggiustamento.importo == Decimal("-400")


def test_voci_create_per_expense_con_anticipo(db, immobile, quote_due_e_uno, sandro, expense_imu):
    settlement = genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))
    voci = OwnerLedgerEntry.objects.filter(
        riferimento_settlement=settlement,
        riferimento_expense=expense_imu,
    )
    # 3 voci SPESA + 1 ANTICIPO per Sandro
    assert voci.filter(tipo=OwnerLedgerEntry.TipoVoce.SPESA).count() == 3
    anticipo = voci.get(tipo=OwnerLedgerEntry.TipoVoce.ANTICIPO)
    assert anticipo.owner == sandro
    assert anticipo.importo == Decimal("1200")


def test_voci_per_expense_con_riferimento_quota_owner(db, immobile, quote_due_e_uno, sandro, bruna, fabio):
    """Bruna paga IMU di Fabio: solo 2 voci (SPESA intera per Fabio, ANTICIPO
    per Bruna), somma zero, Sandro non toccato."""
    cat = ExpenseCategory.objects.create(property=immobile, nome="IMU", codice="imu")
    exp = Expense.objects.create(
        property=immobile,
        data=datetime.date(2024, 6, 16),
        category=cat,
        importo=Decimal("1200"),
        descrizione="IMU 2024 Fabio",
        anticipata_da_owner=bruna,
        riferimento_quota_owner=fabio,
    )
    settlement = genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))
    voci = OwnerLedgerEntry.objects.filter(
        riferimento_settlement=settlement, riferimento_expense=exp,
    )
    assert voci.count() == 2
    spesa = voci.get(tipo=OwnerLedgerEntry.TipoVoce.SPESA)
    assert spesa.owner == fabio
    assert spesa.importo == Decimal("-1200")
    anticipo = voci.get(tipo=OwnerLedgerEntry.TipoVoce.ANTICIPO)
    assert anticipo.owner == bruna
    assert anticipo.importo == Decimal("1200")
    assert Decimal(settlement.snapshot[str(sandro.pk)]) == Decimal("0.00")
    assert Decimal(settlement.snapshot[str(bruna.pk)]) == Decimal("1200.00")
    assert Decimal(settlement.snapshot[str(fabio.pk)]) == Decimal("-1200.00")


def test_spesa_personale_pagata_da_se_nessuna_voce(db, immobile, quote_due_e_uno, fabio):
    """Fabio paga la propria IMU: il settlement non crea voci."""
    cat = ExpenseCategory.objects.create(property=immobile, nome="IMU", codice="imu")
    exp = Expense.objects.create(
        property=immobile,
        data=datetime.date(2024, 6, 16),
        category=cat,
        importo=Decimal("1200"),
        descrizione="IMU 2024 Fabio",
        anticipata_da_owner=fabio,
        riferimento_quota_owner=fabio,
    )
    settlement = genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))
    assert not OwnerLedgerEntry.objects.filter(riferimento_expense=exp).exists()
    assert Decimal(settlement.snapshot[str(fabio.pk)]) == Decimal("0.00")


def test_voce_straordinaria_marcata_in_descrizione(db, immobile, quote_due_e_uno, sandro):
    cat = ExpenseCategory.objects.create(property=immobile, nome="Manutenzione", codice="manut")
    Expense.objects.create(
        property=immobile,
        data=datetime.date(2024, 7, 10),
        category=cat,
        importo=Decimal("3000"),
        descrizione="Rifacimento bagno",
        anticipata_da_owner=sandro,
        is_straordinaria=True,
    )
    settlement = genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))
    voci = OwnerLedgerEntry.objects.filter(riferimento_settlement=settlement)
    assert any("[straord]" in v.descrizione for v in voci)


def test_somma_zero_con_quote_a_terzi(db, immobile, sandro, bruna, fabio, assignment):
    """Quote 0.3334/0.3333/0.3333: il resto di arrotondamento non deve
    rompere la cassa virtuale (somma voci = 0 e somma snapshot = 0)."""
    OwnershipShare.objects.create(
        property=immobile, owner=sandro, valid_from=datetime.date(2020, 1, 1), quota=Decimal("0.3334"),
    )
    OwnershipShare.objects.create(
        property=immobile, owner=bruna, valid_from=datetime.date(2020, 1, 1), quota=Decimal("0.3333"),
    )
    OwnershipShare.objects.create(
        property=immobile, owner=fabio, valid_from=datetime.date(2020, 1, 1), quota=Decimal("0.3333"),
    )
    # Importo che non si divide bene per tre.
    Receivable.objects.create(
        assignment=assignment,
        causale=Receivable.Causale.AFFITTO,
        competenza_da=datetime.date(2024, 4, 1),
        competenza_a=datetime.date(2024, 4, 30),
        scadenza=datetime.date(2024, 4, 5),
        importo_dovuto=Decimal("400.01"),
        importo_pagato=Decimal("400.01"),
        data_pagamento=datetime.date(2024, 4, 4),
        stato=StatoPagamento.PAGATO,
        incassato_da_owner=bruna,
    )
    cat = ExpenseCategory.objects.create(property=immobile, nome="IMU", codice="imu")
    Expense.objects.create(
        property=immobile,
        data=datetime.date(2024, 6, 16),
        category=cat,
        importo=Decimal("1000.01"),
        descrizione="IMU",
        anticipata_da_owner=sandro,
    )
    settlement = genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))
    totale_voci = OwnerLedgerEntry.objects.filter(
        riferimento_settlement=settlement,
    ).aggregate(t=Sum("importo"))["t"]
    assert totale_voci == Decimal("0.00")
    somma_snapshot = sum(Decimal(v) for v in settlement.snapshot.values())
    assert somma_snapshot == Decimal("0.00")


def test_idempotenza_richiede_reset(db, immobile, quote_due_e_uno, receivable_aprile):
    genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))
    with pytest.raises(SettlementGiaEsistente):
        genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))


def test_reset_ricrea_identicamente(db, immobile, quote_due_e_uno, sandro, bruna, fabio,
                                    receivable_aprile, expense_imu):
    s1 = genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))
    snap1 = dict(s1.snapshot)
    s2 = genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31), reset=True)
    assert s1.pk == s2.pk
    assert s2.snapshot == snap1


def test_dry_run_non_scrive(db, immobile, quote_due_e_uno, receivable_aprile):
    genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31), dry_run=True)
    assert OwnerSettlement.objects.count() == 0
    assert OwnerLedgerEntry.objects.count() == 0


def test_settlement_concatenati_baseline(db, immobile, quote_due_e_uno, sandro, bruna, fabio, assignment):
    """Il settlement 2025 eredita come baseline il saldo 2024."""
    Receivable.objects.create(
        assignment=assignment,
        causale=Receivable.Causale.AFFITTO,
        competenza_da=datetime.date(2024, 4, 1),
        competenza_a=datetime.date(2024, 4, 30),
        scadenza=datetime.date(2024, 4, 5),
        importo_dovuto=Decimal("400"),
        importo_pagato=Decimal("400"),
        data_pagamento=datetime.date(2024, 4, 4),
        stato=StatoPagamento.PAGATO,
        incassato_da_owner=bruna,
    )
    s2024 = genera_settlement(immobile, datetime.date(2024, 1, 1), datetime.date(2024, 12, 31))
    # 2025 vuoto: snapshot deve coincidere col baseline 2024
    s2025 = genera_settlement(immobile, datetime.date(2025, 1, 1), datetime.date(2025, 12, 31))
    assert s2025.snapshot == s2024.snapshot


def test_command_genera_settlement(db, immobile, quote_due_e_uno, receivable_aprile):
    # Senza --property: nel DB di test c'è un solo immobile, il command lo usa.
    out = io.StringIO()
    call_command("genera_settlement", "--anno", "2024", stdout=out)
    assert "generato" in out.getvalue()
    assert OwnerSettlement.objects.filter(periodo_da=datetime.date(2024, 1, 1)).exists()
