"""
Matching tra `BankTransaction` (bonifici dell'estratto conto) e `Receivable`
(addebiti inquilino: affitto, utenze, extra).

Centralizza:
  - regex di classificazione causale (extra > utenze > affitto > unknown);
  - mappa tenant ↔ keyword di descrizione;
  - finestre temporali differenziate per causale;
  - ricerca del bonifico migliore per un Receivable;
  - allocazione greedy di un singolo bonifico su più Receivable
    (caso "bonifico cumulativo": un versamento copre più addebiti).

Il modulo è riusato da `assegna_incassi_da_csv` e `genera_storico` per evitare
implementazioni divergenti del matcher.
"""
import datetime
import re
from decimal import Decimal
from typing import Iterable, Optional

from django.db.models import Q

from billing.models import BankTransaction, BankTransactionAllocation, Receivable
from billing.models.payments import StatoPagamento
from properties.models import TenantProfile

# Pattern di riconoscimento causale (priorità: extra > utenze > affitto).
RE_EXTRA = re.compile(
    r"CONSUNTIVO|CONGUAGLIO|SPESE\s+CONDOMINIALI\s+ANNO|CONS(\.|\s)+COND",
    re.IGNORECASE,
)
RE_UTILITY = re.compile(
    r"UTENZE|BILLS|BOLLETTE|CONSUMI|UTILITIES|BOLLETTA",
    re.IGNORECASE,
)
RE_AFFITTO = re.compile(
    r"AFFITTO|CANONE|RENT(\b|\s)",
    re.IGNORECASE,
)

# Mappa keyword UPPER → last_name TenantProfile.user.last_name.
TENANT_KEYWORDS: dict[str, str] = {
    "DI MAIO": "Di Maio",
    "DAVIDE": "Di Maio",
    "MARIASEVERA": "Armas",
    "MARIA SEVERA": "Armas",
    "SEVERA": "Armas",
    "ARMAS": "Armas",
    "POLKOTU": "Polkotu Hetti Arachchilage",
    "ESHANI": "Polkotu Hetti Arachchilage",
    "SINGARAYAR": "Singarayar",
    "ARUN": "Singarayar",
    "PORRAS": "Porras Rodriguez",
    "DIANA": "Porras Rodriguez",
    "LINDY": "Nyathi",
    "NYATHI": "Nyathi",
    "ELISA": "Chiappini",
    "CHIAPPINI": "Chiappini",
    "BLUNDETTO": "Blundetto",
    "EUGENIA": "Blundetto",
    "DI MARINO": "Di Marino",
    "MARIANNA": "Di Marino",
    "D'ANGELLA": "D'Angella",
    "DANGELLA": "D'Angella",
    "SALVATORE": "D'Angella",
}

_SOGLIA = Decimal("1.00")


def classifica_descrizione(descrizione: str) -> str:
    """Ritorna la causale corrispondente al testo del bonifico.

    Valori: ``Receivable.Causale.{EXTRA,UTENZE,AFFITTO}`` o stringa ``"unknown"``.
    Priorità: extra > utenze > affitto.
    """
    if RE_EXTRA.search(descrizione):
        return Receivable.Causale.EXTRA
    if RE_UTILITY.search(descrizione):
        return Receivable.Causale.UTENZE
    if RE_AFFITTO.search(descrizione):
        return Receivable.Causale.AFFITTO
    return "unknown"


def riconosci_tenant(descrizione: str) -> Optional[TenantProfile]:
    """Identifica il tenant guardando la descrizione del bonifico.

    Il match è case-insensitive sulla mappa ``TENANT_KEYWORDS`` (prima
    occorrenza vince).
    """
    upper = descrizione.upper()
    for kw, last_name in TENANT_KEYWORDS.items():
        if kw in upper:
            return TenantProfile.objects.filter(user__last_name=last_name).first()
    return None


def _keywords_per_tenant(tenant: TenantProfile) -> list[str]:
    """Keyword (UPPER) note per il tenant — usate come filtro descrizione."""
    last = (tenant.user.last_name or "").upper()
    return sorted(
        {kw for kw, ln in TENANT_KEYWORDS.items() if ln.upper() == last},
        key=len,
        reverse=True,
    )


