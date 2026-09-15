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
from django.db.utils import IntegrityError

from accounting.models import OwnerLedgerEntry, OwnerSettlement
from accounting.services.bt_inter_owner import marca_bt_come_ledger
from accounting.services.saldi_live import (
    calcola_piano_rientro,
    calcola_saldi_correnti,
    verifica_quadratura,
)
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
def quote_terzi(db, immobile, sandro, bruna, fabio):
    # Quote esatte 1/2 / 1/4 / 1/4: somme intere e cifre stabili nei test.
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
    u = User.objects.create_user("inq_sl", email="inq_sl@v.it", password="pwd")
    tenant = TenantProfile.objects.create(
        user=u, property=immobile, nominativo="Inq", giorno_pagamento_affitto=1,
    )
    room = Room.objects.create(property=immobile, nome="Camera SL", ordinamento=80)
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


def test_nessun_flusso_saldi_zero(db, immobile, quote_terzi, sandro, bruna, fabio):
    saldi = calcola_saldi_correnti(immobile, datetime.date(2025, 6, 30))
    assert set(saldi.keys()) == {sandro, bruna, fabio}
    for s in saldi.values():
        assert s.totale == Decimal("0")
        assert s.baseline_settlement == Decimal("0")


def test_incasso_su_un_solo_owner(db, immobile, quote_terzi, sandro, bruna, fabio, assignment):
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
    saldi = calcola_saldi_correnti(immobile, datetime.date(2025, 6, 30))
    # Bruna (quota 0.25): debito -(1-0.25)*400 = -300 (deve restituire agli altri)
    assert saldi[bruna].totale == Decimal("-300.00")
    # Sandro (quota 0.5): credito 0.5*400 = 200 (sua fetta che Bruna le deve)
    assert saldi[sandro].totale == Decimal("200.00")
    # Fabio (quota 0.25): credito 0.25*400 = 100
    assert saldi[fabio].totale == Decimal("100.00")
    assert saldi[bruna].incassi_per_causale["affitto"] == Decimal("-300.00")
    assert saldi[sandro].incassi_per_causale["affitto"] == Decimal("200.00")


def test_spesa_anticipata_genera_anticipi(db, immobile, quote_terzi, sandro, bruna, fabio):
    """Sandro anticipa 1200 IMU: anticipi_pendenti = (1-0.5)*1200 = 600."""
    cat = ExpenseCategory.objects.create(property=immobile, nome="IMU", codice="imu")
    Expense.objects.create(
        property=immobile,
        data=datetime.date(2025, 6, 16),
        category=cat,
        importo=Decimal("1200"),
        descrizione="IMU 2025 acconto",
        anticipata_da_owner=sandro,
    )
    saldi = calcola_saldi_correnti(immobile, datetime.date(2025, 6, 30))
    assert saldi[sandro].totale == Decimal("600.00")
    assert saldi[sandro].anticipi_pendenti == Decimal("600.00")
    assert saldi[bruna].totale == Decimal("-300.00")
    assert saldi[fabio].totale == Decimal("-300.00")
    chiave = "imu|ord"
    assert saldi[sandro].spese_per_categoria[chiave] == Decimal("600.00")
    assert saldi[bruna].spese_per_categoria[chiave] == Decimal("-300.00")


def test_spesa_con_riferimento_quota_owner(db, immobile, quote_terzi, sandro, bruna, fabio):
    """Bruna paga 1200 di IMU *di Fabio*: niente pro-quota. Bruna vanta
    credito intero su Fabio, Sandro non c'entra."""
    cat = ExpenseCategory.objects.create(property=immobile, nome="IMU", codice="imu")
    Expense.objects.create(
        property=immobile,
        data=datetime.date(2025, 6, 16),
        category=cat,
        importo=Decimal("1200"),
        descrizione="IMU 2025 Fabio",
        anticipata_da_owner=bruna,
        riferimento_quota_owner=fabio,
    )
    saldi = calcola_saldi_correnti(immobile, datetime.date(2025, 6, 30))
    assert saldi[bruna].totale == Decimal("1200")
    assert saldi[bruna].anticipi_pendenti == Decimal("1200")
    assert saldi[fabio].totale == Decimal("-1200")
    assert saldi[sandro].totale == Decimal("0")
    chiave = "imu|ord"
    assert saldi[bruna].spese_per_categoria[chiave] == Decimal("1200")
    assert saldi[fabio].spese_per_categoria[chiave] == Decimal("-1200")
    assert chiave not in saldi[sandro].spese_per_categoria


