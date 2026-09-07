"""
Costanti e helper condivisi dai moduli del package ``dashboard_views``.
"""
import datetime
from decimal import Decimal

from billing._dates import format_mese_anno
from billing._payments import conto_per_receivable, iban_valido
from billing.models import BankTransactionAllocation, Receivable, StatoPagamento

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

STATI_DA_PAGARE = {
    StatoPagamento.ATTESO,
    StatoPagamento.IN_RITARDO,
    StatoPagamento.INSOLUTO,
    StatoPagamento.DICHIARATO,
}

# Mapping causale Receivable -> "tipo" esposto nell'API (compatibilità FE)
TIPO_PER_CAUSALE = {
    Receivable.Causale.AFFITTO: "rent",
    Receivable.Causale.UTENZE: "utility_charge",
    Receivable.Causale.EXTRA: "extra",
    # La registrazione contratto viaggia come un addebito "extra" lato FE.
    Receivable.Causale.REGISTRAZIONE: "extra",
    Receivable.Causale.DEPOSITO: "deposit",
}

# Causali "di gestione" mostrate nelle dashboard rendita/pagamenti.
# DEPOSITO è escluso: i depositi cauzionali non sono entrate operative.
# La home inquilino però aggiunge esplicitamente le rate di versamento
# (DEPOSITO con importo positivo): l'inquilino le deve pagare come il resto.
# REGISTRAZIONE è inclusa: è un addebito una-tantum che l'inquilino deve
# (la sua metà del costo di registrazione), pagabile come un extra; senza
# di essa pesava sullo sbilancio reale ma non compariva in nessuna lista.
CAUSALI_OPERATIVE = (
    Receivable.Causale.AFFITTO,
    Receivable.Causale.UTENZE,
    Receivable.Causale.EXTRA,
    Receivable.Causale.REGISTRAZIONE,
)


def _calcola_semaforo(giorni_ritardo: int) -> str:
    """
    Restituisce il colore semaforo in base ai giorni di ritardo.
    giorni_ritardo > 0 → in ritardo; < 0 → mancano giorni.
    """
    if giorni_ritardo > 7:
        return "argilla_scuro"
    if giorni_ritardo > 0:
        return "argilla_chiaro"
    if giorni_ritardo > -7:
        return "miele"
    return "salvia"


def _giorni_ritardo(scadenza: datetime.date, oggi: datetime.date) -> int:
    """
    Positivo = in ritardo di N giorni.
    Negativo = mancano N giorni alla scadenza.
    """
    return (oggi - scadenza).days


def _conto_suggerito_id(r: Receivable) -> int | None:
    """Conto su cui l'inquilino deve versare l'addebito: quello dell'immobile
    (o l'override sull'assegnazione, per l'affitto). Serve al frontend come
    default quando si registra un incasso — che non dipende da chi guarda."""
    conto = conto_per_receivable(r)
    return conto.pk if conto else None


def _competenza_base(r: Receivable) -> datetime.date:
    """Mese di competenza di riferimento, coerente con la descrizione mostrata."""
    if r.causale == Receivable.Causale.UTENZE and r.utility_period:
        return r.utility_period.periodo_da
    return r.competenza_da


def _descrizione_receivable(r: Receivable) -> str:
    if r.causale == Receivable.Causale.AFFITTO:
        return f"Affitto {format_mese_anno(r.competenza_da)}"
    if r.causale == Receivable.Causale.UTENZE:
        if not r.utility_period_id:
            # Previsionale d'uscita o sua rettifica: la descrizione dice
            # già periodo e natura, il mese di competenza confonderebbe.
            return r.descrizione or "Utenze previsionali"
        return f"Utenze {format_mese_anno(_competenza_base(r))}"
    return r.descrizione or "Addebito extra"


def _dati_pagamento(r: Receivable, descrizione: str) -> dict | None:
    """Dati per bonifico/QR: beneficiario, IBAN, causale. None se non disponibili.

    Esposto solo se il conto è risolvibile e l'IBAN è valido (no placeholder).
    """
    conto = conto_per_receivable(r)
    if not conto or not iban_valido(conto.iban):
        return None
    nominativo = r.assignment.tenant.nominativo if r.assignment_id else ""
    causale = f"{descrizione} - {nominativo}".strip(" -")[:140]
    return {
        "beneficiario": conto.intestatario,
        "iban": conto.iban,
        "banca": conto.banca,
        "causale": causale,
    }


def _build_item_da_pagare(
    r: Receivable,
    oggi: datetime.date,
    allocazioni: list | None = None,
    commenti: list | None = None,
) -> dict:
    giorni = _giorni_ritardo(r.scadenza, oggi)
    dovuto = r.importo_dovuto
    pagato = r.importo_pagato or Decimal("0")
    descrizione = _descrizione_receivable(r)
    return {
        "tipo": TIPO_PER_CAUSALE[r.causale],
        "id": r.id,
        "descrizione": descrizione,
        "competenza": _competenza_base(r).isoformat(),
        # `importo` resta il dovuto pieno per retrocompatibilità FE.
        "importo": float(dovuto),
        "importo_dovuto": float(dovuto),
        "importo_pagato": float(pagato),
        "residuo": float(dovuto - pagato),
        "parziale": bool(0 < pagato < dovuto),
        "scadenza": r.scadenza.isoformat(),
        "stato": r.stato,
        "giorni_ritardo": giorni,
        "semaforo": _calcola_semaforo(giorni),
        "pagamento": _dati_pagamento(r, descrizione),
        # Bonifici che hanno coperto (in tutto o in parte) questa voce: data,
        # quota imputata e importo lordo del bonifico. Alimenta il popup di
        # dettaglio della home inquilino (utile sui pagamenti parziali).
        "allocazioni": allocazioni or [],
        # Commenti inquilino/proprietari sull'addebito (popup di dettaglio).
        "commenti": commenti or [],
    }


def _commenti_per_receivable(receivables: list[Receivable]) -> dict[int, list]:
    """Mappa receivable_id -> lista commenti (ordinati per data)."""
    from billing.commenti import _nome_autore
    from billing.models import ReceivableComment

    commenti_map: dict[int, list] = {}
    qs = (
        ReceivableComment.objects.filter(receivable__in=receivables)
        .select_related("autore")
        .order_by("created_at")
    )
    for c in qs:
        commenti_map.setdefault(c.receivable_id, []).append({
            "id": c.id,
            "autore": _nome_autore(c.autore),
            "testo": c.testo,
            "data": c.created_at.date().isoformat(),
        })
    return commenti_map


def _alloc_per_receivable(receivables: list[Receivable]) -> dict[int, list]:
    """Mappa receivable_id -> lista di allocazioni bonifico (ordinate per data)."""
    alloc_map: dict[int, list] = {}
    qs = (
        BankTransactionAllocation.objects.filter(receivable__in=receivables)
        .select_related("bank_transaction")
        .order_by("bank_transaction__data", "id")
    )
    for a in qs:
        alloc_map.setdefault(a.receivable_id, []).append({
            "data": a.bank_transaction.data.isoformat(),
            "quota": float(a.importo),
            "bonifico_totale": float(a.bank_transaction.importo),
        })
    return alloc_map
