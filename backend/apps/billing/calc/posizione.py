"""
Posizione contabile di un inquilino: **una sola formula** del residuo.

Nel progetto convivono tre modi di calcolare "quanto deve": la home inquilino
(``dovuto − pagato``), i serializer (``dovuto − Σ allocazioni``) e il signal
``_riallinea_receivable`` (con soglia di 1 €). Qui si adotta quella della home
— che è ciò che l'inquilino vede in ``/i/`` — e la si rende riusabile: le
email di sollecito devono riportare **gli stessi numeri** della pagina che
l'inquilino aprirà per pagare.

Conseguenza voluta della soglia di 1 € in ``billing/signals.py``: un residuo
sotto l'euro è già ``PAGATO``, quindi gli spiccioli non entrano nei solleciti.

I ``Decimal`` restano ``Decimal``: la conversione a ``float`` sta nella view
(che serializza JSON) e nella costruzione dei dict email, non qui — altrimenti
uscirebbero stringhe serializzate dall'API.
"""
import datetime
from decimal import Decimal

from django.db.models import Q

from billing.models import Receivable, StatoPagamento
from properties.models import RoomAssignment


def posizione_inquilino(
    tenant, oggi: datetime.date, property=None
) -> dict:
    """Tutto quello che l'inquilino deve, alla data ``oggi``.

    Ritorna un dict con:

    * ``items`` — gli addebiti aperti nel formato della home (float per gli
      importi, come li consuma il frontend), ordinati per scadenza;
      ``items == aperti + in_attesa``;
    * ``aperti`` / ``in_attesa`` — partizione per stato: ``in_attesa`` sono i
      ``dichiarato`` (l'inquilino dice di aver pagato, il bonifico non è
      ancora stato trovato). Servono a impaginare la mail in due sezioni; il
      totale li comprende entrambi;
    * ``totale_residuo``, ``totale_aperti``, ``totale_in_attesa`` — Decimal;
    * ``credito_disponibile`` — resti dei bonifici mai imputati (clamp a 0);
    * ``netto_da_versare`` — ``max(0, totale_residuo − credito)``: l'unico
      "netto" del progetto;
    * ``assignment_attivo`` — il ``RoomAssignment`` in corso, o ``None``
      (inquilino uscito);
    * ``conto_cumulativo`` — il conto per il pagamento unico.

    ``conto_cumulativo`` replica la regola della home
    (``property.bank_account_utenze`` + IBAN valido) e **ignora**
    deliberatamente ``assignment.bank_account_affitto``, a differenza di
    ``conto_per_receivable``: è una divergenza pre-esistente, mantenuta per
    parità con ciò che l'inquilino vede in ``/i/``.
    """
    from billing._payments import iban_valido
    from billing.dashboard_views import (
        CAUSALI_OPERATIVE,
        STATI_DA_PAGARE,
        _alloc_per_receivable,
        _build_item_da_pagare,
        _commenti_per_receivable,
        _resti_per_anno,
    )

    assignments = RoomAssignment.objects.filter(tenant=tenant)
    if property is not None:
        assignments = assignments.filter(room__property=property)

    from properties.models.tenant import assegnazione_in_corso_q

    assignment_attivo = RoomAssignment.objects.select_related(
        "room__property__bank_account_utenze", "tenant"
    ).filter(assegnazione_in_corso_q(oggi), tenant=tenant)
    if property is not None:
        assignment_attivo = assignment_attivo.filter(room__property=property)
    assignment_attivo = assignment_attivo.first()

    da_pagare_qs = (
        Receivable.objects.filter(
            assignment__in=assignments,
            stato__in=STATI_DA_PAGARE,
        )
        .filter(
            # Oltre alle causali operative, le rate di versamento del
            # deposito (importo positivo). Le restituzioni (negative)
            # non sono un debito dell'inquilino e restano fuori.
            Q(causale__in=CAUSALI_OPERATIVE)
            | Q(
                causale=Receivable.Causale.DEPOSITO,
                importo_dovuto__gt=0,
            )
        )
        .select_related(
            "assignment__tenant",
            "assignment__room__property__bank_account_utenze",
            "assignment__bank_account_affitto",
            "utility_period",
        )
        .order_by("scadenza")
    )

    da_pagare_list = list(da_pagare_qs)
    alloc_map = _alloc_per_receivable(da_pagare_list)
    commenti_map = _commenti_per_receivable(da_pagare_list)
    items = [
        _build_item_da_pagare(
            r, oggi, alloc_map.get(r.id, []), commenti_map.get(r.id, [])
        )
        for r in da_pagare_list
    ]

    aperti = [x for x in items if x["stato"] != StatoPagamento.DICHIARATO]
    in_attesa = [x for x in items if x["stato"] == StatoPagamento.DICHIARATO]

    def _somma(lista) -> Decimal:
        return sum(
            (Decimal(str(x["residuo"])) for x in lista), Decimal("0")
        )

    totale_residuo = _somma(items)
    # Credito già versato e non ancora imputato a nessuna bolletta: sono i
    # "resti dei bonifici" (versato − somma allocazioni), gli stessi che lo
    # sbilancio reale della pagina Situazione riaggiunge. Vanno scalati dal
    # totale proposto: chiedere il lordo creerebbe uno sbilancio a favore
    # della proprietà per soldi che l'inquilino ha già versato.
    credito_disponibile = sum(_resti_per_anno(tenant).values(), Decimal("0"))
    if credito_disponibile < 0:
        credito_disponibile = Decimal("0")
    netto_da_versare = totale_residuo - credito_disponibile
    if netto_da_versare < 0:
        netto_da_versare = Decimal("0")

    prop = (
        getattr(assignment_attivo.room, "property", None)
        if assignment_attivo
        else None
    )
    conto_cumulativo = prop.bank_account_utenze if prop else None
    if conto_cumulativo and not iban_valido(conto_cumulativo.iban):
        conto_cumulativo = None

    return {
        "items": items,
        "aperti": aperti,
        "in_attesa": in_attesa,
        "totale_residuo": totale_residuo,
        "totale_aperti": _somma(aperti),
        "totale_in_attesa": _somma(in_attesa),
        "credito_disponibile": credito_disponibile,
        "netto_da_versare": netto_da_versare,
        "assignment_attivo": assignment_attivo,
        "conto_cumulativo": conto_cumulativo,
    }
