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
- Spesa con `riferimento_quota_owner` = R (es. Bruna paga IMU di Fabio):
  niente pro-quota, la spesa è interamente di R.
  Contributo per anticipante A: + importo (credito verso R)
  Contributo per R: - importo (debito verso A)
  Altri owner: nessun effetto. Se A == R la spesa è personale e pagata da sé:
  nessun effetto sui saldi.
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
from properties.models import OwnerProfile, Property, quote_attive_at


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


@dataclass
class Quadratura:
    """Esito del controllo di coerenza dei saldi live.

    I saldi sono per costruzione a somma zero *se* ogni flusso ha un
    responsabile con quota attiva. Record "orfani" (Receivable pagato senza
    incassante, anticipante/incassante senza quota attiva) falsano il calcolo
    in silenzio: qui li portiamo a galla.
    """
    somma_saldi: Decimal
    quadra: bool
    receivable_orfani: list[dict] = field(default_factory=list)
    expense_orfane: list[dict] = field(default_factory=list)


def _ultimo_settlement(property: Property, at_date: date) -> tuple[OwnerSettlement | None, date | None]:
    """Ultimo settlement chiuso ≤ at_date dell'immobile e inizio del periodo aperto."""
    last_sett = OwnerSettlement.objects.filter(
        property=property, data__lte=at_date,
    ).order_by("-data").first()
    periodo_da = last_sett.periodo_a + timedelta(days=1) if last_sett else None
    return last_sett, periodo_da


def _baseline_da_settlement(settlement: OwnerSettlement | None, owner: OwnerProfile) -> Decimal:
    if settlement is None:
        return Decimal("0")
    raw = settlement.snapshot.get(str(owner.pk), "0")
    return Decimal(str(raw))


def _aggrega(d: dict[str, Decimal], chiave: str, importo: Decimal) -> None:
    d[chiave] = d.get(chiave, Decimal("0")) + importo


