"""Sanifica le UB e i UtilityChargePeriod 2023 secondo `ContiAffittoUtenze.xlsx > 2023`.

Eseguire dalla cartella backend con:

    uv run manage.py shell < scripts/sanifica_utenze_2023.py

Idempotente: le UB nuove portano `numero_fattura` con marker
`utenze2023-libromano-<voce>-<MM-MM>`; il riaggancio M2M è un `set` quindi
non duplica.

Cosa fa
-------
Per ogni period 2023 (143-148, tutti `inviato` con tot_* gia' coerenti col
foglio):

* crea le UB luce/gas mancanti per giustificare i tot_* (importi dal foglio);
* aggancia via M2M `period.utility_bills` le UB del foglio (nuove o
  esistenti dalla fase 4) + l'AnnualUtilityCost TARI 2023.

Lascia intoccate le UB 190/191/192 (segnaposto aggregati dal libro mano
`conti 2023`, pre-voltura): restano come traccia del pagamento di Bruna,
fuori dalla M2M dei period quindi escluse dal calc (modalita' pinning).
"""
from decimal import Decimal
from datetime import date

from billing.models import (
    AnnualUtilityCost,
    Supplier,
    UtilityBill,
    UtilityChargePeriod,
)

MARKER_PREFIX = "utenze2023-libromano"

# (period_da, period_a, etichetta_mese_per_marker, luce, gas)
RIGHE_FOGLIO = [
    (date(2023, 2, 1),  date(2023, 2, 28), "02-02", Decimal("54.84"),  Decimal("18.70")),
    (date(2023, 3, 1),  date(2023, 4, 30), "03-04", Decimal("193.00"), Decimal("53.56")),
    (date(2023, 5, 1),  date(2023, 6, 30), "05-06", Decimal("180.28"), Decimal("50.95")),
    (date(2023, 7, 1),  date(2023, 8, 31), "07-08", Decimal("147.08"), Decimal("51.61")),
    (date(2023, 9, 1),  date(2023, 10, 31), "09-10", Decimal("219.20"), Decimal("57.48")),
    (date(2023, 11, 1), date(2023, 12, 31), "11-12", Decimal("251.39"), Decimal("59.63")),
]


def _supplier_sconosciuto():
    s, _ = Supplier.objects.get_or_create(
        nome="Sconosciuto",
        defaults={"tipo": Supplier.TipoFornitore.ALTRO},
    )
    return s


def _trova_ub_esistente(prodotto, periodo_da, periodo_a, importo, tolleranza=Decimal("1.00")):
    """Cerca una UB del 2023 con stesso prodotto e importo ~uguale che
    intersechi il bimestre [periodo_da, periodo_a]. Serve per evitare di
    creare doppioni quando una bolletta gia' a DB (es. UB 145 ago=147.08)
    deve essere agganciata al period bimestrale lug-ago."""
    candidate = UtilityBill.objects.filter(
        prodotto=prodotto,
        periodo_da__lte=periodo_a,
        periodo_a__gte=periodo_da,
    ).exclude(
        # esclude le 190/191/192 aggregate da conti 2023 (luce-segnaposto)
        numero_fattura__startswith="conti2023-bolletta-riga"
    )
    for b in candidate:
        if abs(b.importo_totale - importo) <= tolleranza:
            return b
    return None


def _crea_o_aggiorna_ub_libromano(prodotto, periodo_da, periodo_a, importo, etichetta):
    """Crea o aggiorna la UB sintetica dal libro mano UTENZE."""
    nf = f"{MARKER_PREFIX}-{prodotto}-{etichetta}"
    nota = (
        f"Bolletta ricostruita dal libro mano UTENZE "
        f"(dati/ContiAffittoUtenze.xlsx > 2023): scomposizione manuale di "
        f"Bruna in luce/gas per il calcolo del dovuto inquilini. Nessun PDF, "
        f"nessuna Expense generata. Importo dal foglio."
    )
    bill = UtilityBill.objects.filter(numero_fattura=nf).first()
    azione = "aggiornata" if bill else "creata"
    if bill is None:
        bill = UtilityBill(numero_fattura=nf)
    bill.numero_fattura = nf
    bill.supplier = _supplier_sconosciuto()
    bill.prodotto = prodotto
    bill.data_emissione = periodo_a
    bill.periodo_da = periodo_da
    bill.periodo_a = periodo_a
    bill.importo_totale = importo
    bill.pagata_da_owner = None
    bill.note = nota
    bill.save()
    return bill, azione


def main():
    tari_2023 = AnnualUtilityCost.objects.filter(
        voce="tari", valid_from__year__lte=2023,
    ).order_by("-valid_from").first()
    if tari_2023 is None:
        print("ATTENZIONE: nessun AnnualUtilityCost TARI 2023 trovato")
    else:
        print(f"AC TARI 2023: id={tari_2023.pk}, "
              f"importo_annuale={tari_2023.importo_annuale}, "
              f"valid {tari_2023.valid_from}->{tari_2023.valid_to}")
    print()

    for periodo_da, periodo_a, etichetta, luce, gas in RIGHE_FOGLIO:
        period = UtilityChargePeriod.objects.filter(
            periodo_da=periodo_da, periodo_a=periodo_a,
        ).first()
        if period is None:
            print(f"  SKIP period {periodo_da}->{periodo_a}: non esiste a DB")
            continue
        print(f"period {period.pk}  {periodo_da}->{periodo_a}  stato={period.stato}")

        ub_luce = _trova_ub_esistente("luce", periodo_da, periodo_a, luce)
        if ub_luce:
            print(f"  luce: usa UB {ub_luce.pk} esistente "
                  f"({ub_luce.periodo_da}->{ub_luce.periodo_a} {ub_luce.importo_totale}€)")
        else:
            ub_luce, azione = _crea_o_aggiorna_ub_libromano(
                "luce", periodo_da, periodo_a, luce, etichetta,
            )
            print(f"  luce: UB {ub_luce.pk} {azione} (importo {ub_luce.importo_totale}€)")

        ub_gas = _trova_ub_esistente("gas", periodo_da, periodo_a, gas)
        if ub_gas:
            print(f"  gas:  usa UB {ub_gas.pk} esistente "
                  f"({ub_gas.periodo_da}->{ub_gas.periodo_a} {ub_gas.importo_totale}€)")
        else:
            ub_gas, azione = _crea_o_aggiorna_ub_libromano(
                "gas", periodo_da, periodo_a, gas, etichetta,
            )
            print(f"  gas:  UB {ub_gas.pk} {azione} (importo {ub_gas.importo_totale}€)")

        period.utility_bills.set([ub_luce, ub_gas])
        if tari_2023 is not None:
            period.annual_utility_costs.set([tari_2023])
        print(f"  M2M agganciate: bills=[{ub_luce.pk}, {ub_gas.pk}]  ac=[{tari_2023.pk if tari_2023 else '—'}]")


main()
