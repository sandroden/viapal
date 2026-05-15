"""
Test per genera_pagamenti_mese e aggiustamento_uscita (billing/calc/rent.py).

Coprono:
- Genera per maggio 2026, 5 assignment attivi -> crea 5 payment
- Idempotenza: ricalcolato non duplica
- Aggiustamento ingresso: valid_from = 15 maggio -> giorni=17, importo pro-rata
- Aggiustamento uscita: valid_to = 10 maggio -> giorni=10, importo pro-rata
- Mese senza assignment: 0 record creati (no-op)
- aggiustamento_uscita: crea ExtraCharge negativo
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    Receivable,
    StatoPagamento,
)
from properties.models import (
    OwnerBankAccount,
    OwnerProfile,
    Room,
    RoomAssignment,
    TenantProfile,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_tenant(db):
    """Factory TenantProfile."""
    counter = [0]

    def _make(nominativo="Inquilino Rent", giorno_pagamento=1):
        counter[0] += 1
        u = User.objects.create_user(
            username=f"tenant_rent_{counter[0]}",
            email=f"tenant_rent_{counter[0]}@v.it",
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
    """Factory Room."""
    counter = [0]

    def _make(nome=None):
        counter[0] += 1
        return Room.objects.create(
            nome=nome or f"Camera Rent {counter[0]}",
            ordinamento=counter[0],
        )

    return _make


@pytest.fixture
def make_assignment(db, make_room, make_tenant):
    """Factory RoomAssignment."""

    def _make(
        canone=Decimal("500.00"),
        valid_from=datetime.date(2026, 5, 1),
        valid_to=None,
        giorno_pagamento=1,
        nominativo=None,
        room=None,
    ):
        t = make_tenant(
            nominativo=nominativo or f"Tenant_{valid_from}",
            giorno_pagamento=giorno_pagamento,
        )
        r = room or make_room()
        return RoomAssignment.objects.create(
            room=r,
            tenant=t,
            valid_from=valid_from,
            valid_to=valid_to,
            canone_mensile=canone,
        )

    return _make


# ---------------------------------------------------------------------------
# Test: genera per maggio 2026, 5 assignment -> 5 payment
# ---------------------------------------------------------------------------


class TestGeneraPagamentiMese:
    """Genera per maggio 2026 con 5 assignment attivi."""

    @pytest.fixture
    def setup_5_assignment(self, db, make_assignment):
        return [
            make_assignment(
                canone=Decimal("420.00"),
                valid_from=datetime.date(2026, 5, 1),
                giorno_pagamento=1,
            )
            for _ in range(5)
        ]

    def test_crea_5_payment(self, setup_5_assignment):
        from billing.calc.rent import genera_pagamenti_mese

        risultato = genera_pagamenti_mese(2026, 5)

        assert risultato["creati"] == 5
        assert risultato["aggiornati"] == 0
        assert risultato["skippati"] == 0
        assert len(risultato["payments"]) == 5

    def test_stato_iniziale_atteso(self, setup_5_assignment):
        from billing.calc.rent import genera_pagamenti_mese

        genera_pagamenti_mese(2026, 5)

        for p in Receivable.objects.filter(causale="affitto"):
            assert p.stato == StatoPagamento.ATTESO

    def test_competenza_maggio_intera(self, setup_5_assignment):
        from billing.calc.rent import genera_pagamenti_mese

        genera_pagamenti_mese(2026, 5)

        for p in Receivable.objects.filter(causale="affitto"):
            assert p.competenza_da == datetime.date(2026, 5, 1)
            assert p.competenza_a == datetime.date(2026, 5, 31)
            assert not p.is_aggiustamento
            assert p.importo_dovuto == Decimal("420.00")

    def test_scadenza_corretta(self, setup_5_assignment):
        """Scadenza = giorno_pagamento(1) + 5gg = 6 maggio 2026."""
        from billing.calc.rent import genera_pagamenti_mese

        genera_pagamenti_mese(2026, 5)

        for p in Receivable.objects.filter(causale="affitto"):
            assert p.scadenza == datetime.date(2026, 5, 6)  # 1 + 5gg


# ---------------------------------------------------------------------------
# Idempotenza
# ---------------------------------------------------------------------------


class TestIdempotenzaRent:
    """Ricalcolo non duplica i RentPayment."""

    @pytest.fixture
    def setup_idempotenza(self, db, make_assignment):
        return [
            make_assignment(valid_from=datetime.date(2026, 5, 1))
            for _ in range(3)
        ]

    def test_non_duplica(self, setup_idempotenza):
        from billing.calc.rent import genera_pagamenti_mese

        # Prima chiamata
        r1 = genera_pagamenti_mese(2026, 5)
        count_after_first = Receivable.objects.filter(causale="affitto").count()

        # Seconda chiamata
        r2 = genera_pagamenti_mese(2026, 5)
        count_after_second = Receivable.objects.filter(causale="affitto").count()

        assert count_after_first == count_after_second == 3
        assert r2["creati"] == 0
        assert r2["skippati"] == 3

    def test_force_aggiorna(self, setup_idempotenza):
        from billing.calc.rent import genera_pagamenti_mese

        genera_pagamenti_mese(2026, 5)
        r2 = genera_pagamenti_mese(2026, 5, force=True)

        assert r2["aggiornati"] == 3
        assert r2["creati"] == 0


# ---------------------------------------------------------------------------
# Guardia integrità: force non sovrascrive Receivable già allocati
# ---------------------------------------------------------------------------


class TestGuardiaAllocationForce:
    """Se un Receivable affitto ha BankTransactionAllocation, force NON deve
    sovrascrivere importo/competenza_a/scadenza."""

    @pytest.fixture
    def setup_allocato(self, db, make_assignment):
        a1 = make_assignment(valid_from=datetime.date(2026, 5, 1))
        a2 = make_assignment(valid_from=datetime.date(2026, 5, 1))

        owner_user = User.objects.create_user(
            "owner_guard", email="owner_guard@v.it", password="pwd"
        )
        owner = OwnerProfile.objects.create(user=owner_user, nominativo="Owner Guard")
        owner_account = OwnerBankAccount.objects.create(
            owner=owner,
            banca="Banca Test",
            intestatario="Owner Guard",
            iban="IT00X0000000000000000000002",
        )
        return [a1, a2], owner_account

    def test_force_skip_se_allocato(self, setup_allocato):
        from billing.calc.rent import genera_pagamenti_mese

        assignments, owner_account = setup_allocato

        genera_pagamenti_mese(2026, 5)
        r1 = Receivable.objects.get(
            assignment=assignments[0], causale=Receivable.Causale.AFFITTO
        )
        importo_originale = r1.importo_dovuto

        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 5, 3),
            descrizione="Bonifico affitto",
            importo=importo_originale,
            owner_account=owner_account,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=r1, importo=importo_originale
        )

        # Cambio il canone dell'assignment per forzare un calcolo diverso
        assignments[0].canone_mensile = Decimal("999.99")
        assignments[0].save(update_fields=["canone_mensile"])

        risultato = genera_pagamenti_mese(2026, 5, force=True)

        r1.refresh_from_db()
        assert r1.importo_dovuto == importo_originale, (
            "Receivable allocato non deve essere sovrascritto"
        )

        skippati = risultato["skippati_per_allocation"]
        assert len(skippati) == 1
        assert skippati[0]["receivable_id"] == r1.pk
        assert skippati[0]["importo_esistente"] == importo_originale
        assert skippati[0]["importo_calcolato"] == Decimal("999.99")

        # L'altro receivable senza allocation viene comunque aggiornato
        assert risultato["aggiornati"] == 1


# ---------------------------------------------------------------------------
# Aggiustamento ingresso (valid_from = 15 maggio)
# ---------------------------------------------------------------------------


class TestAggiustamentoIngresso:
    """Assignment con valid_from = 15 maggio -> giorni=17, importo pro-rata."""

    @pytest.fixture
    def setup_ingresso(self, db, make_assignment):
        # Canone 620€, entra il 15 maggio (17 giorni su 31)
        return make_assignment(
            canone=Decimal("620.00"),
            valid_from=datetime.date(2026, 5, 15),
        )

    def test_giorni_competenza(self, setup_ingresso):
        from billing.calc.rent import genera_pagamenti_mese

        genera_pagamenti_mese(2026, 5)

        p = Receivable.objects.get(causale="affitto")
        assert p.competenza_da == datetime.date(2026, 5, 15)
        assert p.competenza_a == datetime.date(2026, 5, 31)

    def test_is_aggiustamento(self, setup_ingresso):
        from billing.calc.rent import genera_pagamenti_mese

        genera_pagamenti_mese(2026, 5)

        p = Receivable.objects.get(causale="affitto")
        assert p.is_aggiustamento is True

    def test_importo_pro_rata(self, setup_ingresso):
        """620 * 17/31 = 340.00 (ROUND_HALF_UP)."""
        from billing.calc.rent import genera_pagamenti_mese

        genera_pagamenti_mese(2026, 5)

        p = Receivable.objects.get(causale="affitto")
        # 620 * 17 / 31 = 10540 / 31 = 340.0
        atteso = (Decimal("620.00") * Decimal(17) / Decimal(31)).quantize(
            Decimal("0.01"), rounding=__import__("decimal").ROUND_HALF_UP
        )
        assert p.importo_dovuto == atteso


# ---------------------------------------------------------------------------
# Aggiustamento uscita (valid_to = 10 maggio)
# ---------------------------------------------------------------------------


class TestAggiustamentoUscita:
    """Assignment con valid_to = 10 maggio -> giorni=10, importo pro-rata."""

    @pytest.fixture
    def setup_uscita(self, db, make_assignment):
        # Canone 500€, esce il 10 maggio
        return make_assignment(
            canone=Decimal("500.00"),
            valid_from=datetime.date(2026, 1, 1),
            valid_to=datetime.date(2026, 5, 10),
        )

    def test_giorni_competenza_uscita(self, setup_uscita):
        from billing.calc.rent import genera_pagamenti_mese

        genera_pagamenti_mese(2026, 5)

        p = Receivable.objects.get(causale="affitto")
        assert p.competenza_da == datetime.date(2026, 5, 1)
        assert p.competenza_a == datetime.date(2026, 5, 10)

    def test_is_aggiustamento_uscita(self, setup_uscita):
        from billing.calc.rent import genera_pagamenti_mese

        genera_pagamenti_mese(2026, 5)

        p = Receivable.objects.get(causale="affitto")
        assert p.is_aggiustamento is True

    def test_importo_pro_rata_uscita(self, setup_uscita):
        """500 * 10/31 = 161.29 (ROUND_HALF_UP)."""
        from billing.calc.rent import genera_pagamenti_mese

        genera_pagamenti_mese(2026, 5)

        p = Receivable.objects.get(causale="affitto")
        atteso = (Decimal("500.00") * Decimal(10) / Decimal(31)).quantize(
            Decimal("0.01"), rounding=__import__("decimal").ROUND_HALF_UP
        )
        assert p.importo_dovuto == atteso


# ---------------------------------------------------------------------------
# Mese senza assignment: 0 record creati
# ---------------------------------------------------------------------------


class TestMeseSenzaAssignment:
    """Nessun assignment attivo nel mese -> risultato vuoto."""

    def test_nessun_payment(self, db):
        from billing.calc.rent import genera_pagamenti_mese

        # Non ci sono assignment nel DB
        risultato = genera_pagamenti_mese(2030, 1)

        assert risultato["creati"] == 0
        assert risultato["aggiornati"] == 0
        assert risultato["skippati"] == 0
        assert risultato["payments"] == []
        assert Receivable.objects.filter(causale="affitto").count() == 0

    def test_assignment_precedente_non_incluso(self, db, make_assignment):
        """Assignment terminato prima del mese non viene incluso."""
        # Terminato il 30 aprile
        make_assignment(
            valid_from=datetime.date(2026, 1, 1),
            valid_to=datetime.date(2026, 4, 30),
        )

        from billing.calc.rent import genera_pagamenti_mese

        risultato = genera_pagamenti_mese(2026, 5)

        assert risultato["creati"] == 0
        assert Receivable.objects.filter(causale="affitto").count() == 0

    def test_assignment_futuro_non_incluso(self, db, make_assignment):
        """Assignment che inizia dopo il mese non viene incluso."""
        make_assignment(valid_from=datetime.date(2026, 6, 1))

        from billing.calc.rent import genera_pagamenti_mese

        risultato = genera_pagamenti_mese(2026, 5)

        assert risultato["creati"] == 0


# ---------------------------------------------------------------------------
# aggiustamento_uscita: crea ExtraCharge negativo
# ---------------------------------------------------------------------------


class TestAggiustamentoUscitaExtraCharge:
    """aggiustamento_uscita crea ExtraCharge con importo negativo."""

    @pytest.fixture
    def setup_extra(self, db, make_assignment):
        return make_assignment(
            canone=Decimal("600.00"),
            valid_from=datetime.date(2026, 1, 1),
        )

    def test_crea_extra_charge_negativo(self, setup_extra):
        from billing.calc.rent import aggiustamento_uscita

        assignment = setup_extra
        result = aggiustamento_uscita(assignment.pk, datetime.date(2026, 5, 15))

        extra = result["extra_charge"]
        assert extra is not None
        assert extra.importo_dovuto < Decimal("0.00"), "L'importo deve essere negativo (rimborso)"

    def test_importo_rimborso_corretto(self, setup_extra):
        """Uscita il 15 maggio: rimborso per i 16 giorni non goduti (16-31)."""
        from billing.calc.rent import aggiustamento_uscita

        assignment = setup_extra
        result = aggiustamento_uscita(assignment.pk, datetime.date(2026, 5, 15))

        # giorni_non_goduti = 31 - 15 = 16
        assert result["giorni_non_goduti"] == 16
        assert result["giorni_presenti"] == 15

        atteso = (Decimal("600.00") * Decimal(16) / Decimal(31)).quantize(
            Decimal("0.01"), rounding=__import__("decimal").ROUND_HALF_UP
        )
        assert result["importo_rimborso"] == atteso
        assert result["extra_charge"].importo_dovuto == -atteso

    def test_nessun_rimborso_ultimo_giorno(self, setup_extra):
        """Uscita il 31 maggio: nessun rimborso."""
        from billing.calc.rent import aggiustamento_uscita

        assignment = setup_extra
        result = aggiustamento_uscita(assignment.pk, datetime.date(2026, 5, 31))

        assert result["extra_charge"] is None
        assert result["giorni_non_goduti"] == 0
        assert Receivable.objects.filter(causale="extra").count() == 0

    def test_extra_charge_stato_atteso(self, setup_extra):
        from billing.calc.rent import aggiustamento_uscita

        assignment = setup_extra
        result = aggiustamento_uscita(assignment.pk, datetime.date(2026, 5, 20))

        extra = result["extra_charge"]
        assert extra.stato == StatoPagamento.ATTESO

    def test_descrizione_contiene_data(self, setup_extra):
        from billing.calc.rent import aggiustamento_uscita

        assignment = setup_extra
        result = aggiustamento_uscita(assignment.pk, datetime.date(2026, 5, 10))

        extra = result["extra_charge"]
        assert "10/05/2026" in extra.descrizione

    def test_rimborso_febbraio_28_giorni(self, db, make_assignment):
        """Mese di febbraio (28 giorni) -> giorni_mese corretto."""
        assignment = make_assignment(
            canone=Decimal("400.00"),
            valid_from=datetime.date(2026, 1, 1),
        )
        from billing.calc.rent import aggiustamento_uscita

        result = aggiustamento_uscita(assignment.pk, datetime.date(2026, 2, 14))

        # 28 - 14 = 14 giorni non goduti
        assert result["giorni_non_goduti"] == 14
        atteso = (Decimal("400.00") * Decimal(14) / Decimal(28)).quantize(
            Decimal("0.01"), rounding=__import__("decimal").ROUND_HALF_UP
        )
        assert result["importo_rimborso"] == atteso


# ---------------------------------------------------------------------------
# Test scadenza con giorno_pagamento > giorni_mese (gestione edge case)
# ---------------------------------------------------------------------------


class TestScadenzaFebbbraio:
    """Giorno pagamento 28, mese febbraio 2026 (28 giorni): scadenza = 28 + 5 = 5 marzo."""

    def test_scadenza_febbraio_28gg(self, db, make_assignment):
        assignment = make_assignment(
            valid_from=datetime.date(2026, 2, 1),
            giorno_pagamento=28,
        )

        from billing.calc.rent import genera_pagamenti_mese

        genera_pagamenti_mese(2026, 2)

        p = Receivable.objects.get(causale="affitto")
        # feb 2026 ha 28 giorni, giorno_eff = min(28, 28) = 28
        # scadenza = 28 feb + 5 = 5 mar
        assert p.scadenza == datetime.date(2026, 3, 5)


# ---------------------------------------------------------------------------
# Test ciclo_fatturazione = INGRESSO (mensilità da giorno di ingresso)
# ---------------------------------------------------------------------------


class TestCicloIngresso:
    """Inquilino con ciclo_fatturazione='ingresso': mensilità anniversary.

    Scenario reale: ragazza entrata 9/2/2025, valid_to=8/7/2025
    (esce il 9/7, ultimo giorno coperto è 8/7) → 5 mensilità intere.
    """

    @pytest.fixture
    def assignment_ingresso(self, db, make_assignment):
        a = make_assignment(
            canone=Decimal("500.00"),
            valid_from=datetime.date(2025, 2, 9),
            valid_to=datetime.date(2025, 7, 8),
        )
        a.tenant.ciclo_fatturazione = TenantProfile.CicloFatturazione.INGRESSO
        a.tenant.save(update_fields=["ciclo_fatturazione"])
        return a

    def test_mensilita_feb_intera(self, assignment_ingresso):
        from billing.calc.rent import genera_pagamenti_mese

        genera_pagamenti_mese(2025, 2)
        p = Receivable.objects.get(causale="affitto")
        assert p.competenza_da == datetime.date(2025, 2, 9)
        assert p.competenza_a == datetime.date(2025, 3, 8)
        assert not p.is_aggiustamento
        assert p.importo_dovuto == Decimal("500.00")
        # Scadenza = 9 feb + 5gg = 14 feb
        assert p.scadenza == datetime.date(2025, 2, 14)

    def test_mensilita_mar_intera(self, assignment_ingresso):
        from billing.calc.rent import genera_pagamenti_mese

        genera_pagamenti_mese(2025, 3)
        p = Receivable.objects.get(causale="affitto")
        assert p.competenza_da == datetime.date(2025, 3, 9)
        assert p.competenza_a == datetime.date(2025, 4, 8)
        assert not p.is_aggiustamento
        assert p.importo_dovuto == Decimal("500.00")

    def test_5_mensilita_totali(self, assignment_ingresso):
        from billing.calc.rent import genera_pagamenti_mese

        for mese in range(2, 8):
            genera_pagamenti_mese(2025, mese)

        records = list(
            Receivable.objects.filter(causale="affitto").order_by("competenza_da")
        )
        assert len(records) == 5
        attesi = [
            (datetime.date(2025, 2, 9), datetime.date(2025, 3, 8)),
            (datetime.date(2025, 3, 9), datetime.date(2025, 4, 8)),
            (datetime.date(2025, 4, 9), datetime.date(2025, 5, 8)),
            (datetime.date(2025, 5, 9), datetime.date(2025, 6, 8)),
            (datetime.date(2025, 6, 9), datetime.date(2025, 7, 8)),
        ]
        for p, (da, a) in zip(records, attesi):
            assert (p.competenza_da, p.competenza_a) == (da, a)
            assert not p.is_aggiustamento
            assert p.importo_dovuto == Decimal("500.00")

    def test_mese_7_nessun_record(self, assignment_ingresso):
        """Mese 7 con valid_to=8/7: competenza_da=9/7 > 8/7 → skip."""
        from billing.calc.rent import genera_pagamenti_mese

        risultato = genera_pagamenti_mese(2025, 7)
        assert risultato["creati"] == 0
        assert Receivable.objects.filter(causale="affitto").count() == 0

    def test_moncone_uscita_prorata(self, db, make_assignment):
        """Uscita 20/7: mensilità 9/7-20/7 = 12 gg su 31 (mens. completa 9/7-8/8)."""
        from billing.calc.rent import genera_pagamenti_mese

        a = make_assignment(
            canone=Decimal("500.00"),
            valid_from=datetime.date(2025, 2, 9),
            valid_to=datetime.date(2025, 7, 20),
        )
        a.tenant.ciclo_fatturazione = TenantProfile.CicloFatturazione.INGRESSO
        a.tenant.save(update_fields=["ciclo_fatturazione"])

        genera_pagamenti_mese(2025, 7)

        p = Receivable.objects.get(causale="affitto")
        assert p.competenza_da == datetime.date(2025, 7, 9)
        assert p.competenza_a == datetime.date(2025, 7, 20)
        assert p.is_aggiustamento
        atteso = (Decimal("500.00") * Decimal(12) / Decimal(31)).quantize(
            Decimal("0.01"), rounding=__import__("decimal").ROUND_HALF_UP
        )
        assert p.importo_dovuto == atteso

    def test_solare_default_non_impattato(self, db, make_assignment):
        """Tenant senza override del ciclo: comportamento solare invariato."""
        from billing.calc.rent import genera_pagamenti_mese

        a = make_assignment(
            canone=Decimal("500.00"),
            valid_from=datetime.date(2025, 2, 9),
        )
        # Niente ciclo_fatturazione: resta default 'solare'
        assert a.tenant.ciclo_fatturazione == TenantProfile.CicloFatturazione.SOLARE

        genera_pagamenti_mese(2025, 2)

        p = Receivable.objects.get(causale="affitto")
        # Solare: competenza 9/2-28/2, pro-rata 20gg/28gg
        assert p.competenza_da == datetime.date(2025, 2, 9)
        assert p.competenza_a == datetime.date(2025, 2, 28)
        assert p.is_aggiustamento


# ---------------------------------------------------------------------------
# Output arricchito: divergenza, contatori diversi/uguali, ordering
# ---------------------------------------------------------------------------


class TestSimulazioneDivergenza:
    """In dry-run, la simulazione segnala se l'importo calcolato divergerebbe
    dall'esistente, sia con force (azione=update) sia senza (azione=skip)."""

    def test_simulazione_segnala_divergenza_con_force(self, db, make_assignment):
        from billing.calc.rent import genera_pagamenti_mese

        a = make_assignment(
            canone=Decimal("500.00"),
            valid_from=datetime.date(2026, 5, 1),
        )
        # Crea il Receivable
        genera_pagamenti_mese(2026, 5)
        # Forza divergenza modificando il canone
        a.canone_mensile = Decimal("600.00")
        a.save(update_fields=["canone_mensile"])

        ris = genera_pagamenti_mese(2026, 5, force=True, persist=False)
        sim = ris["simulazione"]
        assert len(sim) == 1
        assert sim[0]["azione_prevista"] == "update"
        assert sim[0]["divergenza"] is True
        assert sim[0]["importo_esistente"] == Decimal("500.00")
        assert sim[0]["importo_dovuto"] == Decimal("600.00")

    def test_simulazione_segnala_divergenza_senza_force(self, db, make_assignment):
        from billing.calc.rent import genera_pagamenti_mese

        a = make_assignment(
            canone=Decimal("500.00"),
            valid_from=datetime.date(2026, 5, 1),
        )
        genera_pagamenti_mese(2026, 5)
        a.canone_mensile = Decimal("600.00")
        a.save(update_fields=["canone_mensile"])

        ris = genera_pagamenti_mese(2026, 5, force=False, persist=False)
        sim = ris["simulazione"]
        assert len(sim) == 1
        assert sim[0]["azione_prevista"] == "skip"
        assert sim[0]["divergenza"] is True
        assert sim[0]["importo_esistente"] == Decimal("500.00")
        assert sim[0]["importo_dovuto"] == Decimal("600.00")

    def test_simulazione_create_non_ha_divergenza(self, db, make_assignment):
        from billing.calc.rent import genera_pagamenti_mese

        make_assignment(
            canone=Decimal("500.00"),
            valid_from=datetime.date(2026, 5, 1),
        )
        ris = genera_pagamenti_mese(2026, 5, persist=False)
        sim = ris["simulazione"]
        assert len(sim) == 1
        assert sim[0]["azione_prevista"] == "create"
        assert sim[0]["divergenza"] is None
        assert sim[0]["importo_esistente"] is None

    def test_simulazione_skip_uguale_segnala_non_divergenza(
        self, db, make_assignment
    ):
        from billing.calc.rent import genera_pagamenti_mese

        make_assignment(
            canone=Decimal("500.00"),
            valid_from=datetime.date(2026, 5, 1),
        )
        genera_pagamenti_mese(2026, 5)
        # Stesso canone: no divergenza
        ris = genera_pagamenti_mese(2026, 5, persist=False)
        sim = ris["simulazione"]
        assert len(sim) == 1
        assert sim[0]["azione_prevista"] == "skip"
        assert sim[0]["divergenza"] is False


