"""
Calcolo utenze per UtilityChargePeriod.

Criterio: pro_rata_giorni (l'unico usato in pratica secondo PLAN.md).
Algoritmo descritto nella docstring di calcola_conguaglio_periodo.
"""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TypedDict

VOCI_FATTURABILI = ("luce", "gas")

# Voci "a bolletta" che la config di casa può attivare (la TARI è un costo
# annuale, non una bolletta).
VOCI_CONFIGURABILI_BOLLETTA = ("luce", "gas", "acqua")

# Finestra del ribaltamento retroattivo (vedi `_attribuisci_bollette`). Il
# retro serve al conguaglio arrivato in ritardo di qualche mese — il caso
# Edison che ha motivato l'attribuzione v3 sta a ~4 mesi — non a resuscitare
# lo storico: una bolletta che si chiude prima di questa finestra non entra
# mai nella ripartizione del mese corrente, qualunque cosa dicano le date di
# import. Gli inquilini di oggi ripartiscono le bollette di oggi.
RETRO_FINESTRA_MESI = 6


def _voci_fatturabili(property_id) -> tuple[str, ...]:
    """Voci "a bolletta" gestite dalla proprietà per questo immobile.

    Da ``PropertyUtilityService`` (``gestione=proprieta``). Fallback storico
    per immobili senza alcuna riga di configurazione: luce+gas. Può essere
    vuota: appartamento con tutte le utenze intestate all'inquilino.
    """
    from billing.models import PropertyUtilityService

    rows = list(PropertyUtilityService.objects.filter(property_id=property_id))
    if not rows:
        return VOCI_FATTURABILI
    proprieta = {
        r.voce
        for r in rows
        if r.gestione == PropertyUtilityService.Gestione.PROPRIETA
    }
    return tuple(v for v in VOCI_CONFIGURABILI_BOLLETTA if v in proprieta)


def _voci_annuali_escluse(property_id) -> set[str]:
    """Voci annuali da NON ripartire: quelle configurate esplicitamente come
    NON gestite dalla proprietà (es. TARI intestata all'inquilino).

    Un ``AnnualUtilityCost`` senza riga di configurazione resta ripartibile:
    il costo caricato a sistema è già una dichiarazione esplicita.
    """
    from billing.models import PropertyUtilityService

    return {
        r.voce
        for r in PropertyUtilityService.objects.filter(property_id=property_id)
        if r.gestione != PropertyUtilityService.Gestione.PROPRIETA
    }


class QuotaInquilino(TypedDict, total=False):
    assignment_id: int
    tenant_nominativo: str
    giorni_presenza: int
    quota: Decimal
    dettaglio: dict  # {'luce': Decimal, 'gas': Decimal, 'tari': Decimal, ...}
    importo_esistente: Decimal | None  # Receivable utenze gia' presente per (period, assignment)


