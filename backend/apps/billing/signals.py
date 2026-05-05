"""Signal handlers per il package billing.

Mantengono coerenti i campi denormalizzati di ``Receivable``
(``stato``/``data_pagamento``/``importo_pagato``/``incassato_da_owner``) con
le ``BankTransactionAllocation`` che lo coprono.

Cosa succede:

- **Aggiungi/modifichi un'allocation in admin** → il Receivable viene
  riallineato (PAGATO se la somma allocations ≥ dovuto, altrimenti ATTESO
  con ``importo_pagato`` parziale).
- **Cancelli un'allocation** → idem, eventualmente torna ad ATTESO.

Così l'utente in admin può semplicemente abbinare un BT a un Receivable
esistente: lo stato si aggiorna automaticamente, senza bisogno di toccare
campi separati sul Receivable.
"""
from decimal import Decimal

from django.db.models import Max, Sum
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from billing.models import BankTransactionAllocation
from billing.models.payments import StatoPagamento

_SOGLIA = Decimal("1.00")


def _riallinea_receivable(receivable_id: int) -> None:
    """Ricalcola stato/data_pagamento/importo_pagato/incassato_da_owner del
    Receivable a partire dalle sue allocations attuali."""
    from billing.models import Receivable

    try:
        r = Receivable.objects.get(pk=receivable_id)
    except Receivable.DoesNotExist:
        return

    agg = r.allocations.aggregate(
        tot=Sum("importo"), data_max=Max("bank_transaction__data")
    )
    tot = agg["tot"] or Decimal("0")
    data_max = agg["data_max"]

    if tot <= 0:
        r.stato = StatoPagamento.ATTESO
        r.data_pagamento = None
        r.importo_pagato = None
        r.incassato_da_owner = None
    elif tot + _SOGLIA >= r.importo_dovuto:
        r.stato = StatoPagamento.PAGATO
        r.data_pagamento = data_max
        r.importo_pagato = tot
        ultima = r.allocations.order_by("-bank_transaction__data").select_related(
            "bank_transaction__owner_account"
        ).first()
        if ultima:
            r.incassato_da_owner_id = ultima.bank_transaction.owner_account.owner_id
    else:
        # Pagamento parziale: lasciamo stato ATTESO ma teniamo traccia.
        r.stato = StatoPagamento.ATTESO
        r.data_pagamento = data_max
        r.importo_pagato = tot
        ultima = r.allocations.order_by("-bank_transaction__data").select_related(
            "bank_transaction__owner_account"
        ).first()
        if ultima:
            r.incassato_da_owner_id = ultima.bank_transaction.owner_account.owner_id

    r.save(
        update_fields=[
            "stato",
            "data_pagamento",
            "importo_pagato",
            "incassato_da_owner",
            "updated_at",
        ]
    )


@receiver(post_save, sender=BankTransactionAllocation)
def _on_alloc_saved(sender, instance, **kwargs):
    _riallinea_receivable(instance.receivable_id)


@receiver(post_delete, sender=BankTransactionAllocation)
def _on_alloc_deleted(sender, instance, **kwargs):
    _riallinea_receivable(instance.receivable_id)
