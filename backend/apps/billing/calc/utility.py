"""
Calcolo conguaglio utenze per UtilityChargePeriod.

Criterio: pro_rata_giorni (l'unico usato in pratica secondo PLAN.md).
Algoritmo descritto nella docstring di calcola_conguaglio_periodo.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TypedDict


class QuotaInquilino(TypedDict):
    assignment_id: int
    tenant_nominativo: str
    giorni_presenza: int
    quota: Decimal
    dettaglio: dict  # {'luce': Decimal, 'gas': Decimal, 'tari': Decimal, ...}


def _giorni_intersezione(da1: date, a1: date, da2: date, a2: date) -> int:
    """Ritorna il numero di giorni di intersezione tra [da1, a1] e [da2, a2] (inclusivi)."""
    inizio = max(da1, da2)
    fine = min(a1, a2)
    delta = (fine - inizio).days + 1
    return max(0, delta)


def _arrotonda(valore: Decimal) -> Decimal:
    """Arrotonda a 2 decimali con ROUND_HALF_UP."""
    return valore.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _raccoglie_voci_bollette(periodo_da: date, periodo_a: date) -> dict[str, Decimal]:
    """
    Trova le UtilityBill il cui mese di scadenza (data_emissione) cade nel periodo.

    Decisione autonoma: si usa data_emissione come "mese principale" della bolletta,
    in accordo con PLAN.md sezione 3 ("mese di scadenza per default").
    Le bollette bimestrali vengono caricate interamente sul mese di emissione,
    senza pro-rata tra mesi. Smoothing statistico accettato dai proprietari.

    Fornitori mappati su voce:
      - tipo 'energia' -> 'luce'
      - tipo 'gas'     -> 'gas'
      - (altri tipi non sono utenze ripartibili -> ignorati)
    """
    from billing.models import UtilityBill

    TIPO_A_VOCE = {
        "energia": "luce",
        "gas": "gas",
    }

    totali: dict[str, Decimal] = {}

    bills = UtilityBill.objects.filter(
        data_emissione__gte=periodo_da,
        data_emissione__lte=periodo_a,
        supplier__tipo__in=list(TIPO_A_VOCE.keys()),
    ).select_related("supplier")

    for bill in bills:
        voce = TIPO_A_VOCE[bill.supplier.tipo]
        totali[voce] = totali.get(voce, Decimal("0.00")) + bill.importo_totale

    return totali


def _raccoglie_voci_annual(periodo_da: date, periodo_a: date) -> dict[str, Decimal]:
    """
    Calcola la quota TARI (AnnualUtilityCost) proporzionale ai giorni del periodo.

    Formula: importo_annuale * giorni_intersezione / 365
    Se ci sono piu' record TARI sovrapposti (raro), li somma.
    """
    from billing.models import AnnualUtilityCost

    totali: dict[str, Decimal] = {}
    giorni_periodo = (periodo_a - periodo_da).days + 1

    annual_costs = AnnualUtilityCost.objects.filter(
        valid_from__lte=periodo_a,
    ).filter(
        # valid_to IS NULL oppure valid_to >= periodo_da
        valid_to__isnull=True,
    ) | AnnualUtilityCost.objects.filter(
        valid_from__lte=periodo_a,
        valid_to__gte=periodo_da,
    )
    # Dedup (union potrebbe creare duplicati in edge case)
    annual_costs = annual_costs.distinct()

    for ac in annual_costs:
        # Intersezione tra [periodo_da, periodo_a] e [ac.valid_from, ac.valid_to o inf]
        ac_to = ac.valid_to if ac.valid_to else date(9999, 12, 31)
        giorni_intersezione = _giorni_intersezione(periodo_da, periodo_a, ac.valid_from, ac_to)
        if giorni_intersezione <= 0:
            continue

        quota = ac.importo_annuale * Decimal(giorni_intersezione) / Decimal(365)
        voce = ac.voce  # es. 'tari'
        totali[voce] = totali.get(voce, Decimal("0.00")) + quota

    return totali


def calcola_conguaglio_periodo(period_id: int, persist: bool = False) -> dict:
    """
    Calcola la ripartizione di un UtilityChargePeriod fra i RoomAssignment
    attivi (anche parzialmente) nel periodo, con criterio pro_rata_giorni.

    Algoritmo:
    1. Determina periodo_da/periodo_a dal UtilityChargePeriod
    2. Trova UtilityBill collegate (supplier in [energia, gas]) il cui
       periodo principale (= data_emissione per default) cade nel periodo.
       Se manual_totals sono presenti nel period, usa quelli invece di
       bollette e AnnualUtilityCost.
    3. Calcola quota TARI: per ogni AnnualUtilityCost attivo nel periodo,
       quota = importo_annuale * giorni_intersezione / 365
    4. Per ogni RoomAssignment overlap col periodo, calcola
       giorni_presenza = giorni di intersezione
    5. sum_giorni = somma giorni_presenza di tutti gli assignment
    6. costo_per_giorno_persona = totale_voce / sum_giorni (per ciascuna voce)
    7. quota_inquilino_per_voce = costo_per_giorno_persona * giorni_presenza
    8. importo_totale_inquilino = somma quote per voce, ROUND_HALF_UP

    Se persist=True: crea/aggiorna i UtilityCharge + UtilityChargeLine
    (un record per assignment, con line per voce).
    Idempotente: update_or_create sulla coppia (period, assignment).

    Ritorna:
    {
        "period_id": ..., "periodo_da": ..., "periodo_a": ...,
        "totale_periodo": Decimal,           # somma di tutte le voci
        "totali_per_voce": {"luce": ..., "gas": ..., "tari": ...},
        "sum_giorni_presenza": int,
        "quote": [QuotaInquilino, ...],
        "diff_arrotondamento": Decimal       # totale_periodo - somma(quote)
    }
    """
    from billing.models import UtilityChargePeriod
    from properties.models import RoomAssignment

    period = UtilityChargePeriod.objects.get(pk=period_id)
    periodo_da: date = period.periodo_da
    periodo_a: date = period.periodo_a

    # --- Passo 1: raccolta voci ---
    if period.manual_totals:
        # Import storico: manual_totals e' un dict {"luce": "100.00", "gas": "80.00", ...}
        totali_per_voce: dict[str, Decimal] = {
            voce: Decimal(str(importo))
            for voce, importo in period.manual_totals.items()
        }
    else:
        # Bollette fornitori (luce, gas)
        totali_per_voce = _raccoglie_voci_bollette(periodo_da, periodo_a)
        # TARI e altri costi annuali
        totali_annual = _raccoglie_voci_annual(periodo_da, periodo_a)
        for voce, importo in totali_annual.items():
            totali_per_voce[voce] = totali_per_voce.get(voce, Decimal("0.00")) + importo

    totale_periodo = sum(totali_per_voce.values(), Decimal("0.00"))

    # --- Passo 2: assignment attivi (overlap col periodo) ---
    # Un assignment e' attivo nel periodo se:
    #   valid_from <= periodo_a AND (valid_to IS NULL OR valid_to >= periodo_da)
    assignments_qs = RoomAssignment.objects.filter(
        valid_from__lte=periodo_a,
    ).filter(
        valid_to__isnull=True,
    ) | RoomAssignment.objects.filter(
        valid_from__lte=periodo_a,
        valid_to__gte=periodo_da,
    )
    assignments_qs = assignments_qs.distinct().select_related("tenant")

    # --- Passo 3: giorni di presenza per assignment ---
    presenze: list[tuple] = []  # [(assignment, giorni_presenza)]
    for assignment in assignments_qs:
        a_to = assignment.valid_to if assignment.valid_to else date(9999, 12, 31)
        giorni = _giorni_intersezione(periodo_da, periodo_a, assignment.valid_from, a_to)
        if giorni > 0:
            presenze.append((assignment, giorni))

    sum_giorni = sum(g for _, g in presenze)

    # --- Passo 4: calcolo quote ---
    quote: list[QuotaInquilino] = []

    for assignment, giorni_presenza in presenze:
        dettaglio: dict[str, Decimal] = {}
        quota_totale = Decimal("0.00")

        for voce, totale_voce in totali_per_voce.items():
            if sum_giorni == 0:
                quota_voce = Decimal("0.00")
            else:
                costo_giorno = totale_voce / Decimal(sum_giorni)
                quota_voce = _arrotonda(costo_giorno * Decimal(giorni_presenza))
            dettaglio[voce] = quota_voce
            quota_totale += quota_voce

        quota_totale = _arrotonda(quota_totale)

        quote.append(
            QuotaInquilino(
                assignment_id=assignment.pk,
                tenant_nominativo=assignment.tenant.nominativo,
                giorni_presenza=giorni_presenza,
                quota=quota_totale,
                dettaglio=dettaglio,
            )
        )

    # --- Passo 5: differenza di arrotondamento ---
    somma_quote = sum(q["quota"] for q in quote)
    diff_arrotondamento = _arrotonda(totale_periodo - somma_quote)

    # --- Passo 6: persist (se richiesto) ---
    if persist:
        _persist_charges(period, quote, totali_per_voce, periodo_da)

    return {
        "period_id": period_id,
        "periodo_da": periodo_da,
        "periodo_a": periodo_a,
        "totale_periodo": _arrotonda(totale_periodo),
        "totali_per_voce": {v: _arrotonda(i) for v, i in totali_per_voce.items()},
        "sum_giorni_presenza": sum_giorni,
        "quote": quote,
        "diff_arrotondamento": diff_arrotondamento,
    }


def _persist_charges(period, quote: list[QuotaInquilino], totali_per_voce: dict, periodo_da: date) -> None:
    """
    Crea o aggiorna UtilityCharge + UtilityChargeLine per ogni assignment.
    Idempotente tramite update_or_create sulla coppia (period, assignment).

    Scadenza: data_invio + 5gg se presente, altrimenti primo del mese successivo + 5gg.
    """
    from datetime import timedelta
    import calendar

    from billing.models import UtilityCharge, UtilityChargeLine
    from properties.models import RoomAssignment

    # Calcola scadenza
    if period.data_invio:
        scadenza = period.data_invio + timedelta(days=5)
    else:
        # Primo del mese successivo + 5gg
        anno = periodo_da.year
        mese = periodo_da.month
        if mese == 12:
            anno += 1
            mese = 1
        else:
            mese += 1
        scadenza = date(anno, mese, 1) + timedelta(days=5)

    for q in quote:
        assignment = RoomAssignment.objects.get(pk=q["assignment_id"])

        charge, _ = UtilityCharge.objects.update_or_create(
            period=period,
            assignment=assignment,
            defaults={
                "importo_totale": q["quota"],
                "scadenza": scadenza,
            },
        )

        # Ricrea le righe: cancella le esistenti e reinserisce
        charge.lines.all().delete()
        for voce, importo in q["dettaglio"].items():
            UtilityChargeLine.objects.create(
                charge=charge,
                voce=voce,
                importo=importo,
                dettaglio=(
                    f"Quota pro-rata {q['giorni_presenza']} giorni su "
                    f"{(period.periodo_a - period.periodo_da).days + 1}"
                ),
            )
