"""
Calcolo utenze per UtilityChargePeriod.

Criterio: pro_rata_giorni (l'unico usato in pratica secondo PLAN.md).
Algoritmo descritto nella docstring di calcola_conguaglio_periodo.
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TypedDict

VOCI_FATTURABILI = ("luce", "gas")


class QuotaInquilino(TypedDict, total=False):
    assignment_id: int
    tenant_nominativo: str
    giorni_presenza: int
    quota: Decimal
    dettaglio: dict  # {'luce': Decimal, 'gas': Decimal, 'tari': Decimal, ...}
    importo_esistente: Decimal | None  # Receivable utenze gia' presente per (period, assignment)


def _giorni_intersezione(da1: date, a1: date, da2: date, a2: date) -> int:
    """Ritorna il numero di giorni di intersezione tra [da1, a1] e [da2, a2] (inclusivi)."""
    inizio = max(da1, da2)
    fine = min(a1, a2)
    delta = (fine - inizio).days + 1
    return max(0, delta)


def _arrotonda(valore: Decimal) -> Decimal:
    """Arrotonda a 2 decimali con ROUND_HALF_UP."""
    return valore.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _attribuisci_bollette(period) -> tuple[dict[str, Decimal], list]:
    """Decide quali UtilityBill contribuiscono a `period` e con quale importo.

    Regola **semplice e locale**: un periodo prende solo le bollette il cui
    intervallo ``[periodo_da, periodo_a]`` si sovrappone al periodo, in pro-rata
    sui giorni di sovrapposizione fra bolletta e periodo. Una bolletta non
    finisce mai su un mese che non copre: niente "ribaltamento" di bollette in
    ritardo su mesi futuri, e il calcolo di un periodo NON dipende da quali
    altri periodi esistono o sono chiusi. Una bolletta che copre N mesi viene
    ripartita su quei mesi: la somma delle quote = importo della bolletta.

    Restituisce ``(contributi_per_voce, bollette_utilizzate)``:
      - ``contributi_per_voce``: ``{"luce": Decimal, "gas": Decimal}`` per il periodo.
      - ``bollette_utilizzate``: bollette da agganciare alla M2M ``utility_bills``.

    Override manuale (pinning): se ``period.utility_bills`` è già popolata, quelle
    bollette valgono per l'importo intero (verità manuale, no pro-rata). Le
    bollette già pinnate da un altro periodo ``inviato`` sono escluse, per non
    riconteggiare una bolletta già attribuita altrove.
    """
    from billing.models import UtilityBill, UtilityChargePeriod

    P_da: date = period.periodo_da
    P_a: date = period.periodo_a
    INVIATO = UtilityChargePeriod.StatoPeriodo.INVIATO

    # Modalità pinning: la M2M è "verità manuale". Se popolata, ogni bolletta
    # agganciata cade intera sul periodo (no pro-rata).
    pinned = list(period.utility_bills.filter(prodotto__in=VOCI_FATTURABILI))
    if pinned:
        contributi: dict[str, Decimal] = {}
        for b in pinned:
            contributi[b.prodotto] = (
                contributi.get(b.prodotto, Decimal("0.00")) + b.importo_totale
            )
        return contributi, pinned

    # Bollette già consumate (M2M) da un altro periodo inviato: escluse, per non
    # riconteggiare una bolletta che un altro periodo ha già pinnato.
    consumed_ids = set(
        UtilityBill.objects.filter(periods__stato=INVIATO)
        .exclude(periods__pk=period.pk)
        .values_list("pk", flat=True)
    )

    contributi: dict[str, Decimal] = {}
    bollette_usate: list = []

    # Solo le bollette che si sovrappongono al periodo:
    # periodo_da <= P_a AND periodo_a >= P_da.
    bills = (
        UtilityBill.objects.filter(
            immobile_id=period.property_id,
            prodotto__in=VOCI_FATTURABILI,
            periodo_da__lte=P_a,
            periodo_a__gte=P_da,
        )
        .exclude(pk__in=consumed_ids)
    )

    for bill in bills:
        giorni_bolletta = (bill.periodo_a - bill.periodo_da).days + 1
        giorni_in_P = _giorni_intersezione(bill.periodo_da, bill.periodo_a, P_da, P_a)
        if giorni_in_P <= 0 or giorni_bolletta <= 0:
            continue
        if giorni_in_P >= giorni_bolletta:
            quota = bill.importo_totale  # bolletta interamente dentro il periodo
        else:
            quota = (
                bill.importo_totale * Decimal(giorni_in_P) / Decimal(giorni_bolletta)
            )
        contributi[bill.prodotto] = (
            contributi.get(bill.prodotto, Decimal("0.00")) + quota
        )
        bollette_usate.append(bill)

    return contributi, bollette_usate


def _mesi_coperti(da: date, a: date) -> int:
    """Numero di mesi calendario toccati dall'intervallo ``[da, a]`` inclusivo.

    Un periodo mensile (es. 1-30 apr) → 1; un bimestrale (1 gen - 28 feb) → 2.
    """
    if a < da:
        return 0
    return (a.year - da.year) * 12 + (a.month - da.month) + 1


def _raccoglie_voci_annual(property_id: int, periodo_da: date, periodo_a: date) -> dict[str, Decimal]:
    """
    Calcola la quota TARI (AnnualUtilityCost) per il periodo corrente.

    Regola (scelta Sandro 2026-05-31): la TARI annua è **1/12 al mese**, fissa,
    indipendente dai giorni del mese e da quanti altri periodi esistono. Un
    periodo che copre N mesi prende N/12 dell'importo annuale; la somma sui 12
    mesi dell'anno fa esattamente l'importo annuale.

        quota = importo_annuale / 12 × mesi_coperti_dal_periodo

    Il calcolo è **locale al periodo**: non dipende da quali altri periodi sono
    stati creati o emessi (coerente con l'attribuzione delle bollette).
    """
    from billing.models import AnnualUtilityCost

    totali: dict[str, Decimal] = {}

    annual_costs = AnnualUtilityCost.objects.filter(
        property_id=property_id,
        valid_from__lte=periodo_a,
    ).filter(
        valid_to__isnull=True,
    ) | AnnualUtilityCost.objects.filter(
        property_id=property_id,
        valid_from__lte=periodo_a,
        valid_to__gte=periodo_da,
    )
    annual_costs = annual_costs.distinct()

    for ac in annual_costs:
        ac_to = ac.valid_to if ac.valid_to else date(9999, 12, 31)
        # Mesi del periodo che cadono nella validità di questo costo annuale.
        inizio = max(periodo_da, ac.valid_from)
        fine = min(periodo_a, ac_to)
        mesi = _mesi_coperti(inizio, fine)
        if mesi <= 0:
            continue

        quota = ac.importo_annuale / Decimal(12) * Decimal(mesi)
        totali[ac.voce] = totali.get(ac.voce, Decimal("0.00")) + quota

    return totali


def calcola_conguaglio_periodo(
    period_id: int,
    persist: bool = False,
    tenant_id: int | None = None,
) -> dict:
    """
    Calcola la ripartizione di un UtilityChargePeriod fra i RoomAssignment
    attivi (anche parzialmente) nel periodo, con criterio pro_rata_giorni.

    Algoritmo:
    1. Determina periodo_da/periodo_a dal UtilityChargePeriod
    2. Trova UtilityBill collegate (supplier in [energia, gas]) il cui
       periodo principale (= data_emissione per default) cade nel periodo.
    3. Calcola quota TARI: per ogni AnnualUtilityCost attivo nel periodo,
       quota = importo_annuale / 12 * mesi_coperti_dal_periodo
    4. Per ogni RoomAssignment overlap col periodo, calcola
       giorni_presenza = giorni di intersezione
    5. sum_giorni = somma giorni_presenza di tutti gli assignment
    6. costo_per_giorno_persona = totale_voce / sum_giorni (per ciascuna voce)
    7. quota_inquilino_per_voce = costo_per_giorno_persona * giorni_presenza
    8. importo_totale_inquilino = somma quote per voce, ROUND_HALF_UP

    Se persist=True: popola i totali per voce + giorni_totali sul Period e
    crea/aggiorna i Receivable utenze (uno per assignment) con giorni_presenza.
    Idempotente: update_or_create sulla coppia (period, assignment).

    Nota: i giorni di presenza si calcolano sempre come pro-rata sui giorni
    effettivi di occupazione (``RoomAssignment.valid_from``/``valid_to``),
    indipendentemente da ``TenantProfile.ciclo_fatturazione``. Il
    ciclo_fatturazione vale solo per gli affitti (vedi ``calc/rent.py``):
    le utenze sono sempre pro-rata sui giorni.

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

    # --- Passo 1: attribuzione bollette al periodo ---
    contributi, bollette_usate = _attribuisci_bollette(period)
    # Regola Sandro 2026-05-02: non emettere conguagli "solo TARI". I conguagli
    # vanno emessi solo quando c'e' almeno una bolletta luce/gas. Se manca,
    # il periodo viene saltato del tutto.
    if not contributi:
        if persist and period.receivables.exists():
            period.receivables.all().delete()
        if persist:
            period.utility_bills.clear()
        return {
            "period_id": period_id,
            "periodo_da": periodo_da,
            "periodo_a": periodo_a,
            "totale_periodo": Decimal("0.00"),
            "totali_per_voce": {},
            "sum_giorni_presenza": 0,
            "quote": [],
            "diff_arrotondamento": Decimal("0.00"),
            "skipped": "no_bollette_luce_gas",
        }
    totali_per_voce: dict[str, Decimal] = dict(contributi)
    # TARI e altri costi annuali (aggiunti solo se ci sono bollette)
    totali_annual = _raccoglie_voci_annual(period.property_id, periodo_da, periodo_a)
    for voce, importo in totali_annual.items():
        totali_per_voce[voce] = totali_per_voce.get(voce, Decimal("0.00")) + importo

    totale_periodo = sum(totali_per_voce.values(), Decimal("0.00"))

    # --- Passo 2: assignment attivi (overlap col periodo) ---
    # Un assignment e' attivo nel periodo se:
    #   valid_from <= periodo_a AND (valid_to IS NULL OR valid_to >= periodo_da)
    assignments_qs = RoomAssignment.objects.filter(
        room__property_id=period.property_id,
        valid_from__lte=periodo_a,
    ).filter(
        valid_to__isnull=True,
    ) | RoomAssignment.objects.filter(
        room__property_id=period.property_id,
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

    # Ordine deterministico (per output log e quote stabili).
    presenze.sort(key=lambda x: x[0].tenant.nominativo)

    sum_giorni = sum(g for _, g in presenze)

    # Importi gia' presenti (per segnalare divergenze in dry-run e contatori
    # diversi/uguali in persist). Una sola query, mappa per assignment_id.
    from billing.models import Receivable

    receivables_esistenti = {
        r.assignment_id: r.importo_dovuto
        for r in Receivable.objects.filter(
            utility_period=period,
            causale=Receivable.Causale.UTENZE,
        )
    }

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
                importo_esistente=receivables_esistenti.get(assignment.pk),
            )
        )

    # --- Passo 5: differenza di arrotondamento ---
    somma_quote = sum(q["quota"] for q in quote)
    diff_arrotondamento = _arrotonda(totale_periodo - somma_quote)

    # Filtro single-tenant (debug): denominatore e totali restano interi (così
    # le quote dei singoli sono comunque corrette), ma persist e return
    # vengono limitati al tenant richiesto.
    if tenant_id is not None:
        ass_ids_tenant = set(
            RoomAssignment.objects.filter(tenant_id=tenant_id).values_list("pk", flat=True)
        )
        quote = [q for q in quote if q["assignment_id"] in ass_ids_tenant]

    # --- Passo 6: persist (se richiesto) ---
    skippati_per_allocation: list[dict] = []
    persist_stats: dict = {
        "creati": 0,
        "aggiornati_diversi": 0,
        "aggiornati_uguali": 0,
    }
    if persist:
        persist_result = _persist_receivables(
            period, quote, totali_per_voce, periodo_da, sum_giorni, bollette_usate
        )
        skippati_per_allocation = persist_result["skippati_per_allocation"]
        persist_stats = {
            "creati": persist_result["creati"],
            "aggiornati_diversi": persist_result["aggiornati_diversi"],
            "aggiornati_uguali": persist_result["aggiornati_uguali"],
        }

    return {
        "period_id": period_id,
        "periodo_da": periodo_da,
        "periodo_a": periodo_a,
        "totale_periodo": _arrotonda(totale_periodo),
        "totali_per_voce": {v: _arrotonda(i) for v, i in totali_per_voce.items()},
        "sum_giorni_presenza": sum_giorni,
        "quote": quote,
        "diff_arrotondamento": diff_arrotondamento,
        "skippati_per_allocation": skippati_per_allocation,
        **persist_stats,
    }


