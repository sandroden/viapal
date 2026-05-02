"""
Test per calcola_conguaglio_periodo (billing/calc/utility.py).

Coprono:
- Caso base: 5 inquilini presenti tutto il mese, totale 250€ -> ognuno 50€
- Inquilino entrato a meta' mese: pagamento proporzionale
- Stanza vuota per parte del periodo (sum_giorni < 5*giorni_mese)
- TARI pro-rata 30 giorni
- manual_totals (bypass bollette)
- Conservazione: somma quote + diff == totale
- persist=True crea UtilityCharge
- Idempotenza: ricalcolo non duplica
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from billing.models import (
    AnnualUtilityCost,
    Supplier,
    UtilityBill,
    UtilityCharge,
    UtilityChargeLine,
    UtilityChargePeriod,
)
from properties.models import OwnerProfile, Room, RoomAssignment, TenantProfile


# ---------------------------------------------------------------------------
# Fixtures condivise
# ---------------------------------------------------------------------------


@pytest.fixture
def owner_user(db):
    return User.objects.create_user("owner_calc", email="owner_calc@v.it", password="pwd")


@pytest.fixture
def owner(db, owner_user):
    return OwnerProfile.objects.create(user=owner_user, nominativo="Owner Calc")


@pytest.fixture
def make_tenant(db):
    """Factory che crea un TenantProfile con User dedicato."""
    counter = [0]

    def _make(nominativo="Inquilino", giorno_pagamento=1):
        counter[0] += 1
        u = User.objects.create_user(
            username=f"tenant_calc_{counter[0]}",
            email=f"tenant_calc_{counter[0]}@v.it",
            password="pwd",
        )
        return TenantProfile.objects.create(
            user=u,
            nominativo=nominativo,
            giorno_pagamento_affitto=giorno_pagamento,
        )

    return _make


@pytest.fixture
def make_room(db):
    """Factory che crea una Room."""
    counter = [0]

    def _make(nome=None):
        counter[0] += 1
        return Room.objects.create(
            nome=nome or f"Camera Calc {counter[0]}",
            ordinamento=counter[0],
        )

    return _make


@pytest.fixture
def make_assignment(db, make_room, make_tenant):
    """Factory che crea un RoomAssignment con stanza e tenant propri."""

    def _make(
        canone=Decimal("500.00"),
        valid_from=datetime.date(2026, 5, 1),
        valid_to=None,
        tenant=None,
        room=None,
    ):
        t = tenant or make_tenant(nominativo=f"T_{valid_from}")
        r = room or make_room()
        return RoomAssignment.objects.create(
            room=r,
            tenant=t,
            valid_from=valid_from,
            valid_to=valid_to,
            canone_mensile=canone,
            deposito_versato=canone,
        )

    return _make


@pytest.fixture
def periodo_maggio(db):
    """UtilityChargePeriod per maggio 2026 (31 giorni)."""
    return UtilityChargePeriod.objects.create(
        periodo_da=datetime.date(2026, 5, 1),
        periodo_a=datetime.date(2026, 5, 31),
        criterio_ripartizione="pro_rata_giorni",
        data_invio=datetime.date(2026, 6, 1),
    )


@pytest.fixture
def supplier_luce(db, owner):
    return Supplier.objects.create(nome="Enel Test", tipo="energia")


@pytest.fixture
def supplier_gas(db, owner):
    return Supplier.objects.create(nome="Eni Test", tipo="gas")


# ---------------------------------------------------------------------------
# Caso base: 5 inquilini tutto il mese, 250€ totale -> 50€ ciascuno
# ---------------------------------------------------------------------------


class TestCasoBase5Inquilini:
    """5 inquilini presenti per l'intero mese, totale 250€ -> 50€ ciascuno."""

    @pytest.fixture
    def setup_5_inquilini(self, db, make_assignment, periodo_maggio, supplier_luce, owner):
        """Crea 5 assignment per tutto maggio e una bolletta luce da 250€."""
        assignments = [
            make_assignment(
                canone=Decimal("400.00"),
                valid_from=datetime.date(2026, 5, 1),
            )
            for _ in range(5)
        ]
        # Bolletta luce da 250€ emessa nel periodo
        UtilityBill.objects.create(
            supplier=supplier_luce,
            numero_fattura="ENEL-TEST-BASE",
            data_emissione=datetime.date(2026, 5, 15),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("250.00"),
            pagata_da_owner=owner,
        )
        return assignments, periodo_maggio

    def test_quota_uguale_per_tutti(self, setup_5_inquilini):
        from billing.calc.utility import calcola_conguaglio_periodo

        assignments, period = setup_5_inquilini
        risultato = calcola_conguaglio_periodo(period.pk)

        assert len(risultato["quote"]) == 5
        for q in risultato["quote"]:
            assert q["quota"] == Decimal("50.00"), (
                f"Quota attesa 50.00, trovata {q['quota']} per {q['tenant_nominativo']}"
            )

    def test_totale_periodo(self, setup_5_inquilini):
        from billing.calc.utility import calcola_conguaglio_periodo

        assignments, period = setup_5_inquilini
        risultato = calcola_conguaglio_periodo(period.pk)

        assert risultato["totale_periodo"] == Decimal("250.00")

    def test_sum_giorni_presenza(self, setup_5_inquilini):
        from billing.calc.utility import calcola_conguaglio_periodo

        assignments, period = setup_5_inquilini
        risultato = calcola_conguaglio_periodo(period.pk)

        # 5 inquilini * 31 giorni
        assert risultato["sum_giorni_presenza"] == 5 * 31


