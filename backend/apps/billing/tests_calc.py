"""
Test per calcola_conguaglio_periodo (billing/calc/utility.py).

Coprono:
- Caso base: 5 inquilini presenti tutto il mese, totale 250€ -> ognuno 50€
- Inquilino entrato a meta' mese: pagamento proporzionale
- Stanza vuota per parte del periodo (sum_giorni < 5*giorni_mese)
- TARI pro-rata 30 giorni
- Conservazione: somma quote + diff == totale
- persist=True crea Receivable + popola totali sul Period
- Idempotenza: ricalcolo non duplica
"""
import calendar
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from billing.models import (
    AnnualUtilityCost,
    BankTransaction,
    BankTransactionAllocation,
    Receivable,
    Supplier,
    UtilityBill,
    UtilityChargePeriod,
)
from properties.models import OwnerBankAccount, OwnerProfile, Room, RoomAssignment, TenantProfile


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
    """TARI 510€/anno; un solo periodo attivo nell'anno → tutta la TARI annua
    viene caricata su quel periodo (denominatore = giorni dei periodi attivi).
    """

    @pytest.fixture
    def setup_tari(self, db, make_assignment, supplier_luce, owner):
        """Periodo di 30 giorni (giugno), TARI 510€/anno, 2 inquilini."""
        period = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2026, 6, 1),
            periodo_a=datetime.date(2026, 6, 30),
            criterio_ripartizione="pro_rata_giorni",
        )
        AnnualUtilityCost.objects.create(
            voce="tari",
            anno=2026,
            importo_annuale=Decimal("510.00"),
            valid_from=datetime.date(2026, 1, 1),
            valid_to=datetime.date(2026, 12, 31),
        )
        # Bolletta luce nel periodo: senza, il calcolo skippa per regola
        # "no bollette luce/gas → no Receivable" (commit 10554e5).
        UtilityBill.objects.create(
            supplier=supplier_luce,
            numero_fattura="ENEL-TARI-1",
            data_emissione=datetime.date(2026, 6, 15),
            periodo_da=datetime.date(2026, 6, 1),
            periodo_a=datetime.date(2026, 6, 30),
            importo_totale=Decimal("100.00"),
            pagata_da_owner=owner,
        )
        a1 = make_assignment(valid_from=datetime.date(2026, 6, 1))
        a2 = make_assignment(valid_from=datetime.date(2026, 6, 1))
        return period, a1, a2

    def test_totale_tari_unico_periodo_attivo(self, setup_tari):
        """Un solo periodo attivo → la TARI annua va tutta su quel periodo."""
        from billing.calc.utility import calcola_conguaglio_periodo

        period, a1, a2 = setup_tari
        risultato = calcola_conguaglio_periodo(period.pk)

        totale_tari = risultato["totali_per_voce"].get("tari", Decimal("0.00"))
        # 510 × 30 / 30 = 510 (tutto sul singolo periodo attivo)
        assert totale_tari == Decimal("510.00"), (
            f"TARI atteso 510.00, trovato {totale_tari}"
        )

    def test_tari_distribuita_equamente(self, setup_tari):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, a1, a2 = setup_tari
        risultato = calcola_conguaglio_periodo(period.pk)

        assert len(risultato["quote"]) == 2
        quote_vals = [q["dettaglio"].get("tari", Decimal("0")) for q in risultato["quote"]]
        assert quote_vals[0] == quote_vals[1]


# ---------------------------------------------------------------------------
# TARI distribuzione su periodi multipli nell'anno
# ---------------------------------------------------------------------------


