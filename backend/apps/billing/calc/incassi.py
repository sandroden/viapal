"""Registrazione di un incasso su un Receivable.

Un addebito chiuso deve sempre dire **chi** ha incassato: senza
``incassato_da_owner`` il pagamento sparisce dai saldi tra proprietari
(``accounting.services.saldi_live``) e lo scarto salta fuori settimane dopo,
quando nessuno ricorda più chi aveva ricevuto il bonifico.

Per questo l'unica strada per portare un Receivable a PAGATO è passare di qui:
si crea la ``BankTransaction`` sul conto dell'incassante e la si alloca
all'addebito. ``incassato_da_owner`` lo valorizza poi il signal di
riallineamento a partire dal conto del movimento — nessuno lo scrive a mano.
"""
import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from billing.models import BankTransaction, BankTransactionAllocation, Receivable
from billing.models.payments import StatoPagamento


class IncassoRifiutato(Exception):
    """Incasso non registrabile: porta con sé il codice HTTP da restituire."""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def residuo_da_incassare(receivable: Receivable) -> Decimal:
    """Quanto manca per coprire il dovuto, col segno del dovuto.

    Positivo per affitti/utenze/extra, negativo per le restituzioni di
    deposito (dove l'incasso è in realtà un'uscita).

    Misura sulle allocazioni, non su ``importo_pagato``: quel campo è un
    denormalizzato che il signal ricalcola dalle stesse allocazioni, e su un
    addebito solo *dichiarato* riporta quanto afferma l'inquilino, non quanto
    è arrivato. La copertura reale è il denaro allocato.
    """
    allocato = (
        receivable.allocations.aggregate(tot=Sum("importo"))["tot"] or Decimal("0")
    )
    return receivable.importo_dovuto - allocato


def registra_incasso(
    receivable: Receivable,
    *,
    data,
    importo: Decimal,
    owner_account,
    descrizione: str = "",
    note: str = "",
) -> tuple[BankTransaction, Decimal]:
    """Crea il movimento bancario e lo alloca al Receivable.

    Se l'importo eccede il residuo alloca solo il residuo e lascia la
    differenza sulla BT (resta visibile come credito in riconciliazione); se è
    inferiore alloca tutto e l'addebito resta atteso col residuo aggiornato.

    Ritorna la coppia ``(bank_transaction, quota_allocata)``.
    Solleva ``IncassoRifiutato`` se l'incasso non è registrabile.
    """
    from billing.signals import _riallinea_receivable

    residuo = residuo_da_incassare(receivable)
    if residuo == 0:
        raise IncassoRifiutato(
            "Receivable già completamente allocato.", status_code=409
        )
    # Invariante: BT/allocation/Receivable hanno tutti lo stesso segno.
    if (residuo > 0) != (importo > 0):
        atteso = "positivo" if residuo > 0 else "negativo"
        raise IncassoRifiutato(
            f"L'importo deve essere {atteso} (coerente col dovuto)."
        )

    # |quota| = min(|importo|, |residuo|), preservando il segno del residuo.
    quota = importo if abs(importo) <= abs(residuo) else residuo

    with transaction.atomic():
        bt = BankTransaction.objects.create(
            data=data,
            descrizione=descrizione or "",
            importo=importo,
            owner_account=owner_account,
            note=note or "",
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt,
            receivable=receivable,
            importo=quota,
        )
        _riallinea_receivable(receivable.id)

    return bt, quota


def nota_dichiarazione(estremi, oggi: datetime.date | None = None) -> str:
    """Riga di nota con gli estremi del pagamento dichiarato dall'inquilino.

    ``estremi`` è il payload di ``dichiara_pagato`` (``importo_pagato``,
    ``metodo_pagamento``, ``riferimento``, ``note``, tutti facoltativi).
    """
    parti = []
    try:
        importo = Decimal(str(estremi.get("importo_pagato")))
        parti.append(f"{importo:.2f} €".replace(".", ","))
    except Exception:
        pass
    for campo in ("metodo_pagamento", "riferimento", "note"):
        valore = str(estremi.get(campo) or "").strip()
        if valore:
            parti.append(valore[:200])
    if not parti:
        return ""
    oggi = oggi or datetime.date.today()
    return f"[Dichiarato il {oggi.isoformat()}] " + " — ".join(parti)


def dichiara_pagamento(
    receivable: Receivable,
    *,
    data_pagamento: datetime.date | None = None,
    estremi=None,
) -> Receivable:
    """Porta l'addebito a DICHIARATO: l'inquilino afferma di aver pagato.

    NON tocca ``importo_pagato``: quel campo riflette la copertura reale
    (allocazioni bonifico) e sovrascriverlo qui azzererebbe il residuo di un
    addebito pagato solo in parte. Gli estremi dichiarati finiscono nelle
    note, a beneficio del proprietario che deve confermare.

    Solo il cambio di stato: l'avviso ai proprietari
    (``billing._notifiche.notifica_dichiarazione_pagamento``) lo manda chi
    chiama, cioè l'endpoint ``dichiara_pagato``.
    """
    receivable.stato = StatoPagamento.DICHIARATO
    receivable.data_pagamento = data_pagamento or datetime.date.today()
    riga_nota = nota_dichiarazione(estremi or {})
    if riga_nota:
        receivable.note = (
            f"{receivable.note}\n{riga_nota}" if receivable.note else riga_nota
        )
    receivable.save(update_fields=["stato", "data_pagamento", "note"])
    return receivable
