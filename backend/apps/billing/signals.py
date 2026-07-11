"""Signal handlers per il package billing.

Mantengono coerenti i campi denormalizzati di ``Receivable``
(``stato``/``data_pagamento``/``importo_pagato``/``incassato_da_owner``) con
le ``BankTransactionAllocation`` che lo coprono e generano automaticamente
``Expense`` dalle bollette ``UtilityBill`` con ``pagata_da_owner``
valorizzato.

Cosa succede:

- **Aggiungi/modifichi un'allocation in admin** → il Receivable viene
  riallineato (PAGATO se la somma allocations ≥ dovuto, altrimenti ATTESO
  con ``importo_pagato`` parziale).
- **Cancelli un'allocation** → idem, eventualmente torna ad ATTESO.
- **Salvi una UtilityBill con pagata_da_owner valorizzato** → viene creato
  o aggiornato l'``Expense`` collegato (categoria "Utenze").
- **Rimuovi pagata_da_owner o cancelli la bolletta** → l'``Expense``
  collegato viene cancellato.
"""
from decimal import Decimal

from django.db.models import Max, Sum
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from billing.models import BankTransactionAllocation, UtilityBill
from billing.models.payments import StatoPagamento

_SOGLIA = Decimal("1.00")


def _riallinea_receivable(receivable_id: int) -> None:
    """Ricalcola stato/data_pagamento/importo_pagato/incassato_da_owner del
    Receivable a partire dalle sue allocations attuali.

    Logica segno-aware: l'invariante è ``sign(alloc.importo) ==
    sign(Receivable.importo_dovuto)``. La chiusura avviene quando la somma
    delle allocations (con segno) copre il dovuto in valore assoluto.
    Le allocations sulla stessa BT possono avere segni discordi tra loro
    (es. restituzione deposito con trattenuta utenze), ma per ogni singolo
    Receivable concordano col dovuto.
    """
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
    dovuto = r.importo_dovuto

    def _set_incassato_da_owner():
        ultima = r.allocations.order_by("-bank_transaction__data").select_related(
            "bank_transaction__owner_account"
        ).first()
        if ultima:
            r.incassato_da_owner_id = ultima.bank_transaction.owner_account.owner_id

    segni_discordi = (tot > 0 and dovuto < 0) or (tot < 0 and dovuto > 0)
    if tot == 0 or segni_discordi:
        # Nessuna allocazione utile o allocazioni con segno opposto al dovuto:
        # consideriamo il Receivable non coperto.
        r.stato = StatoPagamento.ATTESO
        r.data_pagamento = None
        r.importo_pagato = None
        r.incassato_da_owner = None
    elif abs(tot) + _SOGLIA >= abs(dovuto):
        r.stato = StatoPagamento.PAGATO
        r.data_pagamento = data_max
        r.importo_pagato = tot
        _set_incassato_da_owner()
    else:
        # Pagamento parziale: lasciamo stato ATTESO ma teniamo traccia.
        r.stato = StatoPagamento.ATTESO
        r.data_pagamento = data_max
        r.importo_pagato = tot
        _set_incassato_da_owner()

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


# ---------------------------------------------------------------------------
# UtilityBill -> Expense
# ---------------------------------------------------------------------------


CATEGORIA_UTENZE_CODICE = "utenze"
CATEGORIA_UTENZE_NOME = "Utenze"


def _descrizione_expense_da_bolletta(bill: "UtilityBill") -> str:
    parti = [bill.get_prodotto_display(), bill.supplier.nome]
    if bill.numero_fattura:
        parti.append(f"n. {bill.numero_fattura}")
    parti.append(f"{bill.periodo_da.isoformat()} → {bill.periodo_a.isoformat()}")
    descr = " — ".join(parti)
    return descr[:300]


def sincronizza_expense_da_bolletta(bill: "UtilityBill") -> "Expense | None":
    """Crea/aggiorna/cancella l'Expense collegato a una UtilityBill in base a
    ``pagata_da_owner``.

    Aggiorna il FK ``UtilityBill.expense`` con ``.update()`` per evitare di
    ri-triggerare il post_save.
    """
    from billing.models import Expense, ExpenseCategory

    if bill.pagata_da_owner_id is None:
        # Bolletta non pagata da un proprietario: rimuovi Expense se esiste.
        if bill.expense_id:
            old = bill.expense_id
            UtilityBill.objects.filter(pk=bill.pk).update(expense=None)
            Expense.objects.filter(pk=old).delete()
        return None

    cat, _ = ExpenseCategory.objects.get_or_create(
        property_id=bill.immobile_id,
        codice=CATEGORIA_UTENZE_CODICE,
        defaults={"nome": CATEGORIA_UTENZE_NOME, "ripartibile_inquilini": True},
    )
    descrizione = _descrizione_expense_da_bolletta(bill)

    if bill.expense_id:
        Expense.objects.filter(pk=bill.expense_id).update(
            data=bill.data_emissione,
            category=cat,
            supplier=bill.supplier,
            importo=bill.importo_totale,
            descrizione=descrizione,
            anticipata_da_owner=bill.pagata_da_owner,
        )
        return Expense.objects.get(pk=bill.expense_id)

    expense = Expense.objects.create(
        property_id=bill.immobile_id,
        data=bill.data_emissione,
        category=cat,
        supplier=bill.supplier,
        importo=bill.importo_totale,
        descrizione=descrizione,
        anticipata_da_owner=bill.pagata_da_owner,
    )
    UtilityBill.objects.filter(pk=bill.pk).update(expense=expense)
    return expense


@receiver(post_save, sender=UtilityBill)
def _on_utility_bill_saved(sender, instance, **kwargs):
    sincronizza_expense_da_bolletta(instance)


@receiver(pre_delete, sender=UtilityBill)
def _on_utility_bill_deleted(sender, instance, **kwargs):
    from billing.models import Expense

    if instance.expense_id:
        Expense.objects.filter(pk=instance.expense_id).delete()
