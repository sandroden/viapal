"""
Generazione di un OwnerSettlement: chiusura periodica dei conti tra fratelli.

Modello "cassa virtuale": per ciascuna transazione del periodo creiamo voci
ledger la cui somma è zero. La somma per owner ricostruisce il saldo netto.

- Receivable pagato R con importo I incassato fisicamente da B:
    voce INCASSO_AFFITTO per ogni owner X, importo = quota_X · I
    voce AGGIUSTAMENTO per B, importo = -I (B ha già preso i soldi).
    Saldo B = quota_B·I - I = -(1-quota_B)·I  (debito verso gli altri).
    Saldo X≠B = quota_X·I  (credito verso B).

- Expense E con importo I anticipata da A:
    voce SPESA per ogni owner X, importo = -quota_X · I
    voce ANTICIPO per A, importo = +I (la cassa gli rende il di tasca).
    Saldo A = -quota_A·I + I = (1-quota_A)·I  (credito verso gli altri).
    Saldo X≠A = -quota_X·I  (debito verso A).

Tutte le voci sono collegate al settlement via `riferimento_settlement` e al
record sorgente (Receivable/Expense). I vincoli unique parziali ne garantiscono
l'idempotenza senza bisogno di chiavi composite.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from accounting.models import OwnerLedgerEntry, OwnerSettlement
from billing.models import Expense, Receivable
from billing.models.payments import StatoPagamento
from properties.models import OwnerProfile, quote_attive_at


class SettlementGiaEsistente(Exception):
    """Il settlement per questo periodo esiste già: passare reset=True."""


@transaction.atomic
def genera_settlement(
    periodo_da: date,
    periodo_a: date,
    *,
    descrizione: str | None = None,
    reset: bool = False,
    dry_run: bool = False,
) -> OwnerSettlement:
    """Crea o rigenera un OwnerSettlement per il periodo indicato."""
    settlement, created = OwnerSettlement.objects.get_or_create(
        periodo_da=periodo_da,
        periodo_a=periodo_a,
        defaults={
            "data": periodo_a,
            "descrizione": descrizione or f"Chiusura {periodo_da} → {periodo_a}",
            "snapshot": {},
        },
    )
    if not created:
        if not reset:
            raise SettlementGiaEsistente(
                f"Settlement esistente per {periodo_da} → {periodo_a}. "
                f"Passare reset=True per rigenerarlo.",
            )
        settlement.ledger_entries.all().delete()
        if descrizione:
            settlement.descrizione = descrizione

    quote = quote_attive_at(periodo_a)
    if not quote:
        raise ValueError(
            f"Nessuna quota di proprietà attiva al {periodo_a}: impossibile generare il settlement."
        )

    _crea_voci_da_receivable(settlement, periodo_da, periodo_a, quote)
    _crea_voci_da_expense(settlement, periodo_da, periodo_a, quote)

    settlement.snapshot = _calcola_snapshot(settlement, quote)
    settlement.save()

    if dry_run:
        transaction.set_rollback(True)

    return settlement


def _crea_voci_da_receivable(
    settlement: OwnerSettlement,
    periodo_da: date,
    periodo_a: date,
    quote: dict[OwnerProfile, Decimal],
) -> None:
    rec_qs = Receivable.objects.select_related("incassato_da_owner", "assignment__tenant").filter(
        stato=StatoPagamento.PAGATO,
        data_pagamento__gte=periodo_da,
        data_pagamento__lte=periodo_a,
        importo_pagato__isnull=False,
        incassato_da_owner__isnull=False,
    )
    for r in rec_qs:
        importo = r.importo_pagato
        descr_base = f"{r.get_causale_display()} {r.assignment.tenant} {r.competenza_da or r.scadenza}"
        for owner, quota in quote.items():
            OwnerLedgerEntry.objects.create(
                owner=owner,
                data=r.data_pagamento,
                descrizione=f"Quota {descr_base}",
                importo=(quota * importo).quantize(Decimal("0.01")),
                tipo=OwnerLedgerEntry.TipoVoce.INCASSO_AFFITTO,
                riferimento_receivable=r,
                riferimento_settlement=settlement,
            )
        OwnerLedgerEntry.objects.create(
            owner=r.incassato_da_owner,
            data=r.data_pagamento,
            descrizione=f"Versamento alla cassa: {descr_base}",
            importo=-importo,
            tipo=OwnerLedgerEntry.TipoVoce.AGGIUSTAMENTO,
            riferimento_receivable=r,
            riferimento_settlement=settlement,
        )


def _crea_voci_da_expense(
    settlement: OwnerSettlement,
    periodo_da: date,
    periodo_a: date,
    quote: dict[OwnerProfile, Decimal],
) -> None:
    exp_qs = Expense.objects.select_related("category", "anticipata_da_owner").filter(
        data__gte=periodo_da,
        data__lte=periodo_a,
    )
    for e in exp_qs:
        descr_base = f"{e.category.nome} — {e.descrizione}"
        if e.is_straordinaria:
            descr_base = f"[straord] {descr_base}"
        for owner, quota in quote.items():
            OwnerLedgerEntry.objects.create(
                owner=owner,
                data=e.data,
                descrizione=f"Quota {descr_base}",
                importo=-(quota * e.importo).quantize(Decimal("0.01")),
                tipo=OwnerLedgerEntry.TipoVoce.SPESA,
                riferimento_expense=e,
                riferimento_settlement=settlement,
            )
        OwnerLedgerEntry.objects.create(
            owner=e.anticipata_da_owner,
            data=e.data,
            descrizione=f"Anticipo {descr_base}",
            importo=e.importo,
            tipo=OwnerLedgerEntry.TipoVoce.ANTICIPO,
            riferimento_expense=e,
            riferimento_settlement=settlement,
        )


def _calcola_snapshot(
    settlement: OwnerSettlement,
    quote: dict[OwnerProfile, Decimal],
) -> dict[str, str]:
    """Saldo finale per owner: baseline da settlement precedente + voci di
    questo settlement. Espresso come stringhe Decimal nel JSON."""
    prev = OwnerSettlement.objects.filter(
        data__lt=settlement.data,
    ).exclude(pk=settlement.pk).order_by("-data").first()
    snapshot: dict[str, str] = {}
    for owner in quote:
        baseline = Decimal(str(prev.snapshot.get(str(owner.pk), "0"))) if prev else Decimal("0")
        somma = OwnerLedgerEntry.objects.filter(
            owner=owner,
            riferimento_settlement=settlement,
        ).aggregate(t=Sum("importo"))["t"] or Decimal("0")
        snapshot[str(owner.pk)] = str((baseline + somma).quantize(Decimal("0.01")))
    return snapshot
