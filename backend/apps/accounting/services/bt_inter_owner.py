"""
Marcatura di una BankTransaction come transazione inter-owner.

Quattro tipologie:
- distribuzione / incasso_conguaglio: 2 voci OwnerLedgerEntry simmetriche
  fra il proprietario del conto (bt.owner_account.owner) e una controparte.
- bilaterale: 1 InterOwnerEntry (Livello B), per movimenti privati come
  prestiti o restituzioni che non passano dalla cassa virtuale.
- aggiustamento: 1 OwnerLedgerEntry libera sul proprietario del conto.

Tutte le scritture sono atomiche e proteggono dalla concorrenza con un
SELECT FOR UPDATE sulla BT.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction

from accounting.models import InterOwnerEntry, OwnerLedgerEntry, OwnerSettlement
from billing.models.payments import BankTransaction
from properties.models import OwnerProfile, Property

TIPI_LEDGER_SIMMETRICI = {
    "distribuzione": OwnerLedgerEntry.TipoVoce.DISTRIBUZIONE,
    "incasso_conguaglio": OwnerLedgerEntry.TipoVoce.INCASSO_CONGUAGLIO,
}


class BTGiaMarcata(Exception):
    """La BT ha già voci ledger collegate: chiamare prima disfa_marcatura."""


@transaction.atomic
def marca_bt_come_ledger(
    bt: BankTransaction,
    *,
    property: Property,
    tipo: str,
    controparte_owner: OwnerProfile | None = None,
    settlement: OwnerSettlement | None = None,
    descrizione: str = "",
    note: str = "",
) -> list[Any]:
    if settlement is not None and settlement.property_id != property.pk:
        raise ValueError("Il settlement indicato appartiene a un altro immobile.")
    bt = BankTransaction.objects.select_for_update().get(pk=bt.pk)
    if bt.ledger_entries.exists() or bt.inter_owner_entries.exists():
        raise BTGiaMarcata(
            f"La BT {bt.pk} ha già voci ledger collegate. "
            f"Chiamare prima disfa_marcatura()."
        )

    proprietario_bt = bt.owner_account.owner
    importo: Decimal = bt.importo

    if tipo in TIPI_LEDGER_SIMMETRICI:
        if controparte_owner is None:
            raise ValueError(f"controparte_owner richiesto per tipo={tipo!r}")
        if controparte_owner == proprietario_bt:
            raise ValueError("controparte_owner deve essere diverso dal proprietario del conto")
        tipo_voce = TIPI_LEDGER_SIMMETRICI[tipo]
        descr = descrizione or f"{tipo_voce.label} con {controparte_owner.nominativo}"
        v_ricevente = OwnerLedgerEntry.objects.create(
            property=property,
            owner=proprietario_bt,
            data=bt.data,
            importo=importo,
            tipo=tipo_voce,
            descrizione=descr,
            bank_transaction=bt,
            riferimento_settlement=settlement,
            note=note,
        )
        v_controparte = OwnerLedgerEntry.objects.create(
            property=property,
            owner=controparte_owner,
            data=bt.data,
            importo=-importo,
            tipo=tipo_voce,
            descrizione=descr,
            bank_transaction=bt,
            riferimento_settlement=settlement,
            note=note,
        )
        return [v_ricevente, v_controparte]

    if tipo == "bilaterale":
        if controparte_owner is None:
            raise ValueError("controparte_owner richiesto per tipo='bilaterale'")
        if controparte_owner == proprietario_bt:
            raise ValueError("controparte_owner deve essere diverso dal proprietario del conto")
        if importo >= 0:
            owner_da, owner_a = controparte_owner, proprietario_bt
        else:
            owner_da, owner_a = proprietario_bt, controparte_owner
        entry = InterOwnerEntry.objects.create(
            property=property,
            owner_da=owner_da,
            owner_a=owner_a,
            data=bt.data,
            importo=abs(importo),
            descrizione=descrizione or f"Movimento {owner_da} → {owner_a}",
            bank_transaction=bt,
            riferimento_settlement=settlement,
            note=note,
        )
        return [entry]

    if tipo == "aggiustamento":
        voce = OwnerLedgerEntry.objects.create(
            property=property,
            owner=proprietario_bt,
            data=bt.data,
            importo=importo,
            tipo=OwnerLedgerEntry.TipoVoce.AGGIUSTAMENTO,
            descrizione=descrizione or "Aggiustamento da BT",
            bank_transaction=bt,
            riferimento_settlement=settlement,
            note=note,
        )
        return [voce]

    raise ValueError(
        f"tipo {tipo!r} non riconosciuto. Validi: distribuzione, "
        f"incasso_conguaglio, bilaterale, aggiustamento."
    )


@transaction.atomic
def disfa_marcatura(bt: BankTransaction) -> int:
    """Cancella tutte le voci ledger A e B collegate alla BT."""
    bt = BankTransaction.objects.select_for_update().get(pk=bt.pk)
    n_a, _ = bt.ledger_entries.all().delete()
    n_b, _ = bt.inter_owner_entries.all().delete()
    return n_a + n_b