class TestTARIDistribuzioneAnnua:
    """La TARI annua si distribuisce sui ``UtilityChargePeriod`` con bollette
    luce/gas, proporzionalmente ai loro giorni. La cadenza dei periodi
    (mensile / bimestrale / mix) è gestita automaticamente dal denominatore
    (= somma giorni periodi attivi)."""

    def _crea_periodo_con_bolletta(self, periodo_da, periodo_a, supplier_luce, owner, n=1):
        period = UtilityChargePeriod.objects.create(
            periodo_da=periodo_da,
            periodo_a=periodo_a,
            criterio_ripartizione="pro_rata_giorni",
        )
        UtilityBill.objects.create(
            supplier=supplier_luce,
            numero_fattura=f"ENEL-DISTR-{periodo_da}-{n}",
            data_emissione=periodo_da + datetime.timedelta(days=10),
            periodo_da=periodo_da,
            periodo_a=periodo_a,
            importo_totale=Decimal("50.00"),
            pagata_da_owner=owner,
        )
        return period

    def test_12_periodi_mensili_un_dodicesimo_ciascuno(
        self, db, make_assignment, supplier_luce, owner
    ):
        """12 periodi mensili → ogni periodo riceve circa 1/12 della TARI annua."""
        from billing.calc.utility import calcola_conguaglio_periodo

        AnnualUtilityCost.objects.create(
            voce="tari",
            anno=2026,
            importo_annuale=Decimal("1200.00"),
            valid_from=datetime.date(2026, 1, 1),
            valid_to=datetime.date(2026, 12, 31),
        )
        periodi = []
        for mese in range(1, 13):
            ultimo = calendar.monthrange(2026, mese)[1]
            p = self._crea_periodo_con_bolletta(
                datetime.date(2026, mese, 1),
                datetime.date(2026, mese, ultimo),
                supplier_luce, owner, n=mese,
            )
            periodi.append(p)
        # Almeno un assignment per coprire tutto l'anno
        make_assignment(valid_from=datetime.date(2026, 1, 1))

        # Verifica giugno (30 gg): TARI = 1200 × 30 / 365 = 98.63
        ris_giu = calcola_conguaglio_periodo(periodi[5].pk)
        assert ris_giu["totali_per_voce"]["tari"] == Decimal("98.63")
        # Verifica luglio (31 gg): TARI = 1200 × 31 / 365 = 101.92
        ris_lug = calcola_conguaglio_periodo(periodi[6].pk)
        assert ris_lug["totali_per_voce"]["tari"] == Decimal("101.92")

        # Somma su tutti i 12 periodi ≈ 1200 (entro arrotondamenti)
        somma = sum(
            calcola_conguaglio_periodo(p.pk)["totali_per_voce"].get("tari", Decimal("0"))
            for p in periodi
        )
        assert abs(somma - Decimal("1200.00")) <= Decimal("0.05"), (
            f"Somma TARI sui 12 periodi attesa ~1200, trovata {somma}"
        )

    def test_6_periodi_bimestrali_un_sesto_ciascuno(
        self, db, make_assignment, supplier_luce, owner
    ):
        """6 periodi bimestrali → ogni periodo riceve circa 1/6 della TARI."""
        from billing.calc.utility import calcola_conguaglio_periodo

        AnnualUtilityCost.objects.create(
            voce="tari",
            anno=2024,
            importo_annuale=Decimal("450.00"),
            valid_from=datetime.date(2024, 1, 1),
            valid_to=datetime.date(2024, 12, 31),
        )
        bimestri = [
            (datetime.date(2024, 1, 1), datetime.date(2024, 2, 29)),  # 60 gg
            (datetime.date(2024, 3, 1), datetime.date(2024, 4, 30)),  # 61
            (datetime.date(2024, 5, 1), datetime.date(2024, 6, 30)),  # 61
            (datetime.date(2024, 7, 1), datetime.date(2024, 8, 31)),  # 62
            (datetime.date(2024, 9, 1), datetime.date(2024, 10, 31)),  # 61
            (datetime.date(2024, 11, 1), datetime.date(2024, 12, 31)),  # 61
        ]
        periodi = [
            self._crea_periodo_con_bolletta(da, a, supplier_luce, owner, n=i)
            for i, (da, a) in enumerate(bimestri)
        ]
        make_assignment(valid_from=datetime.date(2024, 1, 1))

        # Ogni bimestre: 450 × giorni / 366 (anno bisestile, sum=366)
        # Nota: sum_giorni_attivi = 60+61+61+62+61+61 = 366
        ris_genfeb = calcola_conguaglio_periodo(periodi[0].pk)
        assert ris_genfeb["totali_per_voce"]["tari"] == Decimal("73.77"), (
            f"trovato {ris_genfeb['totali_per_voce']['tari']}"
        )

        # Somma totale ≈ 450 (l'anno è coperto interamente dai 6 bimestri)
        somma = sum(
            calcola_conguaglio_periodo(p.pk)["totali_per_voce"].get("tari", Decimal("0"))
            for p in periodi
        )
        assert abs(somma - Decimal("450.00")) <= Decimal("0.05"), (
            f"Somma TARI sui 6 bimestri attesa ~450, trovata {somma}"
        )

    def test_mix_bimestrali_e_mensili(
        self, db, make_assignment, supplier_luce, owner
    ):
        """Mix: 2 bimestrali (gen-apr) + 8 mensili (mag-dic). Distribuzione
        proporzionale ai giorni. Un bimestrale prende ~2× di un mensile."""
        from billing.calc.utility import calcola_conguaglio_periodo

        AnnualUtilityCost.objects.create(
            voce="tari",
            anno=2025,
            importo_annuale=Decimal("365.00"),
            valid_from=datetime.date(2025, 1, 1),
            valid_to=datetime.date(2025, 12, 31),
        )
        # 2 bimestrali
        bim1 = self._crea_periodo_con_bolletta(
            datetime.date(2025, 1, 1), datetime.date(2025, 2, 28),
            supplier_luce, owner, n=1,
        )  # 59gg
        bim2 = self._crea_periodo_con_bolletta(
            datetime.date(2025, 3, 1), datetime.date(2025, 4, 30),
            supplier_luce, owner, n=2,
        )  # 61gg
        mensili = []
        for mese in range(5, 13):  # mag-dic
            ultimo = calendar.monthrange(2025, mese)[1]
            p = self._crea_periodo_con_bolletta(
                datetime.date(2025, mese, 1),
                datetime.date(2025, mese, ultimo),
                supplier_luce, owner, n=10 + mese,
            )
            mensili.append(p)
        make_assignment(valid_from=datetime.date(2025, 1, 1))

        # sum_giorni = 59+61 + 31+30+31+31+30+31+30+31 = 365 (esatto!)
        # Bimestrale gen-feb: 365 × 59 / 365 = 59.00
        ris_bim1 = calcola_conguaglio_periodo(bim1.pk)
        assert ris_bim1["totali_per_voce"]["tari"] == Decimal("59.00")
        # Mensile maggio (31 gg): 365 × 31 / 365 = 31.00
        ris_mag = calcola_conguaglio_periodo(mensili[0].pk)
        assert ris_mag["totali_per_voce"]["tari"] == Decimal("31.00")

        # Bimestrale prende ~2× di un mensile
        assert ris_bim1["totali_per_voce"]["tari"] > Decimal("1.8") * ris_mag["totali_per_voce"]["tari"]

    def test_periodo_senza_bollette_non_riceve_tari(
        self, db, make_assignment, supplier_luce, owner
    ):
        """Un ``UtilityChargePeriod`` senza bollette luce/gas viene saltato:
        la sua TARI viene redistribuita sugli altri periodi attivi."""
        from billing.calc.utility import calcola_conguaglio_periodo

        AnnualUtilityCost.objects.create(
            voce="tari",
            anno=2026,
            importo_annuale=Decimal("100.00"),
            valid_from=datetime.date(2026, 1, 1),
            valid_to=datetime.date(2026, 12, 31),
        )
        # Periodo senza bollette (sarà skippato)
        UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2026, 1, 1),
            periodo_a=datetime.date(2026, 1, 31),
            criterio_ripartizione="pro_rata_giorni",
        )
        # Periodo CON bollette
        attivo = self._crea_periodo_con_bolletta(
            datetime.date(2026, 2, 1), datetime.date(2026, 2, 28),
            supplier_luce, owner,
        )
        make_assignment(valid_from=datetime.date(2026, 1, 1))

        # Solo il periodo attivo conta nel denominatore (28 giorni)
        # quindi tutta la TARI 100€ va su febbraio: 100 × 28 / 28 = 100
        ris = calcola_conguaglio_periodo(attivo.pk)
        assert ris["totali_per_voce"]["tari"] == Decimal("100.00")

    def test_uscita_meta_mese_con_tari(
        self, db, make_assignment, supplier_luce, owner
    ):
        """Mensilità parziale: A presente tutto il mese (31gg), B esce il 15
        (15gg). TARI totale del periodo = annua (unico periodo attivo);
        ripartizione fra inquilini proporzionale ai giorni di presenza."""
        from billing.calc.utility import calcola_conguaglio_periodo

        AnnualUtilityCost.objects.create(
            voce="tari",
            anno=2026,
            importo_annuale=Decimal("460.00"),
            valid_from=datetime.date(2026, 1, 1),
            valid_to=datetime.date(2026, 12, 31),
        )
        period = self._crea_periodo_con_bolletta(
            datetime.date(2026, 5, 1), datetime.date(2026, 5, 31),
            supplier_luce, owner,
        )
        # A presente tutto maggio
        a_full = make_assignment(valid_from=datetime.date(2026, 5, 1))
        # B esce il 15 maggio (15 giorni: 1-15 inclusi)
        b_partial = make_assignment(
            valid_from=datetime.date(2026, 5, 1),
            valid_to=datetime.date(2026, 5, 15),
        )
        ris = calcola_conguaglio_periodo(period.pk)

        # Totale TARI = annuale (unico periodo attivo) = 460
        assert ris["totali_per_voce"]["tari"] == Decimal("460.00")
        # sum_giorni = 31 (A) + 15 (B) = 46
        assert ris["sum_giorni_presenza"] == 46

        quote_by_id = {q["assignment_id"]: q for q in ris["quote"]}
        # costo_giorno = 460/46 = 10 esatti
        # A: 10 × 31 = 310.00; B: 10 × 15 = 150.00
        assert quote_by_id[a_full.pk]["dettaglio"]["tari"] == Decimal("310.00")
        assert quote_by_id[b_partial.pk]["dettaglio"]["tari"] == Decimal("150.00")
        # Conservazione: somma quote = totale TARI
        assert (
            quote_by_id[a_full.pk]["dettaglio"]["tari"]
            + quote_by_id[b_partial.pk]["dettaglio"]["tari"]
            == Decimal("460.00")
        )

    def test_cambio_stanza_dello_stesso_inquilino(
        self, db, make_assignment, make_room, make_tenant, supplier_luce, owner
    ):
        """Cambio stanza: lo stesso inquilino ha due ``RoomAssignment``
        consecutivi nel mese (es. cambia camera il 15). I due assignment
        contribuiscono alla TARI come se fossero due "presenze" separate
        ma la somma dei loro giorni è quella di un'occupazione continua."""
        from billing.calc.utility import calcola_conguaglio_periodo

        AnnualUtilityCost.objects.create(
            voce="tari",
            anno=2026,
            importo_annuale=Decimal("310.00"),
            valid_from=datetime.date(2026, 1, 1),
            valid_to=datetime.date(2026, 12, 31),
        )
        period = self._crea_periodo_con_bolletta(
            datetime.date(2026, 5, 1), datetime.date(2026, 5, 31),
            supplier_luce, owner,
        )
        tenant = make_tenant(nominativo="MoverInquilino")
        room1 = make_room(nome="Stanza A")
        room2 = make_room(nome="Stanza B")
        # Assignment 1: 1-15 maggio in stanza A (15gg)
        a1 = make_assignment(
            tenant=tenant, room=room1,
            valid_from=datetime.date(2026, 5, 1),
            valid_to=datetime.date(2026, 5, 15),
        )
        # Assignment 2: 16-31 maggio in stanza B (16gg)
        a2 = make_assignment(
            tenant=tenant, room=room2,
            valid_from=datetime.date(2026, 5, 16),
            valid_to=datetime.date(2026, 5, 31),
        )

        ris = calcola_conguaglio_periodo(period.pk)

        # Totale TARI = 310 (unico periodo attivo)
        assert ris["totali_per_voce"]["tari"] == Decimal("310.00")
        # 2 quote (una per assignment), giorni totali 31
        assert len(ris["quote"]) == 2
        assert ris["sum_giorni_presenza"] == 31

        quote_by_id = {q["assignment_id"]: q for q in ris["quote"]}
        # a1 paga 15/31, a2 paga 16/31; somma = totale TARI
        somma_tari = (
            quote_by_id[a1.pk]["dettaglio"]["tari"]
            + quote_by_id[a2.pk]["dettaglio"]["tari"]
        )
        assert abs(somma_tari - Decimal("310.00")) <= Decimal("0.02")
        # a2 paga di più (16gg vs 15gg)
        assert quote_by_id[a2.pk]["dettaglio"]["tari"] > quote_by_id[a1.pk]["dettaglio"]["tari"]


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
    """persist=True deve creare Receivable utenze e popolare i totali sul Period."""

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

        receivables = Receivable.objects.filter(
            utility_period=period, causale=Receivable.Causale.UTENZE
        )
        assert receivables.count() == 2

    def test_persist_popola_campi_period(self, setup_persist):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, assignments = setup_persist
        calcola_conguaglio_periodo(period.pk, persist=True)

        period.refresh_from_db()
        assert period.tot_luce == Decimal("100.00")
        assert period.tot_gas == Decimal("0.00")
        assert period.giorni_totali == 62  # 2 inquilini × 31 giorni

    def test_persist_popola_giorni_presenza_su_receivable(self, setup_persist):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, assignments = setup_persist
        calcola_conguaglio_periodo(period.pk, persist=True)

        for r in Receivable.objects.filter(
            utility_period=period, causale=Receivable.Causale.UTENZE
        ):
            assert r.giorni_presenza == 31

    def test_importo_charge_uguale_quota(self, setup_persist):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, assignments = setup_persist
        risultato = calcola_conguaglio_periodo(period.pk, persist=True)

        for q in risultato["quote"]:
            r = Receivable.objects.get(
                utility_period=period,
                assignment_id=q["assignment_id"],
                causale=Receivable.Causale.UTENZE,
            )
            assert r.importo_dovuto == q["quota"]