def calcola_saldi_correnti(property: Property, at_date: date) -> dict[OwnerProfile, SaldoLive]:
    """Ritorna {owner: SaldoLive} per i proprietari con quota attiva sull'immobile.

    Il periodo aperto va dal giorno dopo l'ultimo settlement chiuso ≤ at_date
    (incluso) a at_date stesso. Se non esiste alcun settlement, considera
    l'intera storia fino a at_date.
    """
    quote = quote_attive_at(property, at_date)
    if not quote:
        return {}

    last_sett, periodo_da = _ultimo_settlement(property, at_date)

    saldi = {
        owner: SaldoLive(
            owner=owner,
            quota=quota,
            baseline_settlement=_baseline_da_settlement(last_sett, owner),
        )
        for owner, quota in quote.items()
    }

    rec_qs = Receivable.objects.select_related("incassato_da_owner").filter(
        assignment__room__property=property,
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
        property=property,
        data__lte=at_date,
    )
    if periodo_da:
        exp_qs = exp_qs.filter(data__gte=periodo_da)

    owner_pks = {o.pk for o in saldi}
    for e in exp_qs:
        chiave = f"{e.category.codice}|{'straord' if e.is_straordinaria else 'ord'}"
        if e.riferimento_quota_owner_id and e.riferimento_quota_owner_id in owner_pks:
            # Spesa interamente di un owner specifico (es. Bruna paga IMU di Fabio):
            # l'anticipante vanta credito intero su di lui, gli altri non c'entrano.
            if e.riferimento_quota_owner_id == e.anticipata_da_owner_id:
                continue  # spesa personale pagata da sé: nessun effetto fra fratelli
            for owner, saldo in saldi.items():
                if owner.pk == e.anticipata_da_owner_id:
                    saldo.anticipi_pendenti += e.importo
                    _aggrega(saldo.spese_per_categoria, chiave, e.importo)
                elif owner.pk == e.riferimento_quota_owner_id:
                    _aggrega(saldo.spese_per_categoria, chiave, -e.importo)
            continue
        for owner, saldo in saldi.items():
            if owner == e.anticipata_da_owner:
                contributo = (Decimal("1") - saldo.quota) * e.importo
                saldo.anticipi_pendenti += contributo
            else:
                contributo = -saldo.quota * e.importo
            _aggrega(saldo.spese_per_categoria, chiave, contributo)

    led_qs = OwnerLedgerEntry.objects.filter(
        property=property,
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


def verifica_quadratura(property: Property, at_date: date, saldi: dict[OwnerProfile, SaldoLive]) -> Quadratura:
    """Controlla Σ saldi = 0 ed elenca i record orfani del periodo aperto.

    Orfani:
    - Receivable PAGATO senza `incassato_da_owner`: ignorato dal calcolo,
      saldi sottostimati.
    - Receivable con incassante senza quota attiva: gli altri ricevono il
      credito ma nessuno il debito → la somma non fa più zero.
    - Expense con anticipante senza quota attiva: tutti pagano la quota ma
      nessuno riceve il credito → idem.
    """
    _, periodo_da = _ultimo_settlement(property, at_date)
    owner_pks = {o.pk for o in saldi}

    receivable_orfani: list[dict] = []
    rec_qs = Receivable.objects.select_related(
        "incassato_da_owner", "assignment__tenant",
    ).filter(
        assignment__room__property=property,
        stato=StatoPagamento.PAGATO,
        data_pagamento__lte=at_date,
        data_pagamento__isnull=False,
    )
    if periodo_da:
        rec_qs = rec_qs.filter(data_pagamento__gte=periodo_da)
    for r in rec_qs:
        if r.incassato_da_owner_id is None:
            motivo = "manca «incassato da»: escluso dai saldi"
        elif r.incassato_da_owner_id not in owner_pks:
            motivo = f"incassante {r.incassato_da_owner} senza quota attiva"
        else:
            continue
        receivable_orfani.append({
            "id": r.pk,
            "tenant": r.assignment.tenant.nominativo,
            "causale": r.get_causale_display(),
            "importo": r.importo_pagato or Decimal("0"),
            "data": r.data_pagamento,
            "motivo": motivo,
        })

    expense_orfane: list[dict] = []
    exp_qs = Expense.objects.select_related("category", "anticipata_da_owner").filter(
        property=property,
        data__lte=at_date,
    )
    if periodo_da:
        exp_qs = exp_qs.filter(data__gte=periodo_da)
    for e in exp_qs:
        if e.anticipata_da_owner_id in owner_pks:
            continue
        expense_orfane.append({
            "id": e.pk,
            "descrizione": e.descrizione,
            "categoria": e.category.nome,
            "importo": e.importo,
            "data": e.data,
            "motivo": f"anticipante {e.anticipata_da_owner} senza quota attiva",
        })

    somma = sum((s.totale for s in saldi.values()), start=Decimal("0"))
    return Quadratura(
        somma_saldi=somma.quantize(Decimal("0.01")),
        quadra=abs(somma) < Decimal("0.01") and not receivable_orfani and not expense_orfane,
        receivable_orfani=receivable_orfani,
        expense_orfane=expense_orfane,
    )


def calcola_piano_rientro(saldi: dict[OwnerProfile, SaldoLive]) -> list[dict]:
    """Bonifici minimi debitori → creditori per azzerare i saldi live.

    Greedy a due puntatori sui saldi ordinati: max debitore paga max
    creditore. Con N owner produce al più N-1 trasferimenti. Se i saldi non
    quadrano (Σ ≠ 0) il piano copre comunque il min fra crediti e debiti:
    il residuo emerge dalla Quadratura, non da qui.
    """
    cent = Decimal("0.01")
    creditori = [[s.totale.quantize(cent), s.owner] for s in saldi.values() if s.totale >= cent]
    debitori = [[(-s.totale).quantize(cent), s.owner] for s in saldi.values() if s.totale <= -cent]
    creditori.sort(key=lambda x: x[0], reverse=True)
    debitori.sort(key=lambda x: x[0], reverse=True)

    piano: list[dict] = []
    i = j = 0
    while i < len(debitori) and j < len(creditori):
        importo = min(debitori[i][0], creditori[j][0])
        piano.append({
            "da": debitori[i][1],
            "a": creditori[j][1],
            "importo": importo,
        })
        debitori[i][0] -= importo
        creditori[j][0] -= importo
        if debitori[i][0] < cent:
            i += 1
        if creditori[j][0] < cent:
            j += 1
    return piano