def _persist_receivables(
    period,
    quote: list[QuotaInquilino],
    totali_per_voce: dict,
    periodo_da: date,
    sum_giorni: int,
    bollette_usate: list | None = None,
) -> list[dict]:
    """
    Crea o aggiorna Receivable(causale=utenze) per ogni assignment del periodo
    e popola i totali per voce + giorni_totali sul periodo stesso.
    Idempotente sulla coppia (utility_period, assignment).

    Aggancia inoltre le bollette utilizzate (``bollette_usate``) alla M2M
    ``period.utility_bills`` (set, non add): è la registrazione persistente
    di "questo periodo ha consumato queste bollette", usata dal calcolo dei
    periodi successivi per non doppiare l'addebito.

    Scadenza: data_invio + 5gg se presente, altrimenti primo del mese successivo + 5gg.

    Guardia integrità: se un Receivable già esistente ha BankTransactionAllocation
    associate, NON viene aggiornato. Il record viene aggiunto alla lista di ritorno
    per segnalazione al chiamante.
    """
    from billing.models import Receivable
    from properties.models import RoomAssignment

    if period.data_invio:
        scadenza = period.data_invio + timedelta(days=5)
    else:
        anno = periodo_da.year
        mese = periodo_da.month
        if mese == 12:
            anno += 1
            mese = 1
        else:
            mese += 1
        scadenza = date(anno, mese, 1) + timedelta(days=5)

    period.tot_luce = _arrotonda(totali_per_voce.get("luce", Decimal("0.00")))
    period.tot_gas = _arrotonda(totali_per_voce.get("gas", Decimal("0.00")))
    period.tot_tari = _arrotonda(totali_per_voce.get("tari", Decimal("0.00")))
    period.tot_altro = _arrotonda(
        sum(
            (v for k, v in totali_per_voce.items() if k not in ("luce", "gas", "tari")),
            Decimal("0.00"),
        )
    )
    period.giorni_totali = sum_giorni
    period.save(update_fields=["tot_luce", "tot_gas", "tot_tari", "tot_altro", "giorni_totali"])

    if bollette_usate is not None:
        period.utility_bills.set(bollette_usate)

    skippati: list[dict] = []
    creati = 0
    aggiornati_diversi = 0
    aggiornati_uguali = 0

    for q in quote:
        assignment = RoomAssignment.objects.get(pk=q["assignment_id"])

        existing = Receivable.objects.filter(
            utility_period=period,
            assignment=assignment,
            causale=Receivable.Causale.UTENZE,
        ).first()

        if existing and existing.allocations.exists():
            skippati.append(
                {
                    "receivable_id": existing.pk,
                    "assignment_id": assignment.pk,
                    "tenant_nominativo": q["tenant_nominativo"],
                    "importo_esistente": existing.importo_dovuto,
                    "importo_calcolato": q["quota"],
                }
            )
            continue

        importo_pre = existing.importo_dovuto if existing else None
        _obj, created = Receivable.objects.update_or_create(
            utility_period=period,
            assignment=assignment,
            causale=Receivable.Causale.UTENZE,
            defaults={
                "competenza_da": period.periodo_da,
                "competenza_a": period.periodo_a,
                "importo_dovuto": q["quota"],
                "giorni_presenza": q["giorni_presenza"],
                "scadenza": scadenza,
            },
        )
        if created:
            creati += 1
        elif importo_pre != q["quota"]:
            aggiornati_diversi += 1
        else:
            aggiornati_uguali += 1

    return {
        "skippati_per_allocation": skippati,
        "creati": creati,
        "aggiornati_diversi": aggiornati_diversi,
        "aggiornati_uguali": aggiornati_uguali,
    }