# ---------------------------------------------------------------------------
# Idempotenza: ricalcolo non duplica
# ---------------------------------------------------------------------------


class TestIdempotenza:
    """Ricalcolo con persist=True non duplica Receivable utenze."""

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
        count_after_first = Receivable.objects.filter(
            utility_period=period, causale=Receivable.Causale.UTENZE
        ).count()

        # Seconda chiamata: non deve duplicare
        calcola_conguaglio_periodo(period.pk, persist=True)
        count_after_second = Receivable.objects.filter(
            utility_period=period, causale=Receivable.Causale.UTENZE
        ).count()

        assert count_after_first == count_after_second == 2

    def test_persist_aggiorna_totali_period(self, setup_idempotenza):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, assignments = setup_idempotenza

        calcola_conguaglio_periodo(period.pk, persist=True)
        period.refresh_from_db()
        assert period.tot_luce == Decimal("200.00")
        assert period.giorni_totali > 0

        calcola_conguaglio_periodo(period.pk, persist=True)
        period.refresh_from_db()
        assert period.tot_luce == Decimal("200.00")


# ---------------------------------------------------------------------------
# Guardia integrità: receivable già allocati a transazioni bancarie
# ---------------------------------------------------------------------------


class TestGuardiaAllocation:
    """Se un Receivable utenze ha già BankTransactionAllocation, il rilancio di
    calcola_conguaglio_periodo NON deve sovrascriverne importo/righe."""

    @pytest.fixture
    def setup_allocato(self, db, make_assignment, supplier_luce, owner):
        period = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            data_invio=datetime.date(2026, 6, 1),
        )
        UtilityBill.objects.create(
            supplier=supplier_luce,
            numero_fattura="ENEL-GUARD-1",
            data_emissione=datetime.date(2026, 5, 15),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("100.00"),
            pagata_da_owner=owner,
        )
        a1 = make_assignment(valid_from=datetime.date(2026, 5, 1))
        a2 = make_assignment(valid_from=datetime.date(2026, 5, 1))

        owner_account = OwnerBankAccount.objects.create(
            owner=owner,
            banca="Banca Test",
            intestatario="Owner Calc",
            iban="IT00X0000000000000000000001",
        )
        return period, [a1, a2], owner_account

    def test_skip_se_allocato(self, setup_allocato):
        from billing.calc.utility import calcola_conguaglio_periodo

        period, assignments, owner_account = setup_allocato

        calcola_conguaglio_periodo(period.pk, persist=True)
        r1 = Receivable.objects.get(
            utility_period=period,
            assignment=assignments[0],
            causale=Receivable.Causale.UTENZE,
        )
        importo_originale = r1.importo_dovuto

        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 6, 5),
            descrizione="Bonifico utenze",
            importo=importo_originale,
            owner_account=owner_account,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=r1, importo=importo_originale
        )

        r1.importo_dovuto = importo_originale - Decimal("10.00")
        r1.save(update_fields=["importo_dovuto"])
        importo_manuale = r1.importo_dovuto

        # Modifico la bolletta per forzare un calcolo diverso
        bill = UtilityBill.objects.get(numero_fattura="ENEL-GUARD-1")
        bill.importo_totale = Decimal("250.00")
        bill.save(update_fields=["importo_totale"])

        risultato = calcola_conguaglio_periodo(period.pk, persist=True)

        r1.refresh_from_db()
        assert r1.importo_dovuto == importo_manuale, (
            "Receivable allocato non deve essere sovrascritto"
        )

        skippati = risultato["skippati_per_allocation"]
        assert len(skippati) == 1
        assert skippati[0]["receivable_id"] == r1.pk
        assert skippati[0]["importo_esistente"] == importo_manuale

    def test_non_allocato_viene_aggiornato(self, setup_allocato):
        """Sanity check: l'altro receivable (senza allocation) viene comunque ricalcolato."""
        from billing.calc.utility import calcola_conguaglio_periodo

        period, assignments, owner_account = setup_allocato

        calcola_conguaglio_periodo(period.pk, persist=True)
        r1 = Receivable.objects.get(
            utility_period=period,
            assignment=assignments[0],
            causale=Receivable.Causale.UTENZE,
        )

        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 6, 5),
            descrizione="Bonifico",
            importo=r1.importo_dovuto,
            owner_account=owner_account,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=r1, importo=r1.importo_dovuto
        )

        bill = UtilityBill.objects.get(numero_fattura="ENEL-GUARD-1")
        bill.importo_totale = Decimal("300.00")
        bill.save(update_fields=["importo_totale"])

        calcola_conguaglio_periodo(period.pk, persist=True)

        r2 = Receivable.objects.get(
            utility_period=period,
            assignment=assignments[1],
            causale=Receivable.Causale.UTENZE,
        )
        assert r2.importo_dovuto == Decimal("150.00")


