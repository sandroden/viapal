"""
Saldi pro-quota fra proprietari calcolati al volo, mai persistiti.

Filosofia: durante l'anno non scriviamo voci ledger automatiche (eviterebbe
rumore — 30 spese × 3 fratelli = 90 voci inutili). La pagina "Saldi fratelli"
mostra invece la situazione live a una data, pescando da Receivable pagati,
Expense, voci ledger di BT marcate inter-owner e baseline dell'ultimo
OwnerSettlement chiuso.

Convenzione: il saldo di un owner X esprime il netto fra "credito che vanta
sugli altri" (>0) e "debito verso gli altri" (<0).

- Spesa anticipata di tasca da X: X paga, gli altri gli devono pro-quota.
  Contributo per X: + (1 - quota_X) * importo
  Contributo per Y ≠ X: - quota_Y * importo
- Incasso fisico ricevuto da X: X tiene i soldi che spettano pro-quota a tutti
  e quindi *deve* agli altri la loro fetta.
  Contributo per X: - (1 - quota_X) * importo  (debito verso gli altri)
  Contributo per Y ≠ X: + quota_Y * importo    (credito verso X)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from accounting.models import OwnerLedgerEntry, OwnerSettlement
from billing.models import Expense, Receivable
from billing.models.payments import StatoPagamento
from properties.models import OwnerProfile, quote_attive_at


@dataclass
class SaldoLive:
    """Saldo netto pro-quota di un owner alla data, con decomposizione."""
    owner: OwnerProfile
    quota: Decimal
    baseline_settlement: Decimal
    incassi_per_causale: dict[str, Decimal] = field(default_factory=dict)
    spese_per_categoria: dict[str, Decimal] = field(default_factory=dict)
    anticipi_pendenti: Decimal = Decimal("0")
    bt_inter_owner: Decimal = Decimal("0")
    totale: Decimal = Decimal("0")


def _baseline_da_settlement(settlement: OwnerSettlement | None, owner: OwnerProfile) -> Decimal:
    if settlement is None:
        return Decimal("0")
    raw = settlement.snapshot.get(str(owner.pk), "0")
    return Decimal(str(raw))


def _aggrega(d: dict[str, Decimal], chiave: str, importo: Decimal) -> None:
    d[chiave] = d.get(chiave, Decimal("0")) + importo


def calcola_saldi_correnti(at_date: date) -> dict[OwnerProfile, SaldoLive]:
    """Ritorna {owner: SaldoLive} per tutti i proprietari con quota attiva.

    Il periodo aperto va dal giorno dopo l'ultimo settlement chiuso ≤ at_date
    (incluso) a at_date stesso. Se non esiste alcun settlement, considera
    l'intera storia fino a at_date.
    """
    quote = quote_attive_at(at_date)
    if not quote:
        return {}

    last_sett = OwnerSettlement.objects.filter(data__lte=at_date).order_by("-data").first()
    periodo_da = last_sett.periodo_a + timedelta(days=1) if last_sett else None

    saldi = {
        owner: SaldoLive(
            owner=owner,
            quota=quota,
            baseline_settlement=_baseline_da_settlement(last_sett, owner),
        )
        for owner, quota in quote.items()
    }

    rec_qs = Receivable.objects.select_related("incassato_da_owner").filter(
        stato=StatoPagamento.PAGATO,
        data_pagamento__lte=at_date,
        data_pagamento__isnull=False,
        importo_pagato__isnull=False,
    )
    if periodo_da:
        rec_qs = rec_qs.filter(data_pagamento__gte=periodo_da)

    for r in rec_qs:
        if r.incassato_da_owner is None:
            continue
        importo = r.importo_pagato or Decimal("0")
        for owner, saldo in saldi.items():
            if owner == r.incassato_da_owner:
                # Tiene i soldi pro-quota di tutti: deve restituire la fetta degli altri.
                contributo = -(Decimal("1") - saldo.quota) * importo
            else:
                # Vanta credito sull'incassante per la propria quota.
                contributo = saldo.quota * importo
            _aggrega(saldo.incassi_per_causale, r.causale, contributo)

    exp_qs = Expense.objects.select_related("category", "anticipata_da_owner").filter(
        data__lte=at_date,
    )
    if periodo_da:
        exp_qs = exp_qs.filter(data__gte=periodo_da)

    for e in exp_qs:
        chiave = f"{e.category.codice}|{'straord' if e.is_straordinaria else 'ord'}"
        for owner, saldo in saldi.items():
            if owner == e.anticipata_da_owner:
                contributo = (Decimal("1") - saldo.quota) * e.importo
                saldo.anticipi_pendenti += contributo
            else:
                contributo = -saldo.quota * e.importo
            _aggrega(saldo.spese_per_categoria, chiave, contributo)

    led_qs = OwnerLedgerEntry.objects.filter(
        bank_transaction__isnull=False,
        data__lte=at_date,
    )
    if periodo_da:
        led_qs = led_qs.filter(data__gte=periodo_da)

    for v in led_qs:
        if v.owner_id in {o.pk for o in saldi}:
            owner = next(o for o in saldi if o.pk == v.owner_id)
            saldi[owner].bt_inter_owner += v.importo

    for saldo in saldi.values():
        saldo.totale = (
            saldo.baseline_settlement
            + sum(saldo.incassi_per_causale.values(), start=Decimal("0"))
            + sum(saldo.spese_per_categoria.values(), start=Decimal("0"))
            + saldo.bt_inter_owner
        )

    return saldi