def test_spesa_personale_pagata_da_se_non_tocca_i_saldi(db, immobile, quote_terzi, sandro, bruna, fabio):
    """Fabio paga la propria IMU (riferimento = anticipante): nessun effetto."""
    cat = ExpenseCategory.objects.create(property=immobile, nome="IMU", codice="imu")
    Expense.objects.create(
        property=immobile,
        data=datetime.date(2025, 6, 16),
        category=cat,
        importo=Decimal("1200"),
        descrizione="IMU 2025 Fabio",
        anticipata_da_owner=fabio,
        riferimento_quota_owner=fabio,
    )
    saldi = calcola_saldi_correnti(immobile, datetime.date(2025, 6, 30))
    for s in saldi.values():
        assert s.totale == Decimal("0")
        assert s.spese_per_categoria == {}


def test_settlement_baseline_e_periodo_aperto(db, immobile, quote_terzi, sandro, bruna, fabio, assignment):
    """Settlement 2024 chiude i conti: i flussi precedenti non entrano nel
    calcolo live, baseline_settlement esprime la posizione di partenza."""
    OwnerSettlement.objects.create(
        property=immobile,
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
    saldi = calcola_saldi_correnti(immobile, datetime.date(2025, 6, 30))
    # Solo baseline, niente flussi nel periodo
    assert saldi[sandro].totale == Decimal("100.00")
    assert saldi[sandro].baseline_settlement == Decimal("100.00")
    assert saldi[bruna].totale == Decimal("-50.00")
    assert saldi[bruna].incassi_per_causale == {}


def test_bt_inter_owner_marcata(db, immobile, quote_terzi, sandro, bruna, fabio, conto_bruna):
    """Una BT marcata genera voci ledger A che entrano nel saldo.

    Convenzione: chi riceve denaro ha una voce negativa (il suo credito verso
    gli altri si riduce), chi lo eroga una voce positiva.
    """
    bt = BankTransaction.objects.create(
        data=datetime.date(2025, 5, 10),
        descrizione="CONGUAGLIO",
        importo=Decimal("700"),
        owner_account=conto_bruna,
    )
    # Sandro paga 700 a Bruna come conguaglio: Bruna riceve, Sandro paga
    OwnerLedgerEntry.objects.create(
        property=immobile,
        owner=bruna,
        data=bt.data,
        descrizione="Conguaglio da Sandro",
        importo=Decimal("-700"),
        tipo=OwnerLedgerEntry.TipoVoce.INCASSO_CONGUAGLIO,
        bank_transaction=bt,
    )
    OwnerLedgerEntry.objects.create(
        property=immobile,
        owner=sandro,
        data=bt.data,
        descrizione="Pagamento conguaglio a Bruna",
        importo=Decimal("700"),
        tipo=OwnerLedgerEntry.TipoVoce.AGGIUSTAMENTO,
        bank_transaction=bt,
    )
    saldi = calcola_saldi_correnti(immobile, datetime.date(2025, 6, 30))
    assert saldi[bruna].bt_inter_owner == Decimal("-700")
    assert saldi[sandro].bt_inter_owner == Decimal("700")
    assert saldi[fabio].bt_inter_owner == Decimal("0")
    assert saldi[bruna].totale == Decimal("-700")
    assert saldi[sandro].totale == Decimal("700")


def test_marcatura_distribuzione_estingue_il_debito_di_chi_ha_incassato(
    db, immobile, quote_terzi, sandro, bruna, fabio, conto_bruna, assignment,
):
    """Bruna incassa l'affitto e ne gira una parte a Fabio: il debito cala.

    È il verso che conta: il bonifico esce dal conto di Bruna (importo
    negativo) e deve farla risalire, non scendere ancora.
    """
    Receivable.objects.create(
        assignment=assignment,
        causale=Receivable.Causale.AFFITTO,
        competenza_da=datetime.date(2025, 5, 1),
        competenza_a=datetime.date(2025, 5, 31),
        scadenza=datetime.date(2025, 5, 1),
        importo_dovuto=Decimal("400"),
        importo_pagato=Decimal("400"),
        data_pagamento=datetime.date(2025, 5, 2),
        stato=StatoPagamento.PAGATO,
        incassato_da_owner=bruna,
    )
    saldi = calcola_saldi_correnti(immobile, datetime.date(2025, 5, 31))
    # Bruna tiene i 3/4 degli altri; Fabio vanta il suo quarto.
    assert saldi[bruna].totale == Decimal("-300")
    assert saldi[fabio].totale == Decimal("100")

    bt = BankTransaction.objects.create(
        data=datetime.date(2025, 5, 20),
        descrizione="quota Fabio",
        importo=Decimal("-100"),
        owner_account=conto_bruna,
    )
    marca_bt_come_ledger(
        bt, property=immobile, tipo="distribuzione", controparte_owner=fabio,
    )

    saldi = calcola_saldi_correnti(immobile, datetime.date(2025, 5, 31))
    assert saldi[bruna].totale == Decimal("-200")
    assert saldi[fabio].totale == Decimal("0")
    assert saldi[sandro].totale == Decimal("200")


def test_at_date_anteriore_a_quote_torna_dict_vuoto(db, immobile, quote_terzi):
    """Prima del valid_from delle quote nessun saldo è calcolabile."""
    saldi = calcola_saldi_correnti(immobile, datetime.date(2019, 1, 1))
    assert saldi == {}


# ---------------------------------------------------------------------------
# Quadratura
# ---------------------------------------------------------------------------


def test_quadratura_ok_con_flussi_completi(db, immobile, quote_terzi, sandro, bruna, fabio, assignment):
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
    at = datetime.date(2025, 6, 30)
    saldi = calcola_saldi_correnti(immobile, at)
    q = verifica_quadratura(immobile, at, saldi)
    assert q.quadra is True
    assert q.somma_saldi == Decimal("0.00")
    assert q.receivable_orfani == []
    assert q.expense_orfane == []


def test_db_rifiuta_pagato_senza_incassante(db, immobile, quote_terzi, assignment):
    """Un addebito pagato senza incassante non è più rappresentabile.

    Era la causa degli «incassi esclusi dal calcolo» nei saldi: adesso il
    vincolo di database lo impedisce a monte, da qualunque strada di scrittura.
    """
    with pytest.raises(IntegrityError):
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
            incassato_da_owner=None,
        )