# ---------------------------------------------------------------------------
# Inquilino entrato a meta' mese
# ---------------------------------------------------------------------------


class TestInquilinoParziale:
    """1 inquilino entra il 15 maggio (17 giorni su 31), 4 presenti tutto il mese."""

    @pytest.fixture
    def setup_parziale(self, db, make_assignment, periodo_maggio, supplier_luce, owner):
        # 4 inquilini da inizio mese
        full_month = [
            make_assignment(
                canone=Decimal("400.00"),
                valid_from=datetime.date(2026, 5, 1),
            )
            for _ in range(4)
        ]
        # 1 inquilino dal 15 maggio (17 giorni: 15,16,...,31)
        partial = make_assignment(
            canone=Decimal("400.00"),
            valid_from=datetime.date(2026, 5, 15),
        )
        # Bolletta luce 155€
        UtilityBill.objects.create(
            supplier=supplier_luce,
            numero_fattura="ENEL-TEST-PARZ",
            data_emissione=datetime.date(2026, 5, 15),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("155.00"),
            pagata_da_owner=owner,
        )
        return full_month, partial, periodo_maggio

    def test_parziale_paga_meno(self, setup_parziale):
        from billing.calc.utility import calcola_conguaglio_periodo

        full_month, partial, period = setup_parziale
        risultato = calcola_conguaglio_periodo(period.pk)

        assert len(risultato["quote"]) == 5

        quote_by_id = {q["assignment_id"]: q for q in risultato["quote"]}
        quota_partial = quote_by_id[partial.pk]["quota"]
        giorni_partial = quote_by_id[partial.pk]["giorni_presenza"]

        assert giorni_partial == 17  # 15-31 maggio inclusi

        # Il parziale deve pagare meno degli interi
        for a in full_month:
            assert quote_by_id[a.pk]["quota"] > quota_partial, (
                "Il parziale dovrebbe pagare meno dei presenti tutto il mese"
            )

    def test_proporzione_corretta(self, setup_parziale):
        from billing.calc.utility import calcola_conguaglio_periodo

        full_month, partial, period = setup_parziale
        risultato = calcola_conguaglio_periodo(period.pk)

        quote_by_id = {q["assignment_id"]: q for q in risultato["quote"]}
        # sum_giorni = 4*31 + 1*17 = 141
        assert risultato["sum_giorni_presenza"] == 4 * 31 + 17

    def test_conservazione(self, setup_parziale):
        from billing.calc.utility import calcola_conguaglio_periodo

        full_month, partial, period = setup_parziale
        risultato = calcola_conguaglio_periodo(period.pk)

        somma_quote = sum(q["quota"] for q in risultato["quote"])
        diff = risultato["diff_arrotondamento"]
        # somma + diff deve essere uguale al totale originale (entro arrotondamento)
        assert abs(somma_quote + diff - risultato["totale_periodo"]) <= Decimal("0.05")