class TestContatoriPersist:
    """Persist con force distingue aggiornati_diversi vs aggiornati_uguali.
    Persist senza force popola skippati_divergenti per importi divergenti."""

    def test_force_conta_diversi_uguali(self, db, make_assignment):
        from billing.calc.rent import genera_pagamenti_mese

        a1 = make_assignment(
            canone=Decimal("500.00"),
            valid_from=datetime.date(2026, 5, 1),
            nominativo="Aaa",
        )
        a2 = make_assignment(
            canone=Decimal("600.00"),
            valid_from=datetime.date(2026, 5, 1),
            nominativo="Bbb",
        )
        genera_pagamenti_mese(2026, 5)

        # Solo a1 cambia canone: divergerà
        a1.canone_mensile = Decimal("510.00")
        a1.save(update_fields=["canone_mensile"])

        ris = genera_pagamenti_mese(2026, 5, force=True)
        assert ris["aggiornati"] == 2
        assert ris["aggiornati_diversi"] == 1
        assert ris["aggiornati_uguali"] == 1

    def test_no_force_popola_skippati_divergenti(self, db, make_assignment):
        from billing.calc.rent import genera_pagamenti_mese

        a1 = make_assignment(
            canone=Decimal("500.00"),
            valid_from=datetime.date(2026, 5, 1),
            nominativo="Aaa",
        )
        a2 = make_assignment(
            canone=Decimal("600.00"),
            valid_from=datetime.date(2026, 5, 1),
            nominativo="Bbb",
        )
        genera_pagamenti_mese(2026, 5)
        a1.canone_mensile = Decimal("510.00")
        a1.save(update_fields=["canone_mensile"])

        ris = genera_pagamenti_mese(2026, 5, force=False)
        # Tutti e 2 skippati (no force), ma solo 1 divergente
        assert ris["skippati"] == 2
        assert len(ris["skippati_divergenti"]) == 1
        div = ris["skippati_divergenti"][0]
        assert div["tenant_nominativo"] == "Aaa"
        assert div["importo_esistente"] == Decimal("500.00")
        assert div["importo_calcolato"] == Decimal("510.00")