def test_quadratura_segnala_anticipante_senza_quota(db, immobile, quote_terzi, sandro, bruna, fabio):
    """Spesa anticipata da un owner senza quota attiva: la somma dei saldi
    non fa più zero e la spesa è elencata fra le orfane."""
    u = User.objects.create_user("x_sl", email="x_sl@v.it", password="pwd")
    esterno = OwnerProfile.objects.create(user=u, nominativo="Esterno")
    cat = ExpenseCategory.objects.create(property=immobile, nome="IMU", codice="imu")
    e = Expense.objects.create(
        property=immobile,
        data=datetime.date(2025, 6, 16),
        category=cat,
        importo=Decimal("1200"),
        descrizione="IMU 2025 acconto",
        anticipata_da_owner=esterno,
    )
    at = datetime.date(2025, 6, 30)
    saldi = calcola_saldi_correnti(immobile, at)
    q = verifica_quadratura(immobile, at, saldi)
    assert q.quadra is False
    assert q.somma_saldi == Decimal("-1200.00")
    assert [o["id"] for o in q.expense_orfane] == [e.pk]


# ---------------------------------------------------------------------------
# Piano di rientro
# ---------------------------------------------------------------------------


def test_piano_rientro_saldi_zero_vuoto(db, immobile, quote_terzi):
    saldi = calcola_saldi_correnti(immobile, datetime.date(2025, 6, 30))
    assert calcola_piano_rientro(saldi) == []