def finestra_match(receivable: Receivable) -> tuple[datetime.date, datetime.date]:
    """Finestra ``[start, end]`` in cui cercare il bonifico per il Receivable.

    L'**ancora** è la scadenza del Receivable (giorno 1 del mese per l'affitto,
    scadenza per utenze ed extra). Le tolleranze pre/post sono differenziate
    per causale e calibrate sui pagamenti reali storici:

      - **affitto** ``[scadenza − 3, scadenza + 20]``: l'affitto è quasi
        sempre pagato nel mese di riferimento, con piccolo anticipo o ritardo
        contenuto. Finestra stretta per evitare che importi alti finiscano
        attribuiti a periodi sbagliati.
      - **utenze** ``[scadenza − 7, scadenza + 40]``: l'inquilino paga di
        norma dopo l'avviso, ma può anticipare di una settimana.
      - **extra** ``[scadenza − 90, scadenza + 60]``: i consuntivi annuali
        sono spesso comunicati e pagati nei primi mesi dell'anno successivo,
        ben prima della scadenza legale (entro 60gg dalla comunicazione).
    """
    causale = receivable.causale
    if causale == Receivable.Causale.AFFITTO:
        start = receivable.scadenza - datetime.timedelta(days=3)
        end = receivable.scadenza + datetime.timedelta(days=20)
    elif causale == Receivable.Causale.UTENZE:
        start = receivable.scadenza - datetime.timedelta(days=7)
        end = receivable.scadenza + datetime.timedelta(days=40)
    elif causale == Receivable.Causale.EXTRA:
        start = receivable.scadenza - datetime.timedelta(days=90)
        end = receivable.scadenza + datetime.timedelta(days=60)
    else:
        raise ValueError(f"Causale sconosciuta: {causale}")
    return start, end


def candidati_bonifici_per(
    receivable: Receivable, escludi_allocati: bool = True
) -> list[BankTransaction]:
    """Bonifici compatibili con il Receivable: tenant + finestra + classe.

    La classe del bonifico (`classifica_descrizione`) deve coincidere con
    `receivable.causale` — questo evita che un consuntivo extra venga
    attribuito a un affitto, anche se temporalmente nella finestra.
    """
    tenant = receivable.assignment.tenant
    keywords = _keywords_per_tenant(tenant)
    if not keywords:
        return []
    start, end = finestra_match(receivable)
    qs = BankTransaction.objects.filter(
        importo__gt=0, data__gte=start, data__lte=end
    )
    if escludi_allocati:
        qs = qs.filter(allocations__isnull=True)
    q_kw = Q()
    for kw in keywords:
        q_kw |= Q(descrizione__icontains=kw)
    qs = qs.filter(q_kw)
    return [
        bt for bt in qs if classifica_descrizione(bt.descrizione) == receivable.causale
    ]


def trova_bonifico_per(
    receivable: Receivable, escludi_allocati: bool = True
) -> Optional[BankTransaction]:
    """Bonifico migliore per il Receivable, o ``None``.

    Ranking:
      1) match esatto importo (|bt.importo − dovuto| < 1€), data più vicina
         alla scadenza vince;
      2) bonifico ≥ dovuto (potenziale cumulativo): preferisci il più vicino
         per importo, poi per data;
      3) altrimenti nessun match (un bonifico inferiore al dovuto non è un
         buon candidato — sarebbe un pagamento parziale).
    """
    candidati = candidati_bonifici_per(receivable, escludi_allocati=escludi_allocati)
    if not candidati:
        return None
    dovuto = receivable.importo_dovuto
    esatti = [bt for bt in candidati if abs(bt.importo - dovuto) < _SOGLIA]
    if esatti:
        return min(esatti, key=lambda bt: abs((bt.data - receivable.scadenza).days))
    cumulativi = [bt for bt in candidati if bt.importo >= dovuto - _SOGLIA]
    if cumulativi:
        cumulativi.sort(
            key=lambda bt: (
                bt.importo - dovuto,
                abs((bt.data - receivable.scadenza).days),
            )
        )
        return cumulativi[0]
    return None