# ---------------------------------------------------------------------------
# Attribuzione bolletta → periodo (regole del 2026-05-13)
# ---------------------------------------------------------------------------


class TestAttribuzioneBolletta:
    """La bolletta si attribuisce in pro-rata sui giorni di intersezione col
    periodo, dopo aver troncato le porzioni che cadono in periodi `inviato`.

    Caso operativo: a fine mese arriva una bolletta etichettata "gen-apr" ma
    gen-feb era già stato fatturato con un'altra bolletta. La porzione gen-feb
    si comprime: tutto l'importo si attribuisce su mar-apr (l'unico periodo
    rimasto nel range bolletta).
    """

    def test_prodotto_gas_va_su_voce_gas_anche_con_supplier_energia(
        self, db, make_assignment, supplier_luce, owner
    ):
        """`bill.prodotto` è il discriminante luce/gas, non `supplier.tipo`.
        (regressione: bolletta gas erogata dallo stesso fornitore luce.)"""
        from billing.calc.utility import calcola_conguaglio_periodo

        period = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
        )
        UtilityBill.objects.create(
            supplier=supplier_luce,  # tipo "energia"
            prodotto="gas",          # ma prodotto gas
            numero_fattura="WIND-GAS",
            data_emissione=datetime.date(2026, 5, 31),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("22.37"),
            pagata_da_owner=owner,
        )
        # Serve almeno un assignment per avere quote
        make_assignment(valid_from=datetime.date(2026, 5, 1))

        ris = calcola_conguaglio_periodo(period.pk)
        # Niente luce, tutto gas
        assert ris["totali_per_voce"].get("luce", Decimal("0")) == Decimal("0")
        assert ris["totali_per_voce"]["gas"] == Decimal("22.37")

    def test_troncamento_porzione_in_periodo_inviato(
        self, db, make_assignment, supplier_luce, owner
    ):
        """Bolletta etichettata gen-apr (120gg), periodo gen-feb già `inviato`:
        la porzione gen-feb si comprime, l'intero importo va sul periodo
        mar-apr (61gg)."""
        from billing.calc.utility import calcola_conguaglio_periodo

        # gen-feb chiuso
        gen_feb = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2025, 1, 1),
            periodo_a=datetime.date(2025, 2, 28),
            stato=UtilityChargePeriod.StatoPeriodo.INVIATO,
        )
        # mar-apr in calcolo
        mar_apr = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2025, 3, 1),
            periodo_a=datetime.date(2025, 4, 30),
        )
        # Bolletta gen-apr che arriva durante mar-apr
        UtilityBill.objects.create(
            supplier=supplier_luce,
            prodotto="luce",
            numero_fattura="ENEL-GENAPR",
            data_emissione=datetime.date(2025, 4, 15),
            periodo_da=datetime.date(2025, 1, 1),
            periodo_a=datetime.date(2025, 4, 30),
            importo_totale=Decimal("120.00"),
            pagata_da_owner=owner,
        )
        make_assignment(valid_from=datetime.date(2025, 1, 1))

        ris = calcola_conguaglio_periodo(mar_apr.pk)
        # gen-feb è chiuso → range effettivo = mar-apr (61gg). Tutta sul periodo.
        assert ris["totali_per_voce"]["luce"] == Decimal("120.00"), (
            f"Atteso 120.00 (tutta la bolletta), trovato {ris['totali_per_voce']['luce']}"
        )

    def test_ribaltamento_su_successivo_se_tutto_in_chiusi(
        self, db, make_assignment, supplier_luce, owner
    ):
        """Bolletta che cade interamente in periodi `inviato`: viene
        ribaltata sul primo periodo bozza con periodo_da ≥ data_emissione."""
        from billing.calc.utility import calcola_conguaglio_periodo

        # gen-feb e mar-apr entrambi chiusi
        UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2025, 1, 1),
            periodo_a=datetime.date(2025, 2, 28),
            stato=UtilityChargePeriod.StatoPeriodo.INVIATO,
        )
        UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2025, 3, 1),
            periodo_a=datetime.date(2025, 4, 30),
            stato=UtilityChargePeriod.StatoPeriodo.INVIATO,
        )
        # maggio in calcolo (bozza)
        mag = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2025, 5, 1),
            periodo_a=datetime.date(2025, 5, 31),
        )
        # Bolletta gen-apr emessa a maggio: range tutto in chiusi → ribalta su maggio
        UtilityBill.objects.create(
            supplier=supplier_luce,
            prodotto="luce",
            numero_fattura="ENEL-RETRO",
            data_emissione=datetime.date(2025, 5, 22),
            periodo_da=datetime.date(2025, 1, 1),
            periodo_a=datetime.date(2025, 4, 30),
            importo_totale=Decimal("111.21"),
            pagata_da_owner=owner,
        )
        # Bolletta maggio "vera"
        UtilityBill.objects.create(
            supplier=supplier_luce,
            prodotto="luce",
            numero_fattura="WIND-MAG",
            data_emissione=datetime.date(2025, 5, 31),
            periodo_da=datetime.date(2025, 5, 1),
            periodo_a=datetime.date(2025, 5, 31),
            importo_totale=Decimal("156.49"),
            pagata_da_owner=owner,
        )
        make_assignment(valid_from=datetime.date(2025, 1, 1))

        ris = calcola_conguaglio_periodo(mag.pk)
        # 156.49 (mag) + 111.21 (ribaltata) = 267.70
        assert ris["totali_per_voce"]["luce"] == Decimal("267.70"), (
            f"Atteso 267.70, trovato {ris['totali_per_voce']['luce']}"
        )

    def test_bolletta_consumata_da_periodo_inviato_non_riconta(
        self, db, make_assignment, supplier_luce, owner
    ):
        """Una bolletta già agganciata via M2M a un periodo `inviato` non
        rientra nel calcolo di un altro periodo (anche se il range bolletta
        intersecherebbe l'altro periodo)."""
        from billing.calc.utility import calcola_conguaglio_periodo

        # mar-apr inviato, con la sua bolletta gen-apr già "consumata"
        mar_apr = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2025, 3, 1),
            periodo_a=datetime.date(2025, 4, 30),
            stato=UtilityChargePeriod.StatoPeriodo.INVIATO,
        )
        bolletta = UtilityBill.objects.create(
            supplier=supplier_luce,
            prodotto="luce",
            numero_fattura="ENEL-CONS",
            data_emissione=datetime.date(2025, 5, 22),
            periodo_da=datetime.date(2025, 1, 1),
            periodo_a=datetime.date(2025, 4, 30),
            importo_totale=Decimal("111.21"),
            pagata_da_owner=owner,
        )
        mar_apr.utility_bills.add(bolletta)

        # Calcolo maggio: la bolletta NON deve essere riconteggiata
        mag = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2025, 5, 1),
            periodo_a=datetime.date(2025, 5, 31),
        )
        UtilityBill.objects.create(
            supplier=supplier_luce,
            prodotto="luce",
            numero_fattura="WIND-MAG",
            data_emissione=datetime.date(2025, 5, 31),
            periodo_da=datetime.date(2025, 5, 1),
            periodo_a=datetime.date(2025, 5, 31),
            importo_totale=Decimal("156.49"),
            pagata_da_owner=owner,
        )
        make_assignment(valid_from=datetime.date(2025, 1, 1))

        ris = calcola_conguaglio_periodo(mag.pk)
        # Solo la bolletta di maggio
        assert ris["totali_per_voce"]["luce"] == Decimal("156.49"), (
            f"Atteso 156.49, trovato {ris['totali_per_voce']['luce']}"
        )

    def test_pinning_manuale_override_algoritmo(
        self, db, make_assignment, supplier_luce, owner
    ):
        """Se la M2M ``period.utility_bills`` è già popolata, il calcolo entra
        in modalità pinning: ogni bolletta agganciata contribuisce per
        l'importo intero, ignorando completamente l'algoritmo di troncamento/
        ribaltamento. Caso d'uso: decisioni storiche dell'utente caso-per-caso
        che non sono ricavabili da regole automatiche."""
        from billing.calc.utility import calcola_conguaglio_periodo

        # Setup: due bollette potenzialmente candidate per maggio, ma l'utente
        # vuole solo una agganciata.
        mag = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2025, 5, 1),
            periodo_a=datetime.date(2025, 5, 31),
        )
        b_pinned = UtilityBill.objects.create(
            supplier=supplier_luce,
            prodotto="luce",
            numero_fattura="PIN-1",
            data_emissione=datetime.date(2025, 5, 22),
            periodo_da=datetime.date(2025, 1, 1),  # range storico, automatico
            periodo_a=datetime.date(2025, 4, 30),  # lo metterebbe altrove
            importo_totale=Decimal("111.21"),
            pagata_da_owner=owner,
        )
        # Bolletta "naturale" per maggio, NON pinnata: deve essere ignorata
        UtilityBill.objects.create(
            supplier=supplier_luce,
            prodotto="luce",
            numero_fattura="AUTO-MAG",
            data_emissione=datetime.date(2025, 5, 31),
            periodo_da=datetime.date(2025, 5, 1),
            periodo_a=datetime.date(2025, 5, 31),
            importo_totale=Decimal("156.49"),
            pagata_da_owner=owner,
        )
        # Pin manuale: solo b_pinned su maggio
        mag.utility_bills.add(b_pinned)
        make_assignment(valid_from=datetime.date(2025, 5, 1))

        ris = calcola_conguaglio_periodo(mag.pk)
        # Solo la bolletta pinnata, intera. L'altra è ignorata.
        assert ris["totali_per_voce"]["luce"] == Decimal("111.21"), (
            f"Atteso 111.21 (solo pinned), trovato {ris['totali_per_voce']['luce']}"
        )

    def test_ciclo_fatturazione_non_influenza_giorni_presenza(
        self, db, make_assignment, make_room, make_tenant, supplier_luce, owner
    ):
        """Regressione: il calcolo utenze deve essere SEMPRE pro-rata sui
        giorni effettivi di RoomAssignment, indipendente da
        ``TenantProfile.ciclo_fatturazione`` (che vale solo per gli affitti).

        Caso: tenant con ciclo='ingresso' entrato il 9/2/2025. Per il periodo
        gen-feb 2025 deve contare 20gg (dal 9 al 28), non un altro valore
        eventualmente influenzato dal ciclo di fatturazione 'ingresso'.
        """
        from billing.calc.utility import calcola_conguaglio_periodo
        from properties.models import TenantProfile

        period = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2025, 1, 1),
            periodo_a=datetime.date(2025, 2, 28),
        )
        UtilityBill.objects.create(
            supplier=supplier_luce,
            prodotto="luce",
            numero_fattura="REGR-CICLO-1",
            data_emissione=datetime.date(2025, 2, 28),
            periodo_da=datetime.date(2025, 1, 1),
            periodo_a=datetime.date(2025, 2, 28),
            importo_totale=Decimal("295.00"),
            pagata_da_owner=owner,
        )
        # Tenant con ciclo_fatturazione='ingresso' (NON deve influenzare utenze)
        tenant_ingresso = make_tenant(nominativo="Tenant Ingresso")
        tenant_ingresso.ciclo_fatturazione = TenantProfile.CicloFatturazione.INGRESSO
        tenant_ingresso.save(update_fields=["ciclo_fatturazione"])
        # Tenant con ciclo_fatturazione='solare' (controllo)
        tenant_solare = make_tenant(nominativo="Tenant Solare")
        tenant_solare.ciclo_fatturazione = TenantProfile.CicloFatturazione.SOLARE
        tenant_solare.save(update_fields=["ciclo_fatturazione"])

        # Entrambi entrano il 9/2/2025: presenti 20gg nel bimestre.
        ass_ingresso = make_assignment(
            tenant=tenant_ingresso,
            valid_from=datetime.date(2025, 2, 9),
        )
        ass_solare = make_assignment(
            tenant=tenant_solare,
            valid_from=datetime.date(2025, 2, 9),
        )

        ris = calcola_conguaglio_periodo(period.pk)
        quote_by_id = {q["assignment_id"]: q for q in ris["quote"]}
        # Identica presenza per entrambi: 20gg
        assert quote_by_id[ass_ingresso.pk]["giorni_presenza"] == 20, (
            f"Atteso 20gg, trovato {quote_by_id[ass_ingresso.pk]['giorni_presenza']}"
        )
        assert quote_by_id[ass_solare.pk]["giorni_presenza"] == 20, (
            f"Atteso 20gg, trovato {quote_by_id[ass_solare.pk]['giorni_presenza']}"
        )
        # Identica quota: il ciclo_fatturazione non discrimina
        assert quote_by_id[ass_ingresso.pk]["quota"] == quote_by_id[ass_solare.pk]["quota"]

    def test_persist_popola_m2m_utility_bills(
        self, db, make_assignment, supplier_luce, owner
    ):
        """``persist=True`` aggancia le bollette utilizzate alla M2M del periodo,
        così i ricalcoli successivi le riconoscono come "consumate"."""
        from billing.calc.utility import calcola_conguaglio_periodo

        period = UtilityChargePeriod.objects.create(
            periodo_da=datetime.date(2025, 5, 1),
            periodo_a=datetime.date(2025, 5, 31),
        )
        b1 = UtilityBill.objects.create(
            supplier=supplier_luce,
            prodotto="luce",
            numero_fattura="WIND-MAG-1",
            data_emissione=datetime.date(2025, 5, 31),
            periodo_da=datetime.date(2025, 5, 1),
            periodo_a=datetime.date(2025, 5, 31),
            importo_totale=Decimal("100.00"),
            pagata_da_owner=owner,
        )
        b2 = UtilityBill.objects.create(
            supplier=supplier_luce,
            prodotto="gas",
            numero_fattura="WIND-MAG-2",
            data_emissione=datetime.date(2025, 5, 31),
            periodo_da=datetime.date(2025, 5, 1),
            periodo_a=datetime.date(2025, 5, 31),
            importo_totale=Decimal("20.00"),
            pagata_da_owner=owner,
        )
        make_assignment(valid_from=datetime.date(2025, 5, 1))

        calcola_conguaglio_periodo(period.pk, persist=True)
        period.refresh_from_db()
        bills_agganciate = set(period.utility_bills.values_list("pk", flat=True))
        assert bills_agganciate == {b1.pk, b2.pk}