# ---------------------------------------------------------------------------
# Stanza vuota per parte del periodo
# ---------------------------------------------------------------------------


class TestStanzaVuota:
    """Solo 3 inquilini attivi (2 stanze vuote) -> sum_giorni < 5*31."""

    @pytest.fixture
    def setup_vuote(self, db, make_assignment, periodo_maggio, supplier_luce, owner):
        # Solo 3 inquilini per tutto il mese
        assignments = [
            make_assignment(
                canone=Decimal("400.00"),
                valid_from=datetime.date(2026, 5, 1),
            )
            for _ in range(3)
        ]
        UtilityBill.objects.create(
            supplier=supplier_luce,
            numero_fattura="ENEL-TEST-VUOTE",
            data_emissione=datetime.date(2026, 5, 10),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("90.00"),
            pagata_da_owner=owner,
        )
        return assignments, periodo_maggio

    def test_sum_giorni_solo_attivi(self, setup_vuote):
        from billing.calc.utility import calcola_conguaglio_periodo

        assignments, period = setup_vuote
        risultato = calcola_conguaglio_periodo(period.pk)

        assert risultato["sum_giorni_presenza"] == 3 * 31
        assert len(risultato["quote"]) == 3

    def test_quota_maggiore_con_meno_inquilini(self, setup_vuote):
        """Con 3 inquilini anziche' 5, la quota di ciascuno e' maggiore."""
        from billing.calc.utility import calcola_conguaglio_periodo

        assignments, period = setup_vuote
        risultato = calcola_conguaglio_periodo(period.pk)

        # 90€ / 3 = 30€ ciascuno
        for q in risultato["quote"]:
            assert q["quota"] == Decimal("30.00")


# ---------------------------------------------------------------------------
# TARI pro-rata
# ---------------------------------------------------------------------------