class TestDuplicatoAltroAssignment:
    """Quando un tenant ha 2 assignment in continuita' (es. rinnovo) e i
    Receivable storici sono su quello vecchio, il calcolo del nuovo assignment
    deve riconoscerlo come 'create_duplicato' e NON creare un duplicato."""

    @pytest.fixture
    def setup_rinnovo(self, db, make_room, make_tenant):
        """Eshani-like: 1 tenant, 2 assignment back-to-back nella stessa camera."""
        room = make_room()
        t = make_tenant(nominativo="Tenant Rinnovo")
        a1 = RoomAssignment.objects.create(
            room=room, tenant=t,
            valid_from=datetime.date(2025, 1, 1),
            valid_to=datetime.date(2025, 2, 14),
            canone_mensile=Decimal("500.00"),
        )
        a2 = RoomAssignment.objects.create(
            room=room, tenant=t,
            valid_from=datetime.date(2025, 2, 15),
            valid_to=None,
            canone_mensile=Decimal("520.00"),
        )
        # Receivable storico per marzo 2025 linkato (erroneamente) ad a1
        Receivable.objects.create(
            assignment=a1,
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(2025, 3, 1),
            competenza_a=datetime.date(2025, 3, 31),
            importo_dovuto=Decimal("520.00"),
            scadenza=datetime.date(2025, 3, 6),
            stato=StatoPagamento.ATTESO,
        )
        return a1, a2

    def test_dry_run_segnala_create_duplicato(self, setup_rinnovo):
        from billing.calc.rent import genera_pagamenti_mese

        a1, a2 = setup_rinnovo
        ris = genera_pagamenti_mese(2025, 3, persist=False)
        sim = ris["simulazione"]
        # Solo a2 e' attivo nel mese di marzo (a1 finisce 14/2)
        assert len(sim) == 1
        assert sim[0]["azione_prevista"] == "create_duplicato"
        assert sim[0]["altro_importo"] == Decimal("520.00")
        assert sim[0]["altro_assignment_id"] == a1.pk
        assert sim[0]["divergenza"] is False  # importi coincidono

    def test_persist_non_crea_duplicati(self, setup_rinnovo):
        from billing.calc.rent import genera_pagamenti_mese

        a1, a2 = setup_rinnovo
        ris = genera_pagamenti_mese(2025, 3, persist=True)
        # Nessun nuovo Receivable creato
        assert ris["creati"] == 0
        assert ris["aggiornati"] == 0
        assert len(ris["duplicati_altro_assignment"]) == 1
        dup = ris["duplicati_altro_assignment"][0]
        assert dup["assignment_id_corrente"] == a2.pk
        assert dup["assignment_id_esistente"] == a1.pk
        # Il DB resta con 1 solo Receivable (non duplicato)
        assert Receivable.objects.filter(
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(2025, 3, 1),
        ).count() == 1

    def test_dry_run_force_segnala_update_riassocia(self, setup_rinnovo):
        from billing.calc.rent import genera_pagamenti_mese

        a1, a2 = setup_rinnovo
        # a2 ha canone 520, il Receivable storico ha importo 520 → uguale
        ris = genera_pagamenti_mese(2025, 3, force=True, persist=False)
        sim = ris["simulazione"]
        assert len(sim) == 1
        assert sim[0]["azione_prevista"] == "update_riassocia"
        assert sim[0]["altro_assignment_id"] == a1.pk
        assert sim[0]["divergenza"] is False

    def test_persist_force_riassocia_e_aggiorna(self, setup_rinnovo):
        from billing.calc.rent import genera_pagamenti_mese

        a1, a2 = setup_rinnovo
        # Cambio canone di a2 per forzare divergenza importo
        a2.canone_mensile = Decimal("540.00")
        a2.save(update_fields=["canone_mensile"])

        ris = genera_pagamenti_mese(2025, 3, force=True, persist=True)
        assert ris["aggiornati"] == 1
        assert ris["aggiornati_diversi"] == 1
        assert len(ris["rilinkati"]) == 1
        r = ris["rilinkati"][0]
        assert r["old_assignment_id"] == a1.pk
        assert r["new_assignment_id"] == a2.pk
        assert r["importo_pre"] == Decimal("520.00")
        assert r["importo_post"] == Decimal("540.00")

        # Verifica nel DB: il Receivable è stato rilinkato e aggiornato
        rec = Receivable.objects.get(
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(2025, 3, 1),
        )
        assert rec.assignment_id == a2.pk
        assert rec.importo_dovuto == Decimal("540.00")
        # No duplicati creati
        assert Receivable.objects.filter(
            causale=Receivable.Causale.AFFITTO,
            competenza_da=datetime.date(2025, 3, 1),
        ).count() == 1

    def test_force_non_tocca_se_altro_record_e_allocato(self, setup_rinnovo):
        """Anche con force, se il Receivable di un altro assignment è già
        allocato a BankTransaction, NON viene toccato."""
        from billing.calc.rent import genera_pagamenti_mese

        a1, a2 = setup_rinnovo
        recv = Receivable.objects.get(assignment=a1)

        owner_user = User.objects.create_user("owner_dup", email="owner_dup@v.it", password="pwd")
        owner = OwnerProfile.objects.create(user=owner_user, nominativo="Owner Dup")
        owner_account = OwnerBankAccount.objects.create(
            owner=owner, banca="X", intestatario="X",
            iban="IT00X0000000000000000000099",
        )
        bt = BankTransaction.objects.create(
            data=datetime.date(2025, 3, 5),
            descrizione="bonifico",
            importo=recv.importo_dovuto,
            owner_account=owner_account,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=recv, importo=recv.importo_dovuto
        )

        ris = genera_pagamenti_mese(2025, 3, force=True, persist=True)
        recv.refresh_from_db()
        # Non rilinkato, ancora su a1
        assert recv.assignment_id == a1.pk
        assert len(ris["skippati_per_allocation"]) == 1
        assert len(ris["rilinkati"]) == 0


class TestOrderingAssignmentsPerNominativo:
    """Simulazione e generazione iterano in ordine alfabetico di nominativo
    inquilino, per output log deterministico."""

    def test_ordering_simulazione(self, db, make_assignment):
        from billing.calc.rent import genera_pagamenti_mese

        # Creati in ordine non alfabetico
        make_assignment(
            canone=Decimal("500.00"),
            valid_from=datetime.date(2026, 5, 1),
            nominativo="Zorro",
        )
        make_assignment(
            canone=Decimal("500.00"),
            valid_from=datetime.date(2026, 5, 1),
            nominativo="Alpha",
        )
        make_assignment(
            canone=Decimal("500.00"),
            valid_from=datetime.date(2026, 5, 1),
            nominativo="Mike",
        )
        ris = genera_pagamenti_mese(2026, 5, persist=False)
        nominativi = [s["tenant_nominativo"] for s in ris["simulazione"]]
        assert nominativi == ["Alpha", "Mike", "Zorro"]