# ---------------------------------------------------------------------------
# Output arricchito: importo_esistente nelle quote, contatori diversi/uguali, ordering
# ---------------------------------------------------------------------------


class TestQuoteImportoEsistente:
    """Le quote includono `importo_esistente` per consentire all'admin di
    distinguere nuovo/uguale/diverso in dry-run."""

    @pytest.fixture
    def setup(self, db, make_assignment, make_tenant, make_room, periodo_maggio, supplier_luce, owner):
        # 2 inquilini per maggio 2026
        t1 = make_tenant(nominativo="Aaa")
        t2 = make_tenant(nominativo="Bbb")
        make_assignment(
            tenant=t1, room=make_room(),
            valid_from=datetime.date(2026, 5, 1),
        )
        make_assignment(
            tenant=t2, room=make_room(),
            valid_from=datetime.date(2026, 5, 1),
        )
        UtilityBill.objects.create(
            supplier=supplier_luce,
            numero_fattura="ENEL-TEST-DIVERG",
            data_emissione=datetime.date(2026, 5, 15),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("200.00"),
            pagata_da_owner=owner,
        )
        return periodo_maggio

    def test_dry_run_quote_includono_importo_esistente_none(self, setup):
        from billing.calc.utility import calcola_conguaglio_periodo

        # Prima esecuzione, nessun Receivable esiste ancora
        ris = calcola_conguaglio_periodo(setup.pk, persist=False)
        for q in ris["quote"]:
            assert q["importo_esistente"] is None

    def test_dry_run_quote_includono_importo_esistente_valorizzato(self, setup):
        from billing.calc.utility import calcola_conguaglio_periodo

        # Persisti prima
        calcola_conguaglio_periodo(setup.pk, persist=True)
        # Poi dry-run: importo_esistente deve riflettere il valore esistente
        ris = calcola_conguaglio_periodo(setup.pk, persist=False)
        for q in ris["quote"]:
            assert q["importo_esistente"] == q["quota"]