class TestTARIProRata:
    """TARI 510€/anno, periodo 30 giorni -> 510/365*30 ≈ 41.92€ totale."""

    @pytest.fixture
    def setup_tari(self, db, make_assignment, owner):
        """Periodo di 30 giorni (giugno), TARI 510€/anno, 2 inquilini."""
        period = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2026, 6, 1),
            periodo_a=datetime.date(2026, 6, 30),
            criterio_ripartizione="pro_rata_giorni",
        )
        # TARI valida tutto l'anno
        AnnualUtilityCost.objects.create(
            voce="tari",
            anno=2026,
            importo_annuale=Decimal("510.00"),
            valid_from=datetime.date(2026, 1, 1),
        )
        # 2 assignment attivi tutto giugno
        a1 = make_assignment(valid_from=datetime.date(2026, 6, 1))
        a2 = make_assignment(valid_from=datetime.date(2026, 6, 1))
        return period, a1, a2

    def test_totale_tari_30_giorni(self, setup_tari):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, a1, a2 = setup_tari
        risultato = calcola_conguaglio_periodo(period.pk)

        # 510 * 30 / 365 = 41.917... -> arrotondato dalla somma delle quote
        totale_tari = risultato["totali_per_voce"].get("tari", Decimal("0.00"))
        # Valore atteso: Decimal("510.00") * 30 / 365 = ~41.92
        from decimal import ROUND_HALF_UP
        atteso = (Decimal("510.00") * Decimal(30) / Decimal(365)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert totale_tari == atteso, f"TARI atteso {atteso}, trovato {totale_tari}"

    def test_tari_distribuita_equamente(self, setup_tari):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, a1, a2 = setup_tari
        risultato = calcola_conguaglio_periodo(period.pk)

        assert len(risultato["quote"]) == 2
        # Entrambi presenti 30 giorni -> stessa quota
        quote_vals = [q["dettaglio"].get("tari", Decimal("0")) for q in risultato["quote"]]
        assert quote_vals[0] == quote_vals[1]


# ---------------------------------------------------------------------------
# manual_totals (bypass bollette)
# ---------------------------------------------------------------------------


class TestManualTotals:
    """Se manual_totals e' presente, bypass delle bollette e AnnualUtilityCost."""

    @pytest.fixture
    def setup_manual(self, db, make_assignment, supplier_luce, owner):
        # Bolletta presente ma deve essere ignorata
        UtilityBill.objects.create(
            supplier=supplier_luce,
            numero_fattura="ENEL-TEST-MANUAL",
            data_emissione=datetime.date(2026, 5, 15),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("999.00"),  # valore irrealistico -> deve essere ignorato
            pagata_da_owner=owner,
        )
        # Period con manual_totals espliciti
        period = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            criterio_ripartizione="pro_rata_giorni",
            manual_totals={"luce": "100.00", "gas": "60.00"},
        )
        # 2 inquilini per tutto il mese
        a1 = make_assignment(valid_from=datetime.date(2026, 5, 1))
        a2 = make_assignment(valid_from=datetime.date(2026, 5, 1))
        return period, a1, a2

    def test_usa_manual_totals(self, setup_manual):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, a1, a2 = setup_manual
        risultato = calcola_conguaglio_periodo(period.pk)

        # Totale deve essere 100+60=160, non 999
        assert risultato["totale_periodo"] == Decimal("160.00")
        assert risultato["totali_per_voce"]["luce"] == Decimal("100.00")
        assert risultato["totali_per_voce"]["gas"] == Decimal("60.00")

    def test_quota_dimezzata_tra_due(self, setup_manual):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, a1, a2 = setup_manual
        risultato = calcola_conguaglio_periodo(period.pk)

        # 160€ / 2 = 80€ ciascuno
        for q in risultato["quote"]:
            assert q["quota"] == Decimal("80.00")


# ---------------------------------------------------------------------------
# Conservazione: somma quote + diff == totale (entro 0.05€)
# ---------------------------------------------------------------------------


class TestConservazione:
    """Verifica che somma(quote) + diff_arrotondamento == totale_periodo."""

    @pytest.fixture
    def setup_conservazione(self, db, make_assignment, supplier_luce, supplier_gas, owner):
        """Totale volutamente non divisibile esattamente (per avere diff reale)."""
        period = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
        )
        # 3 bollette di importi irregolari
        UtilityBill.objects.create(
            supplier=supplier_luce,
            numero_fattura="ENEL-CONS-1",
            data_emissione=datetime.date(2026, 5, 10),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("103.37"),
            pagata_da_owner=owner,
        )
        UtilityBill.objects.create(
            supplier=supplier_gas,
            numero_fattura="ENI-CONS-1",
            data_emissione=datetime.date(2026, 5, 10),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("77.13"),
            pagata_da_owner=owner,
        )
        # 3 inquilini con giorni diversi (non divisibili)
        a1 = make_assignment(valid_from=datetime.date(2026, 5, 1))
        a2 = make_assignment(valid_from=datetime.date(2026, 5, 8))   # 24 giorni
        a3 = make_assignment(valid_from=datetime.date(2026, 5, 20))  # 12 giorni
        return period

    def test_conservazione_somma(self, setup_conservazione):
        from billing.calc.utility import calcola_conguaglio_periodo

        period = setup_conservazione
        risultato = calcola_conguaglio_periodo(period.pk)

        somma_quote = sum(q["quota"] for q in risultato["quote"])
        diff = risultato["diff_arrotondamento"]
        totale = risultato["totale_periodo"]

        assert abs(somma_quote + diff - totale) <= Decimal("0.05"), (
            f"Conservazione fallita: {somma_quote} + {diff} != {totale}"
        )


