"""
Test di `pin_bollette_periodi_emessi`: riempire la M2M dei periodi già emessi
senza toccare un solo importo.

I periodi nati dagli import hanno i `tot_*` ma nessuna bolletta agganciata:
l'abbinamento vive solo come calcolo al volo. Il comando lo rende dato — anche
per le bimestrali, agganciate a entrambi i mesi che coprono — e si ferma dove
il pinning allontanerebbe il ricalcolo da quanto fu davvero addebitato.
"""
import datetime
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def _bolletta(immobile, prodotto, importo, da, a, numero=None):
    from billing.models import Supplier, UtilityBill

    supplier, _ = Supplier.objects.get_or_create(
        property=immobile,
        nome=f"Forn-{prodotto}",
        defaults={"tipo": Supplier.TipoFornitore.ALTRO},
    )
    return UtilityBill.objects.create(
        immobile=immobile,
        supplier=supplier,
        prodotto=prodotto,
        numero_fattura=numero or f"{prodotto}-{da}",
        data_emissione=a,
        periodo_da=da,
        periodo_a=a,
        importo_totale=Decimal(importo),
    )


def _periodo_emesso(immobile, da, a, luce="0.00", gas="0.00"):
    from billing.models import UtilityChargePeriod

    return UtilityChargePeriod.objects.create(
        property=immobile,
        periodo_da=da,
        periodo_a=a,
        stato=UtilityChargePeriod.StatoPeriodo.INVIATO,
        tot_luce=Decimal(luce),
        tot_gas=Decimal(gas),
    )


def _run(**kwargs):
    out = StringIO()
    call_command("pin_bollette_periodi_emessi", stdout=out, **kwargs)
    return out.getvalue()


class TestPinPeriodiEmessi:
    def test_pinna_e_non_cambia_gli_importi(self, immobile):
        from billing.calc.utility import calcola_conguaglio_periodo

        p = _periodo_emesso(
            immobile,
            datetime.date(2025, 9, 1), datetime.date(2025, 9, 30),
            luce="153.27", gas="22.21",
        )
        luce = _bolletta(
            immobile, "luce", "153.27",
            datetime.date(2025, 9, 1), datetime.date(2025, 9, 30),
        )
        gas = _bolletta(
            immobile, "gas", "22.21",
            datetime.date(2025, 9, 1), datetime.date(2025, 9, 30),
        )
        prima = calcola_conguaglio_periodo(p.pk, persist=False)["totali_per_voce"]

        out = _run(property=str(immobile.pk), apply=True)

        assert set(p.utility_bills.values_list("pk", flat=True)) == {luce.pk, gas.pk}
        dopo = calcola_conguaglio_periodo(p.pk, persist=False)["totali_per_voce"]
        assert dopo == prima, out

    def test_dry_run_non_scrive(self, immobile):
        p = _periodo_emesso(
            immobile,
            datetime.date(2025, 9, 1), datetime.date(2025, 9, 30),
            luce="153.27",
        )
        _bolletta(
            immobile, "luce", "153.27",
            datetime.date(2025, 9, 1), datetime.date(2025, 9, 30),
        )

        out = _run(property=str(immobile.pk))

        assert p.utility_bills.count() == 0
        assert "pin 1" in out and "--apply" in out

    def test_bimestrale_agganciata_a_entrambi_i_mesi(self, immobile):
        """La bolletta che copre due periodi appartiene a entrambi: agganciata
        a tutti e due, si ripartisce pro-rata e la somma resta l'intero."""
        from billing.calc.utility import calcola_conguaglio_periodo

        p1 = _periodo_emesso(
            immobile,
            datetime.date(2025, 1, 1), datetime.date(2025, 1, 31),
            luce="100.00", gas="31.00",
        )
        p2 = _periodo_emesso(
            immobile,
            datetime.date(2025, 2, 1), datetime.date(2025, 2, 28),
            luce="100.00", gas="28.00",
        )
        _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 1, 1), datetime.date(2025, 1, 31), numero="L1",
        )
        _bolletta(
            immobile, "luce", "100.00",
            datetime.date(2025, 2, 1), datetime.date(2025, 2, 28), numero="L2",
        )
        gas = _bolletta(
            immobile, "gas", "59.00",
            datetime.date(2025, 1, 1), datetime.date(2025, 2, 28), numero="G-BIM",
        )

        _run(property=str(immobile.pk), apply=True)

        assert gas.pk in p1.utility_bills.values_list("pk", flat=True)
        assert gas.pk in p2.utility_bills.values_list("pk", flat=True)
        # 59 € su 59 giorni: 31 a gennaio, 28 a febbraio. Niente doppioni.
        g1 = calcola_conguaglio_periodo(p1.pk, persist=False)["totali_per_voce"]["gas"]
        g2 = calcola_conguaglio_periodo(p2.pk, persist=False)["totali_per_voce"]["gas"]
        assert g1 == Decimal("31.00"), g1
        assert g2 == Decimal("28.00"), g2
        assert g1 + g2 == Decimal("59.00")

    def test_salta_il_periodo_a_cui_manca_una_bolletta(self, immobile):
        """tot_gas addebitato ma nessuna bolletta gas a DB: manca il dato."""
        p = _periodo_emesso(
            immobile,
            datetime.date(2024, 1, 1), datetime.date(2024, 2, 29),
            luce="230.00", gas="69.00",
        )
        _bolletta(
            immobile, "luce", "230.00",
            datetime.date(2024, 1, 1), datetime.date(2024, 2, 29),
        )

        out = _run(property=str(immobile.pk), apply=True)

        assert p.utility_bills.count() == 0
        assert "manca il dato" in out

    def test_idempotente(self, immobile):
        p = _periodo_emesso(
            immobile,
            datetime.date(2025, 9, 1), datetime.date(2025, 9, 30),
            luce="153.27",
        )
        _bolletta(
            immobile, "luce", "153.27",
            datetime.date(2025, 9, 1), datetime.date(2025, 9, 30),
        )
        _run(property=str(immobile.pk), apply=True)
        agganciate = set(p.utility_bills.values_list("pk", flat=True))

        out = _run(property=str(immobile.pk), apply=True)

        assert set(p.utility_bills.values_list("pk", flat=True)) == agganciate
        assert "senza bollette agganciate: 0" in out