class TestPersistContatoriUtility:
    """Persist popola contatori creati / aggiornati_diversi / aggiornati_uguali."""

    @pytest.fixture
    def setup(self, db, make_assignment, make_tenant, make_room, periodo_maggio, supplier_luce, owner):
        t1 = make_tenant(nominativo="Aaa")
        t2 = make_tenant(nominativo="Bbb")
        make_assignment(
            tenant=t1, room=make_room(),
            valid_from=datetime.date(2026, 5, 1),
        )
        make_assignment(
            tenant=t2, room=make_room(),
            valid_from=datetime.date(2026, 5, 1),
        )
        UtilityBill.objects.create(
            supplier=supplier_luce,
            numero_fattura="ENEL-PERSIST-CNT",
            data_emissione=datetime.date(2026, 5, 15),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("200.00"),
            pagata_da_owner=owner,
        )
        return periodo_maggio

    def test_prima_run_conta_creati(self, setup):
        from billing.calc.utility import calcola_conguaglio_periodo

        ris = calcola_conguaglio_periodo(setup.pk, persist=True)
        assert ris["creati"] == 2
        assert ris["aggiornati_diversi"] == 0
        assert ris["aggiornati_uguali"] == 0

    def test_seconda_run_uguali(self, setup):
        from billing.calc.utility import calcola_conguaglio_periodo

        calcola_conguaglio_periodo(setup.pk, persist=True)
        ris = calcola_conguaglio_periodo(setup.pk, persist=True)
        assert ris["creati"] == 0
        assert ris["aggiornati_diversi"] == 0
        assert ris["aggiornati_uguali"] == 2

    def test_run_dopo_modifica_bolletta_conta_diversi(self, setup):
        from billing.calc.utility import calcola_conguaglio_periodo

        calcola_conguaglio_periodo(setup.pk, persist=True)
        # Modifico l'importo della bolletta pinned: il pinning M2M trattiene
        # la bolletta, e il ricalcolo somma il nuovo importo_totale.
        bill = UtilityBill.objects.get(numero_fattura="ENEL-PERSIST-CNT")
        bill.importo_totale = Decimal("300.00")
        bill.save(update_fields=["importo_totale"])
        ris = calcola_conguaglio_periodo(setup.pk, persist=True)
        assert ris["aggiornati_diversi"] == 2
        assert ris["aggiornati_uguali"] == 0