def _mesi_indietro(d: date, mesi: int) -> date:
    """Il giorno 1 del mese che sta `mesi` mesi prima di `d`."""
    n = d.year * 12 + (d.month - 1) - mesi
    return date(n // 12, n % 12 + 1, 1)


def _giorni_intersezione(da1: date, a1: date, da2: date, a2: date) -> int:
    """Ritorna il numero di giorni di intersezione tra [da1, a1] e [da2, a2] (inclusivi)."""
    inizio = max(da1, da2)
    fine = min(a1, a2)
    delta = (fine - inizio).days + 1
    return max(0, delta)


def _arrotonda(valore: Decimal) -> Decimal:
    """Arrotonda a 2 decimali con ROUND_HALF_UP."""
    return valore.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _attribuisci_bollette(period) -> tuple[dict[str, Decimal], list, list[dict], list[dict]]:
    """Decide quali UtilityBill contribuiscono a `period` e con quale importo.

    Attribuzione **day-based** (v3, vedi docs/piano-utenze-configurabili.md §8):

    - **Quota propria**: un periodo prende le bollette il cui intervallo
      ``[periodo_da, periodo_a]`` si sovrappone al periodo, in pro-rata sui
      giorni di sovrapposizione. Una bolletta che copre N mesi viene ripartita
      su quei mesi: la somma delle quote = importo ripartibile della bolletta,
      **qualunque sia l'ordine di emissione** (i giorni che cadono in periodi
      ``inviato`` restano congelati lì, gli altri restano attribuibili).
    - **Quota retroattiva** (caso Edison): i giorni di una bolletta che cadono
      in periodi ``inviato`` che NON l'hanno pinnata — e che sono nati prima
      della bolletta (``bill.created_at > periodo.created_at``, la guardia che
      esclude gli import storici) — si ribaltano tutti sul periodo **target**,
      cioè il primo periodo che copre il giorno successivo alla fine
      dell'ultimo periodo inviato. Così un conguaglio arrivato a luglio che
      riprende aprile non va perso: finisce tutto sul mese dopo l'ultimo
      addebito creato. Il ribaltamento vale **solo dentro
      ``RETRO_FINESTRA_MESI``**: una bolletta che si chiude prima di quella
      finestra è storia, non un conguaglio in ritardo, e non entra mai nella
      ripartizione del mese corrente — a prescindere da quando è stata
      importata.

    I contributi sono al **netto** della ``quota_esclusa`` (voci a carico
    proprietà: canone RAI, aumento potenza, allacci...): la base è sempre
    ``bill.importo_ripartibile``, mai ``importo_totale``.

    Restituisce ``(contributi_per_voce, bollette_utilizzate, esclusioni, arretrati)``:
      - ``contributi_per_voce``: ``{"luce": Decimal, "gas": Decimal}`` per il periodo (netti).
      - ``bollette_utilizzate``: bollette da agganciare alla M2M ``utility_bills``.
      - ``esclusioni``: ``[{"bill_id", "prodotto", "motivo", "quota_esclusa"}]``
        con la quota già pro-rata sul periodo.
      - ``arretrati``: ``[{"bill_id", "prodotto", "periodo_da", "periodo_a",
        "giorni", "importo"}]`` — le quote retroattive incluse nel periodo
        target, per trasparenza in anteprima/UI.

    Override manuale (pinning): se ``period.utility_bills`` è già popolata,
    quelle bollette valgono per l'importo ripartibile intero (verità manuale,
    niente retroattivi) — **tranne** quelle agganciate anche ad altri periodi,
    che si ripartiscono pro-rata sui giorni. È il caso della bimestrale che
    appartiene a entrambi i mesi: agganciarla a tutti e due è la verità
    documentale e la somma resta l'importo della bolletta. Una bolletta
    pinnata da un periodo ``inviato`` non genera mai quote retroattive; i suoi
    giorni FUORI dal periodo che l'ha pinnata restano però attribuibili come
    quota propria dei mesi che coprono — chi pinna a mano una bolletta su un
    solo periodo che non la copre tutta se ne assume la doppia imputazione.
    """
    from billing.models import UtilityBill, UtilityChargePeriod

    P_da: date = period.periodo_da
    P_a: date = period.periodo_a
    INVIATO = UtilityChargePeriod.StatoPeriodo.INVIATO

    esclusioni: list[dict] = []
    voci = _voci_fatturabili(period.property_id)

    # Modalità pinning: la M2M è "verità manuale". Una bolletta agganciata a
    # QUESTO SOLO periodo cade intera (è l'override: "questa bolletta la voglio
    # qui"). Una bolletta agganciata anche ad altri periodi — il caso naturale
    # della bimestrale, che appartiene a entrambi i mesi — si ripartisce
    # pro-rata sui giorni, come farebbe la quota propria: così la somma sui
    # periodi che la condividono resta l'importo della bolletta, senza doppia
    # imputazione. Se il periodo non ne copre nemmeno un giorno vince
    # l'override e vale intera.
    pinned = list(period.utility_bills.filter(prodotto__in=voci))
    if pinned:
        contributi: dict[str, Decimal] = {}
        for b in pinned:
            giorni_bolletta = (b.periodo_a - b.periodo_da).days + 1
            giorni = _giorni_intersezione(b.periodo_da, b.periodo_a, P_da, P_a)
            condivisa = b.periods.count() > 1
            if condivisa and 0 < giorni < giorni_bolletta:
                quota = b.importo_ripartibile * Decimal(giorni) / Decimal(giorni_bolletta)
            else:
                quota = b.importo_ripartibile
            contributi[b.prodotto] = (
                contributi.get(b.prodotto, Decimal("0.00")) + quota
            )
            if b.quota_esclusa:
                # La quota a carico proprietà segue la stessa frazione della
                # quota ripartita, altrimenti su una bimestrale condivisa
                # verrebbe esclusa due volte.
                esclusa = b.quota_esclusa
                if condivisa and 0 < giorni < giorni_bolletta:
                    esclusa = esclusa * Decimal(giorni) / Decimal(giorni_bolletta)
                esclusioni.append(
                    {
                        "bill_id": b.pk,
                        "prodotto": b.prodotto,
                        "motivo": b.motivo_esclusione,
                        "quota_esclusa": esclusa,
                    }
                )
        return contributi, pinned, esclusioni, []

    contributi: dict[str, Decimal] = {}
    bollette_usate: list = []
    arretrati: list[dict] = []

    def _aggiungi(bill, giorni: int, giorni_bolletta: int) -> Decimal:
        """Somma a ``contributi``/``esclusioni`` la quota pro-rata di ``giorni``."""
        if giorni >= giorni_bolletta:
            quota = bill.importo_ripartibile
            esclusa = bill.quota_esclusa or Decimal("0")
        else:
            frazione = Decimal(giorni) / Decimal(giorni_bolletta)
            quota = bill.importo_ripartibile * frazione
            esclusa = (bill.quota_esclusa or Decimal("0")) * frazione
        contributi[bill.prodotto] = (
            contributi.get(bill.prodotto, Decimal("0.00")) + quota
        )
        if esclusa:
            esclusioni.append(
                {
                    "bill_id": bill.pk,
                    "prodotto": bill.prodotto,
                    "motivo": bill.motivo_esclusione,
                    "quota_esclusa": esclusa,
                }
            )
        if bill not in bollette_usate:
            bollette_usate.append(bill)
        return quota

    # --- Quota propria: bollette in overlap col periodo, pro-rata sui giorni.
    # Niente esclusione binaria delle bollette pinnate altrove: i giorni dentro
    # i periodi inviati sono congelati lì, ma quelli che cadono qui contano qui
    # (una bolletta a cavallo non perde più la coda se i mesi si emettono in
    # ordine sparso).
    bills = UtilityBill.objects.filter(
        immobile_id=period.property_id,
        prodotto__in=voci,
        periodo_da__lte=P_a,
        periodo_a__gte=P_da,
    )
    for bill in bills:
        giorni_bolletta = (bill.periodo_a - bill.periodo_da).days + 1
        giorni_in_P = _giorni_intersezione(bill.periodo_da, bill.periodo_a, P_da, P_a)
        if giorni_in_P <= 0 or giorni_bolletta <= 0:
            continue
        _aggiungi(bill, giorni_in_P, giorni_bolletta)

    # --- Quota retroattiva: solo se questo periodo è il "target", cioè copre
    # il giorno successivo alla fine dell'ultimo periodo inviato.
    inviati = list(
        UtilityChargePeriod.objects.filter(
            property_id=period.property_id, stato=INVIATO
        ).exclude(pk=period.pk)
    )
    if inviati:
        ultimo_a = max(e.periodo_a for e in inviati)
        if P_da <= ultimo_a + timedelta(days=1) <= P_a:
            pinnate_da_inviati = set(
                UtilityBill.objects.filter(periods__stato=INVIATO)
                .exclude(periods__pk=period.pk)
                .values_list("pk", flat=True)
            )
            candidate = UtilityBill.objects.filter(
                immobile_id=period.property_id,
                prodotto__in=voci,
                periodo_da__lte=ultimo_a,
                # Finestra: niente ribaltamenti dal passato remoto. Una
                # bolletta chiusa da più di RETRO_FINESTRA_MESI non è un
                # conguaglio in ritardo, è storia — e la storia non si
                # riparte tra gli inquilini di oggi.
                periodo_a__gte=_mesi_indietro(P_da, RETRO_FINESTRA_MESI),
            ).exclude(pk__in=pinnate_da_inviati)
            for bill in candidate:
                giorni_bolletta = (bill.periodo_a - bill.periodo_da).days + 1
                if giorni_bolletta <= 0:
                    continue
                giorni_retro = sum(
                    _giorni_intersezione(
                        bill.periodo_da, bill.periodo_a, e.periodo_da, e.periodo_a
                    )
                    for e in inviati
                    # Guardia storico: ribalta solo ciò che è nato DOPO il
                    # periodo (il conguaglio arrivato a cose fatte), mai le
                    # bollette importate prima che i periodi esistessero.
                    if bill.created_at > e.created_at
                )
                if giorni_retro <= 0:
                    continue
                quota = _aggiungi(bill, giorni_retro, giorni_bolletta)
                arretrati.append(
                    {
                        "bill_id": bill.pk,
                        "prodotto": bill.prodotto,
                        "periodo_da": bill.periodo_da,
                        "periodo_a": bill.periodo_a,
                        "giorni": giorni_retro,
                        "importo": quota,
                    }
                )

    return contributi, bollette_usate, esclusioni, arretrati


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
    forza_senza_bollette: bool = False,
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

    ``forza_senza_bollette``: di norma un periodo senza bollette luce/gas
    viene saltato (``skipped="no_bollette_luce_gas"``). Con il flag a True
    (richiesta esplicita del proprietario, es. TARI a carico dell'inquilino
    con luce/gas intestate a lui) si ripartiscono comunque i costi annuali.

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
        "diff_arrotondamento": Decimal,      # totale_periodo - somma(quote)
        "totale_escluso": Decimal,           # quote escluse (a carico proprietà) nel periodo
        "esclusioni": [{"bill_id", "prodotto", "motivo", "quota_esclusa"}, ...],
                                             # bill_id None = esclusione TARI del periodo
        "arretrati": [{"bill_id", "prodotto", "periodo_da", "periodo_a",
                       "giorni", "importo"}, ...]   # quote retroattive (v3)
    }

    I totali per voce sono al netto delle quote escluse (importo_ripartibile
    delle bollette e ``period.quota_esclusa_tari`` per la TARI): la parte
    esclusa resta a carico della proprietà e non entra mai nelle quote
    inquilino.
    """
    from billing.models import UtilityChargePeriod
    from properties.models import RoomAssignment

    period = UtilityChargePeriod.objects.get(pk=period_id)
    periodo_da: date = period.periodo_da
    periodo_a: date = period.periodo_a

    # --- Passo 1: attribuzione bollette al periodo (contributi già netti) ---
    contributi, bollette_usate, esclusioni, arretrati = _attribuisci_bollette(period)

    def _skip(motivo: str) -> dict:
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
            "totale_escluso": Decimal("0.00"),
            "esclusioni": [],
            "arretrati": [],
            "skipped": motivo,
        }

    # Regola Sandro 2026-05-02: non emettere conguagli "solo TARI". I conguagli
    # vanno emessi solo quando c'e' almeno una bolletta luce/gas. Se manca,
    # il periodo viene saltato del tutto. Eccezione (2026-08-06): con
    # ``forza_senza_bollette`` — scelta esplicita del proprietario — si
    # ripartisce quello che c'è, inclusi i soli costi annuali (es. TARI quando
    # luce/gas sono intestate direttamente all'inquilino).
    # Un immobile configurato SENZA utenze a bolletta gestite dalla proprietà
    # (es. appartamento: luce/gas intestate all'inquilino, resta la TARI)
    # procede coi soli costi annuali senza bisogno di forzature.
    if (
        not contributi
        and not forza_senza_bollette
        and _voci_fatturabili(period.property_id)
    ):
        return _skip("no_bollette_luce_gas")
    totali_per_voce: dict[str, Decimal] = dict(contributi)
    # TARI e altri costi annuali (aggiunti solo se ci sono bollette).
    # Le voci configurate come NON gestite dalla proprietà (es. TARI
    # intestata all'inquilino) restano fuori anche se il costo esiste.
    escluse_config = _voci_annuali_escluse(period.property_id)
    totali_annual = _raccoglie_voci_annual(period.property_id, periodo_da, periodo_a)
    for voce, importo in totali_annual.items():
        if voce in escluse_config:
            continue
        totali_per_voce[voce] = totali_per_voce.get(voce, Decimal("0.00")) + importo

    # Quota TARI a carico proprietà (es. i posti che non siamo riusciti ad
    # affittare: la loro fetta di TARI non si scarica su chi c'è). È un valore
    # **del mese**, non dell'anno: lo sfitto cambia di mese in mese. Vale la
    # stessa regola delle bollette — la parte esclusa resta alla proprietà,
    # la riga resta visibile all'inquilino. Clamp difensivo: un valore
    # rimasto in giro dopo che la TARI del mese è calata non deve mai
    # produrre una voce negativa.
    esclusa_tari = period.quota_esclusa_tari or Decimal("0")
    tari_lorda = totali_per_voce.get("tari", Decimal("0.00"))
    if esclusa_tari > 0 and tari_lorda > 0:
        esclusa_tari = min(esclusa_tari, tari_lorda)
        residuo = tari_lorda - esclusa_tari
        if residuo > 0:
            totali_per_voce["tari"] = residuo
        else:
            del totali_per_voce["tari"]
        esclusioni.append(
            {
                "bill_id": None,
                "prodotto": "tari",
                "motivo": period.motivo_esclusione_tari,
                "quota_esclusa": esclusa_tari,
            }
        )
    if not totali_per_voce:
        # Forzatura su un periodo davvero vuoto: niente da ripartire.
        return _skip("nessun_importo")

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
    # Le rinunce non hanno mai occupato la stanza: vanno tolte prima del
    # conteggio dei giorni, altrimenti finirebbero anche nel denominatore
    # `sum_giorni` diluendo la quota di tutti gli altri inquilini.
    assignments_qs = (
        assignments_qs.exclude(rinunciata=True).distinct().select_related("tenant")
    )

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
        "totale_escluso": _arrotonda(
            sum((e["quota_esclusa"] for e in esclusioni), Decimal("0.00"))
        ),
        "esclusioni": [
            {**e, "quota_esclusa": _arrotonda(e["quota_esclusa"])} for e in esclusioni
        ],
        "arretrati": [
            {**a, "importo": _arrotonda(a["importo"])} for a in arretrati
        ],
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