def alloca_bonifico(
    bt: BankTransaction, receivables: Iterable[Receivable]
) -> list[BankTransactionAllocation]:
    """Distribuisce ``bt.importo`` sui ``receivables`` chiudendoli completamente.

    Il **primo** elemento di ``receivables`` è il *primario* e ha priorità
    assoluta: viene sempre allocato per primo. Gli elementi successivi sono i
    *compagni* (es. utenze/extra dello stesso periodo) e vengono allocati
    greedy in ordine di scadenza con il residuo.

    Per ogni Receivable, crea una ``BankTransactionAllocation`` con
    ``importo = receivable.importo_dovuto`` **solo se** il residuo del
    bonifico è sufficiente a coprirlo per intero (entro ``_SOGLIA``). I
    Receivable che non possono essere chiusi vengono saltati: non vogliamo
    lasciare addebiti in stato "pagato parzialmente" basati su un bonifico
    che chiaramente paga qualcos'altro (es. €490 = 466 affitto + 24 spese
    non assegnabili).

    Aggiorna ``stato``/``data_pagamento``/``importo_pagato`` solo sui
    Receivable effettivamente allocati.
    """
    receivables = list(receivables)
    if not receivables:
        return []
    primario = receivables[0]
    compagni = sorted(receivables[1:], key=lambda r: r.scadenza)
    ordinati = [primario, *compagni]
    residuo = bt.importo
    owner_id = bt.owner_account.owner_id
    out: list[BankTransactionAllocation] = []
    for r in ordinati:
        dovuto = r.importo_dovuto
        if residuo + _SOGLIA < dovuto:
            continue
        alloc = BankTransactionAllocation.objects.create(
            bank_transaction=bt,
            receivable=r,
            importo=dovuto,
        )
        out.append(alloc)
        r.stato = StatoPagamento.PAGATO
        r.data_pagamento = bt.data
        r.importo_pagato = dovuto
        r.incassato_da_owner_id = owner_id
        r.save(
            update_fields=[
                "stato",
                "data_pagamento",
                "importo_pagato",
                "incassato_da_owner",
                "updated_at",
            ]
        )
        residuo -= dovuto
    return out


def trova_receivables_per_bt(
    bt: BankTransaction, escludi_pagati: bool = True
) -> list[Receivable]:
    """Receivable candidati per questo bonifico, in ordine di affinità.

    Identifica tenant + causale dal testo, filtra per finestra coerente con
    la causale del Receivable. Ranking:
      1. dovuto ≈ importo del bonifico (match 1:1 perfetto);
      2. dovuto ≤ importo del bonifico (potenziale cumulativo), ordinati per
         scadenza più vicina alla data del bonifico.

    I Receivable il cui ``importo_dovuto`` eccede ``bt.importo`` sono esclusi
    (un bonifico inferiore al dovuto non chiude l'addebito).
    """
    tenant = riconosci_tenant(bt.descrizione)
    if not tenant:
        return []
    causale = classifica_descrizione(bt.descrizione)
    if causale == "unknown":
        causale = (
            Receivable.Causale.AFFITTO
            if bt.importo >= Decimal("400")
            else Receivable.Causale.UTENZE
        )
    qs = Receivable.objects.filter(causale=causale, assignment__tenant=tenant)
    if escludi_pagati:
        qs = qs.filter(stato=StatoPagamento.ATTESO)
    candidati: list[Receivable] = []
    for r in qs.select_related("assignment__tenant"):
        start, end = finestra_match(r)
        if start <= bt.data <= end and r.importo_dovuto <= bt.importo + _SOGLIA:
            candidati.append(r)
    esatti = [c for c in candidati if abs(c.importo_dovuto - bt.importo) < _SOGLIA]
    if esatti:
        esatti.sort(key=lambda c: abs((bt.data - c.scadenza).days))
        return esatti
    candidati.sort(
        key=lambda c: (
            bt.importo - c.importo_dovuto,
            abs((bt.data - c.scadenza).days),
        )
    )
    return candidati


def receivables_compagni(
    primario: Receivable, finestra_giorni: int = 35
) -> list[Receivable]:
    """Receivable dello stesso tenant che potrebbero condividere un bonifico
    cumulativo con ``primario`` (es. affitto + utenze del mese).

    Filtra quelli ancora non pagati e con scadenza vicina (entro
    ``finestra_giorni`` dalla scadenza del primario), causale ≠ primario.
    """
    delta = datetime.timedelta(days=finestra_giorni)
    return list(
        Receivable.objects.filter(
            assignment__tenant=primario.assignment.tenant,
            stato=StatoPagamento.ATTESO,
            scadenza__gte=primario.scadenza - delta,
            scadenza__lte=primario.scadenza + delta,
        )
        .exclude(pk=primario.pk)
        .exclude(causale=primario.causale)
    )