# ---------------------------------------------------------------------------
# persist=True crea UtilityCharge
# ---------------------------------------------------------------------------


class TestPersist:
    """persist=True deve creare UtilityCharge e UtilityChargeLine."""

    @pytest.fixture
    def setup_persist(self, db, make_assignment, supplier_luce, owner):
        period = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            data_invio=datetime.date(2026, 6, 1),
        )
        UtilityBill.objects.create(
            supplier=supplier_luce,
            numero_fattura="ENEL-PERSIST-1",
            data_emissione=datetime.date(2026, 5, 15),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("100.00"),
            pagata_da_owner=owner,
        )
        a1 = make_assignment(valid_from=datetime.date(2026, 5, 1))
        a2 = make_assignment(valid_from=datetime.date(2026, 5, 1))
        return period, [a1, a2]

    def test_crea_utility_charge(self, setup_persist):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, assignments = setup_persist
        calcola_conguaglio_periodo(period.pk, persist=True)

        charges = UtilityCharge.objects.filter(period=period)
        assert charges.count() == 2

    def test_crea_charge_lines(self, setup_persist):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, assignments = setup_persist
        calcola_conguaglio_periodo(period.pk, persist=True)

        # 2 charge * 1 voce (luce) = 2 lines
        lines_count = UtilityChargeLine.objects.filter(charge__period=period).count()
        assert lines_count == 2

    def test_importo_charge_uguale_quota(self, setup_persist):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, assignments = setup_persist
        risultato = calcola_conguaglio_periodo(period.pk, persist=True)

        for q in risultato["quote"]:
            charge = UtilityCharge.objects.get(period=period, assignment_id=q["assignment_id"])
            assert charge.importo_totale == q["quota"]


# ---------------------------------------------------------------------------
# Idempotenza: ricalcolo non duplica
# ---------------------------------------------------------------------------


class TestIdempotenza:
    """Ricalcolo con persist=True non duplica UtilityCharge o UtilityChargeLine."""

    @pytest.fixture
    def setup_idempotenza(self, db, make_assignment, supplier_luce, owner):
        period = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            data_invio=datetime.date(2026, 6, 1),
        )
        UtilityBill.objects.create(
            supplier=supplier_luce,
            numero_fattura="ENEL-IDEM-1",
            data_emissione=datetime.date(2026, 5, 15),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("200.00"),
            pagata_da_owner=owner,
        )
        a1 = make_assignment(valid_from=datetime.date(2026, 5, 1))
        a2 = make_assignment(valid_from=datetime.date(2026, 5, 1))
        return period, [a1, a2]

    def test_non_duplica(self, setup_idempotenza):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, assignments = setup_idempotenza

        # Prima chiamata
        calcola_conguaglio_periodo(period.pk, persist=True)
        count_after_first = UtilityCharge.objects.filter(period=period).count()

        # Seconda chiamata: non deve duplicare
        calcola_conguaglio_periodo(period.pk, persist=True)
        count_after_second = UtilityCharge.objects.filter(period=period).count()

        assert count_after_first == count_after_second == 2

    def test_lines_non_duplicate(self, setup_idempotenza):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, assignments = setup_idempotenza

        calcola_conguaglio_periodo(period.pk, persist=True)
        lines_after_first = UtilityChargeLine.objects.filter(charge__period=period).count()

        calcola_conguaglio_periodo(period.pk, persist=True)
        lines_after_second = UtilityChargeLine.objects.filter(charge__period=period).count()

        assert lines_after_first == lines_after_second