def test_piano_rientro_un_debitore_due_creditori(db, immobile, quote_terzi, sandro, bruna, fabio, assignment):
    """Bruna incassa 400: deve 200 a Sandro e 100 a Fabio (max creditore prima)."""
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
    saldi = calcola_saldi_correnti(immobile, datetime.date(2025, 6, 30))
    piano = calcola_piano_rientro(saldi)
    assert [(v["da"], v["a"], v["importo"]) for v in piano] == [
        (bruna, sandro, Decimal("200.00")),
        (bruna, fabio, Decimal("100.00")),
    ]


def test_piano_rientro_compensa_flussi_incrociati(db, immobile, quote_terzi, sandro, bruna, fabio, assignment):
    """Incasso di Bruna (400) + spesa anticipata da Bruna (1200): saldi netti
    Bruna +600, Sandro -400, Fabio -200 → due bonifici verso Bruna."""
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
    cat = ExpenseCategory.objects.create(property=immobile, nome="IMU", codice="imu")
    Expense.objects.create(
        property=immobile,
        data=datetime.date(2025, 6, 16),
        category=cat,
        importo=Decimal("1200"),
        descrizione="IMU 2025 acconto",
        anticipata_da_owner=bruna,
    )
    saldi = calcola_saldi_correnti(immobile, datetime.date(2025, 6, 30))
    assert saldi[bruna].totale == Decimal("600.00")
    assert saldi[sandro].totale == Decimal("-400.00")
    assert saldi[fabio].totale == Decimal("-200.00")
    piano = calcola_piano_rientro(saldi)
    assert [(v["da"], v["a"], v["importo"]) for v in piano] == [
        (sandro, bruna, Decimal("400.00")),
        (fabio, bruna, Decimal("200.00")),
    ]


def test_endpoint_trasferimento_crea_bt_e_marcatura(
    db, client, immobile, quote_terzi, sandro, bruna, fabio, conto_bruna, assignment,
):
    """Un bonifico fra proprietari si registra in un gesto solo dal frontend."""
    from django.contrib.auth.models import Group
    from properties.models import PropertyMembership

    gruppo, _ = Group.objects.get_or_create(name="proprietari")
    for owner in (sandro, bruna, fabio):
        PropertyMembership.objects.get_or_create(
            property=immobile, user=owner.user, defaults={"ruolo": "proprietario"},
        )
        owner.user.groups.add(gruppo)
    conto_bruna.properties.add(immobile)
    client.force_login(bruna.user)

    r = client.post(
        "/api/v1/owner-ledger/trasferimento/",
        data={
            "owner_account": conto_bruna.pk,
            "controparte_owner": fabio.pk,
            "importo": "300.00",
            "data": "2025-05-20",
            "direzione": "uscita",
            "descrizione": "Quota parte affitto",
        },
        content_type="application/json",
    )
    assert r.status_code == 201, r.content
    bt = BankTransaction.objects.get(pk=r.json()["bank_transaction"])
    assert bt.importo == Decimal("-300.00")
    assert bt.owner_account == conto_bruna
    voci = {v.owner: v.importo for v in bt.ledger_entries.all()}
    # Chi paga risale, chi incassa scende: cfr. bt_inter_owner.
    assert voci[bruna] == Decimal("300.00")
    assert voci[fabio] == Decimal("-300.00")


