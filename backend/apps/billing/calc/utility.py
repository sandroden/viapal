"""
Calcolo utenze per UtilityChargePeriod.

Criterio: pro_rata_giorni (l'unico usato in pratica secondo PLAN.md).
Algoritmo descritto nella docstring di calcola_conguaglio_periodo.
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TypedDict

VOCI_FATTURABILI = ("luce", "gas")


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


def _sottrai_intervalli(
    intervalli: list[tuple[date, date]],
    da_togliere: list[tuple[date, date]],
) -> list[tuple[date, date]]:
    """Sottrae `da_togliere` da `intervalli`. Intervalli inclusivi a entrambi gli estremi."""
    risultato = list(intervalli)
    for t_da, t_a in da_togliere:
        nuovi: list[tuple[date, date]] = []
        for s, e in risultato:
            # Nessuna intersezione
            if t_a < s or t_da > e:
                nuovi.append((s, e))
                continue
            # Parte a sinistra di t_da
            if s < t_da:
                nuovi.append((s, t_da - timedelta(days=1)))
            # Parte a destra di t_a
            if e > t_a:
                nuovi.append((t_a + timedelta(days=1), e))
        risultato = nuovi
    return risultato


def _giorni_in_intervalli(intervalli: list[tuple[date, date]]) -> int:
    return sum((e - s).days + 1 for s, e in intervalli)


def _attribuisci_bollette(period) -> tuple[dict[str, Decimal], list]:
    """Decide quali UtilityBill contribuiscono a `period` e con quale importo.

    Restituisce ``(contributi_per_voce, bollette_utilizzate)``:
      - ``contributi_per_voce``: dict ``{"luce": Decimal, "gas": Decimal}`` con i totali
        attribuiti al periodo.
      - ``bollette_utilizzate``: lista di ``UtilityBill`` da agganciare alla M2M
        ``period.utility_bills`` (segna le bollette come "consumate" dal periodo).

    Regole (vedi conversazione 2026-05-13):

    1. Una bolletta "consumata" da un altro periodo `inviato` (cioè presente nella
       sua M2M ``utility_bills``) **non rientra** nel calcolo. Garantisce che una
       volta chiuso un periodo, le bollette che ha addebitato non vengano
       ri-addebitate altrove.
    2. La bolletta si attribuisce in pro-rata sui giorni di intersezione tra il
       suo ``[periodo_da, periodo_a]`` e ``period``, **dopo aver troncato** le
       porzioni che cadono in altri periodi ``inviato``. Cioè le porzioni di
       bolletta che riferiscono a un periodo già chiuso ma non lo hanno
       addebitato (es. fornitore che etichetta gen-apr quando gen-feb era già
       stato fatturato con un'altra bolletta) si comprimono sui giorni
       rimanenti.
    3. Se il "range effettivo" della bolletta si svuota (cade interamente in
       periodi chiusi), la bolletta viene **ribaltata interamente** sul primo
       periodo bozza con ``periodo_da >= bill.data_emissione``. È il caso del
       conguaglio retroattivo che arriva dopo che il bimestre era già stato
       chiuso: invece di sparire, l'importo viene addebitato al periodo
       successivo ancora aperto.

    Override manuale (pin via M2M)
    ------------------------------
    Le decisioni storiche dell'utente non sono sempre derivabili da regole
    semplici (es. fornitore con etichetta "gen-apr" che in realtà significa
    "mar-apr" perché gen-feb era stato già fatturato altrove). Per questo, se
    ``period.utility_bills`` è già popolata, il calcolo entra in **modalità
    pinning**: ogni bolletta agganciata contribuisce per l'importo intero al
    periodo, ignorando l'algoritmo automatico. Sull'admin l'utente popola la
    M2M con un widget filter_horizontal.
    """
    from billing.models import UtilityBill, UtilityChargePeriod

    P_da: date = period.periodo_da
    P_a: date = period.periodo_a
    INVIATO = UtilityChargePeriod.StatoPeriodo.INVIATO
    BOZZA = UtilityChargePeriod.StatoPeriodo.BOZZA

    # Modalità pinning: la M2M è "verità manuale". Se popolata, ogni bolletta
    # agganciata cade intera sul periodo (no pro-rata, no ribaltamento).
    pinned = list(period.utility_bills.filter(prodotto__in=VOCI_FATTURABILI))
    if pinned:
        contributi: dict[str, Decimal] = {}
        for b in pinned:
            contributi[b.prodotto] = (
                contributi.get(b.prodotto, Decimal("0.00")) + b.importo_totale
            )
        return contributi, pinned

    # Periodi inviato (≠ corrente), per troncare i range bolletta
    closed_qs = UtilityChargePeriod.objects.filter(stato=INVIATO).exclude(pk=period.pk)
    closed_intervals: list[tuple[date, date]] = [
        (pd, pa) for pd, pa in closed_qs.values_list("periodo_da", "periodo_a")
    ]

    # ID bollette già consumate da altri periodi inviato (escluse dal calcolo)
    consumed_ids = set(
        UtilityBill.objects.filter(periods__stato=INVIATO)
        .exclude(periods__pk=period.pk)
        .values_list("pk", flat=True)
    )

    # Per il ribaltamento delle bollette "stranded": il primo bozza con
    # periodo_da >= data_emissione. Calcoliamo solo se serve.
    def _primo_bozza_dopo(d: date):
        return (
            UtilityChargePeriod.objects.filter(stato=BOZZA, periodo_da__gte=d)
            .order_by("periodo_da")
            .first()
        )

    contributi: dict[str, Decimal] = {}
    bollette_usate: list = []

    bills = UtilityBill.objects.filter(
        prodotto__in=VOCI_FATTURABILI,
        periodo_da__lte=P_a,  # bollette iniziate prima della fine di P
    ).exclude(pk__in=consumed_ids)

    for bill in bills:
        effective = _sottrai_intervalli(
            [(bill.periodo_da, bill.periodo_a)], closed_intervals
        )
        giorni_effective = _giorni_in_intervalli(effective)
        giorni_in_P = sum(
            _giorni_intersezione(s, e, P_da, P_a) for s, e in effective
        )

        if giorni_effective > 0 and giorni_in_P > 0:
            quota = (
                bill.importo_totale * Decimal(giorni_in_P) / Decimal(giorni_effective)
            )
            contributi[bill.prodotto] = (
                contributi.get(bill.prodotto, Decimal("0.00")) + quota
            )
            bollette_usate.append(bill)
        elif giorni_effective == 0:
            # Bolletta interamente in periodi chiusi: ribalta sul primo bozza
            # successivo all'emissione, se è proprio `period`.
            target = _primo_bozza_dopo(bill.data_emissione)
            if target is None:
                # Nessun bozza ≥ data_emissione: fallback sul bozza più recente.
                target = (
                    UtilityChargePeriod.objects.filter(stato=BOZZA)
                    .order_by("-periodo_da")
                    .first()
                )
            if target is not None and target.pk == period.pk:
                contributi[bill.prodotto] = (
                    contributi.get(bill.prodotto, Decimal("0.00")) + bill.importo_totale
                )
                bollette_usate.append(bill)
        # else: giorni_effective > 0 ma giorni_in_P == 0 → bolletta riguarda
        # altri periodi bozza, non contribuisce a `period`.

    return contributi, bollette_usate


def _periodi_attivi_in_range(periodo_da: date, periodo_a: date) -> list[tuple[date, date]]:
    """Ritorna `[(da, a), ...]` per i ``UtilityChargePeriod`` nel range
    ``[periodo_da, periodo_a]`` che hanno almeno una bolletta luce/gas
    (cioè quelli che producono effettivamente Receivable).

    Usato come denominatore per la distribuzione di costi annuali (TARI):
    serve sapere quali periodi ricevono Receivable per ripartire la quota
    annua solo fra essi (vedi razionale sotto).
    """
    from billing.models import UtilityBill, UtilityChargePeriod

    periodi = UtilityChargePeriod.objects.filter(
        periodo_da__lte=periodo_a,
        periodo_a__gte=periodo_da,
    )
    attivi: list[tuple[date, date]] = []
    for p in periodi:
        ha_bollette = UtilityBill.objects.filter(
            periodo_da__lte=p.periodo_a,
            periodo_a__gte=p.periodo_da,
            prodotto__in=VOCI_FATTURABILI,
        ).exists()
        if ha_bollette:
            attivi.append((p.periodo_da, p.periodo_a))
    return attivi


def _raccoglie_voci_annual(periodo_da: date, periodo_a: date) -> dict[str, Decimal]:
    """
    Calcola la quota TARI (AnnualUtilityCost) per il periodo corrente,
    distribuita sui ``UtilityChargePeriod`` attivi (= con bollette luce/gas)
    nello stesso intervallo di validità.

    Formula:
        quota = importo_annuale × giorni_periodo_corrente / sum_giorni_periodi_attivi

    Razionale: la TARI annua va ripartita solo fra i periodi che producono
    Receivable. Se in un anno emetti 6 conguagli bimestrali ognuno prende
    ~1/6, se ne emetti 12 mensili ognuno prende ~1/12, se mixato la
    proporzionalità ai giorni distribuisce correttamente. Periodi senza
    bollette luce/gas (skippati dal calcolo upstream) non concorrono al
    denominatore: la loro quota viene redistribuita sugli altri.

    Fallback: se nessun periodo attivo è trovato (caso degenere), si torna
    alla vecchia formula con denominatore 365 per non bloccare il calcolo.
    """
    from billing.models import AnnualUtilityCost

    totali: dict[str, Decimal] = {}

    annual_costs = AnnualUtilityCost.objects.filter(
        valid_from__lte=periodo_a,
    ).filter(
        valid_to__isnull=True,
    ) | AnnualUtilityCost.objects.filter(
        valid_from__lte=periodo_a,
        valid_to__gte=periodo_da,
    )
    annual_costs = annual_costs.distinct()

    for ac in annual_costs:
        ac_to = ac.valid_to if ac.valid_to else date(9999, 12, 31)
        giorni_periodo_corrente = _giorni_intersezione(
            periodo_da, periodo_a, ac.valid_from, ac_to
        )
        if giorni_periodo_corrente <= 0:
            continue

        # Denominatore: somma giorni dei periodi attivi nel range di validità di ac
        attivi = _periodi_attivi_in_range(ac.valid_from, ac_to)
        sum_giorni_attivi = sum(
            _giorni_intersezione(p_da, p_a, ac.valid_from, ac_to)
            for p_da, p_a in attivi
        )

        if sum_giorni_attivi > 0:
            quota = ac.importo_annuale * Decimal(giorni_periodo_corrente) / Decimal(
                sum_giorni_attivi
            )
        else:
            quota = ac.importo_annuale * Decimal(giorni_periodo_corrente) / Decimal(365)

        voce = ac.voce
        totali[voce] = totali.get(voce, Decimal("0.00")) + quota

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
       quota = importo_annuale * giorni_intersezione / 365
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
    if persist:
        skippati_per_allocation = _persist_receivables(
            period, quote, totali_per_voce, periodo_da, sum_giorni, bollette_usate
        )

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

        Receivable.objects.update_or_create(
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

    return skippati