class TestOrderingQuotePerNominativo:
    """Le quote escono in ordine alfabetico di nominativo per output stabile."""

    def test_ordering(self, db, make_assignment, make_tenant, make_room, periodo_maggio, supplier_luce, owner):
        from billing.calc.utility import calcola_conguaglio_periodo

        # Tenant in ordine non alfabetico per pk
        t_zorro = make_tenant(nominativo="Zorro")
        t_alpha = make_tenant(nominativo="Alpha")
        t_mike = make_tenant(nominativo="Mike")
        make_assignment(
            tenant=t_zorro, room=make_room(),
            valid_from=datetime.date(2026, 5, 1),
        )
        make_assignment(
            tenant=t_alpha, room=make_room(),
            valid_from=datetime.date(2026, 5, 1),
        )
        make_assignment(
            tenant=t_mike, room=make_room(),
            valid_from=datetime.date(2026, 5, 1),
        )
        UtilityBill.objects.create(
            supplier=supplier_luce,
            numero_fattura="ENEL-ORDER",
            data_emissione=datetime.date(2026, 5, 15),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("300.00"),
            pagata_da_owner=owner,
        )
        ris = calcola_conguaglio_periodo(periodo_maggio.pk, persist=False)
        nominativi = [q["tenant_nominativo"] for q in ris["quote"]]
        assert nominativi == ["Alpha", "Mike", "Zorro"]