def test_endpoint_trasferimento_rifiuta_se_stesso(
    db, client, immobile, quote_terzi, bruna, conto_bruna,
):
    from django.contrib.auth.models import Group
    from properties.models import PropertyMembership

    PropertyMembership.objects.get_or_create(
        property=immobile, user=bruna.user, defaults={"ruolo": "proprietario"},
    )
    gruppo, _ = Group.objects.get_or_create(name="proprietari")
    bruna.user.groups.add(gruppo)
    conto_bruna.properties.add(immobile)
    client.force_login(bruna.user)
    r = client.post(
        "/api/v1/owner-ledger/trasferimento/",
        data={
            "owner_account": conto_bruna.pk,
            "controparte_owner": bruna.pk,
            "importo": "50.00",
            "data": "2025-05-20",
        },
        content_type="application/json",
    )
    assert r.status_code == 400
    assert BankTransaction.objects.filter(owner_account=conto_bruna).count() == 0


def test_endpoint_modifica_marcatura(
    db, client, immobile, quote_terzi, sandro, bruna, fabio, conto_bruna,
):
    """Causale e tipologia di un movimento già registrato si correggono."""
    from django.contrib.auth.models import Group
    from properties.models import PropertyMembership

    gruppo, _ = Group.objects.get_or_create(name="proprietari")
    for owner in (sandro, bruna, fabio):
        PropertyMembership.objects.get_or_create(
            property=immobile, user=owner.user, defaults={"ruolo": "proprietario"},
        )
        owner.user.groups.add(gruppo)
    conto_bruna.properties.add(immobile)
    client.force_login(bruna.user)

    creata = client.post(
        "/api/v1/owner-ledger/trasferimento/",
        data={
            "owner_account": conto_bruna.pk,
            "controparte_owner": fabio.pk,
            "importo": "1707.00",
            "data": "2026-02-02",
            "descrizione": "Bonifico",
        },
        content_type="application/json",
    )
    assert creata.status_code == 201, creata.content
    bt_id = creata.json()["bank_transaction"]

    r = client.patch(
        f"/api/v1/owner-ledger/bt-inter-owner/{bt_id}/",
        data={
            "tipo": "incasso_conguaglio",
            "controparte_owner": sandro.pk,
            "descrizione": "Conguaglio 2025",
        },
        content_type="application/json",
    )
    assert r.status_code == 200, r.content
    bt = BankTransaction.objects.get(pk=bt_id)
    assert bt.descrizione == "Conguaglio 2025"
    voci = {v.owner: v for v in bt.ledger_entries.all()}
    assert set(voci) == {bruna, sandro}          # la controparte è cambiata
    assert voci[bruna].tipo == OwnerLedgerEntry.TipoVoce.INCASSO_CONGUAGLIO
    assert voci[bruna].importo == Decimal("1707.00")
    assert voci[sandro].importo == Decimal("-1707.00")
    # L'importo resta quello della banca: non è modificabile da qui.
    assert bt.importo == Decimal("-1707.00")


def test_anno_competenza_sposta_il_movimento_di_periodo(
    db, client, immobile, quote_terzi, sandro, bruna, fabio, conto_bruna,
):
    """Il bonifico di gennaio dichiarato dell'anno prima appartiene a quello.

    Il totale non cambia mai — la competenza dice a quale periodo il
    movimento appartiene, non quanto vale — ma la chiusura del 2024 se lo
    porta dentro invece di lasciarlo al periodo aperto.
    """
    import datetime as dt

    from accounting.services.settlement import genera_settlement
    from django.contrib.auth.models import Group
    from properties.models import PropertyMembership

    gruppo, _ = Group.objects.get_or_create(name="proprietari")
    for owner in (sandro, bruna, fabio):
        PropertyMembership.objects.get_or_create(
            property=immobile, user=owner.user, defaults={"ruolo": "proprietario"},
        )
        owner.user.groups.add(gruppo)
    conto_bruna.properties.add(immobile)
    client.force_login(bruna.user)

    r = client.post(
        "/api/v1/owner-ledger/trasferimento/",
        data={
            "owner_account": conto_bruna.pk,
            "controparte_owner": fabio.pk,
            "importo": "400.00",
            "data": "2025-01-13",
            "anno_competenza": 2024,
            "descrizione": "Quota di dicembre",
        },
        content_type="application/json",
    )
    assert r.status_code == 201, r.content
    bt = BankTransaction.objects.get(pk=r.json()["bank_transaction"])
    assert bt.data_competenza == dt.date(2024, 12, 31)

    al = dt.date(2025, 6, 30)
    prima = calcola_saldi_correnti(immobile, al)
    assert prima[fabio].totale == Decimal("-400.00")

    genera_settlement(immobile, dt.date(2024, 1, 1), dt.date(2024, 12, 31))
    dopo = calcola_saldi_correnti(immobile, al)
    # Stessa posizione, ma ora è la baseline a portarla: il periodo aperto
    # comincia dal 2025 e quel bonifico non ci appartiene più.
    assert dopo[fabio].totale == prima[fabio].totale
    assert dopo[fabio].baseline_settlement == Decimal("-400.00")
    assert dopo[fabio].bt_inter_owner == Decimal("0")


def test_anno_competenza_uguale_alla_data_non_si_dichiara(
    db, client, immobile, quote_terzi, sandro, bruna, fabio, conto_bruna,
):
    """Dichiarare l'anno in cui il bonifico è stato fatto non scrive nulla."""
    from django.contrib.auth.models import Group
    from properties.models import PropertyMembership

    gruppo, _ = Group.objects.get_or_create(name="proprietari")
    for owner in (sandro, bruna, fabio):
        PropertyMembership.objects.get_or_create(
            property=immobile, user=owner.user, defaults={"ruolo": "proprietario"},
        )
        owner.user.groups.add(gruppo)
    conto_bruna.properties.add(immobile)
    client.force_login(bruna.user)

    r = client.post(
        "/api/v1/owner-ledger/trasferimento/",
        data={
            "owner_account": conto_bruna.pk,
            "controparte_owner": fabio.pk,
            "importo": "300.00",
            "data": "2025-03-02",
            "anno_competenza": 2025,
        },
        content_type="application/json",
    )
    assert r.status_code == 201, r.content
    bt = BankTransaction.objects.get(pk=r.json()["bank_transaction"])
    assert bt.data_competenza is None


def test_anno_competenza_di_una_partita_privata_si_rilegge(
    db, client, immobile, quote_terzi, sandro, bruna, fabio, conto_bruna,
):
    """Il giro completo che non funzionava: dichiarare l'anno e ritrovarlo.

    Per una partita bilaterale non esistono voci di libro mastro, quindi
    finché l'anno stava lì veniva accettato e perso in silenzio.
    """
    import datetime as dt

    from django.contrib.auth.models import Group
    from properties.models import PropertyMembership

    gruppo, _ = Group.objects.get_or_create(name="proprietari")
    for owner in (sandro, bruna, fabio):
        PropertyMembership.objects.get_or_create(
            property=immobile, user=owner.user, defaults={"ruolo": "proprietario"},
        )
        owner.user.groups.add(gruppo)
    conto_bruna.properties.add(immobile)
    client.force_login(bruna.user)

    creata = client.post(
        "/api/v1/owner-ledger/trasferimento/",
        data={
            "owner_account": conto_bruna.pk,
            "controparte_owner": sandro.pk,
            "importo": "1707.00",
            "data": "2026-02-02",
            "descrizione": "Pareggio dei conti",
        },
        content_type="application/json",
    )
    assert creata.status_code == 201, creata.content
    bt_id = creata.json()["bank_transaction"]

    r = client.patch(
        f"/api/v1/owner-ledger/bt-inter-owner/{bt_id}/",
        data={
            "tipo": "bilaterale",
            "controparte_owner": sandro.pk,
            "anno_competenza": 2025,
            "descrizione": "Pareggio dei conti 2025",
        },
        content_type="application/json",
    )
    assert r.status_code == 200, r.content
    assert BankTransaction.objects.get(pk=bt_id).data_competenza == dt.date(2025, 12, 31)

    riletta = client.get("/api/v1/inter-owner-entries/").json()
    voci = riletta["results"] if isinstance(riletta, dict) else riletta
    nostra = [v for v in voci if v["bank_transaction"] == bt_id]
    assert len(nostra) == 1
    assert nostra[0]["anno_competenza"] == 2025
