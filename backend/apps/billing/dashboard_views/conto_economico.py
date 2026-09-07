"""
Conto economico dell'immobile (cassa vs competenza).
"""
import datetime
from decimal import Decimal

from django.db.models import Sum
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPropertyMember
from billing.models import Receivable, StatoPagamento

from ._common import CAUSALI_OPERATIVE, _competenza_base

# ---------------------------------------------------------------------------
# Conto economico dell'immobile
# ---------------------------------------------------------------------------

class ContoEconomicoView(APIView):
    """GET /api/v1/dashboard/conto-economico/?anno=YYYY — Solo proprietari.

    Conto economico dell'immobile per anno, in doppia lettura:
    - `cassa`: incassato (data_pagamento) nell'anno;
    - `competenza`: dovuto con competenza nell'anno (affitti/extra per
      competenza_da, utenze per periodo bolletta), insoluti evidenziati.
    Le spese sono per data (unica data disponibile) in entrambe le letture,
    separate in ordinarie e straordinarie.
    Più: utile pro-quota per proprietario, serie multi-anno, occupazione
    stanze da RoomAssignment.
    """

    permission_classes = [IsPropertyMember]

    VOCE_PER_CAUSALE = {
        Receivable.Causale.AFFITTO: "rent",
        Receivable.Causale.UTENZE: "utility",
        Receivable.Causale.EXTRA: "extra",
        Receivable.Causale.REGISTRAZIONE: "extra",
    }

    def get(self, request):
        from django.db.models.functions import ExtractYear

        from billing.models import Expense
        from properties.models import Room, quote_attive_at

        from properties.context import get_request_property

        prop = get_request_property(request)
        oggi = datetime.date.today()
        try:
            anno = int(request.query_params.get("anno", oggi.year))
        except (TypeError, ValueError):
            return Response({"detail": "Parametro 'anno' deve essere intero."}, status=400)

        # --- Ricavi per cassa: incassato nell'anno --------------------------
        ricavi_cassa = {"rent": Decimal("0"), "utility": Decimal("0"), "extra": Decimal("0")}
        for r in Receivable.objects.filter(
            assignment__room__property=prop,
            stato=StatoPagamento.PAGATO,
            data_pagamento__year=anno,
            causale__in=CAUSALI_OPERATIVE,
        ):
            ricavi_cassa[self.VOCE_PER_CAUSALE[r.causale]] += r.importo_pagato or Decimal("0")

        # --- Ricavi per competenza: dovuto maturato nell'anno ---------------
        ricavi_comp = {"rent": Decimal("0"), "utility": Decimal("0"), "extra": Decimal("0")}
        non_incassato = Decimal("0")
        non_incassato_voci = 0
        insoluti = Decimal("0")
        comp_qs = Receivable.objects.filter(
            assignment__room__property=prop,
            causale__in=CAUSALI_OPERATIVE,
        ).select_related("utility_period")
        for r in comp_qs:
            base = _competenza_base(r) or r.scadenza
            if base is None or base.year != anno:
                continue
            dovuto = r.importo_dovuto or Decimal("0")
            ricavi_comp[self.VOCE_PER_CAUSALE[r.causale]] += dovuto
            if r.stato == StatoPagamento.INSOLUTO:
                insoluti += dovuto - (r.importo_pagato or Decimal("0"))
            if r.stato != StatoPagamento.PAGATO:
                residuo = dovuto - (r.importo_pagato or Decimal("0"))
                if residuo > 0:
                    non_incassato += residuo
                    non_incassato_voci += 1

        # --- Spese: ordinarie e straordinarie per categoria -----------------
        spese_ord: dict[str, Decimal] = {}
        spese_straord: dict[str, Decimal] = {}
        for sp in Expense.objects.filter(
            property=prop, data__year=anno,
        ).select_related("category"):
            target = spese_straord if sp.is_straordinaria else spese_ord
            cat = sp.category.nome if sp.category else "Senza categoria"
            target[cat] = target.get(cat, Decimal("0")) + sp.importo

        tot_ord = sum(spese_ord.values(), start=Decimal("0"))
        tot_straord = sum(spese_straord.values(), start=Decimal("0"))

        def _blocco(ricavi: dict[str, Decimal]) -> dict:
            tot_ricavi = sum(ricavi.values(), start=Decimal("0"))
            margine = tot_ricavi - tot_ord
            utile = margine - tot_straord
            return {
                "ricavi": {**{k: float(v) for k, v in ricavi.items()}, "totale": float(tot_ricavi)},
                "spese_ordinarie": float(tot_ord),
                "margine_operativo": float(margine),
                "spese_straordinarie": float(tot_straord),
                "utile": float(utile),
            }

        blocco_cassa = _blocco(ricavi_cassa)
        blocco_comp = _blocco(ricavi_comp)

        def _per_categoria(d: dict[str, Decimal]) -> list[dict]:
            return sorted(
                [{"nome": k, "importo": float(v)} for k, v in d.items()],
                key=lambda x: -x["importo"],
            )

        # --- Utile pro-quota -------------------------------------------------
        data_quote = min(datetime.date(anno, 12, 31), oggi)
        quote = quote_attive_at(prop, data_quote)
        utile_pro_quota = [
            {
                "owner_id": owner.pk,
                "nominativo": owner.nominativo,
                "quota": float(quota),
                "utile_cassa": round(float(quota) * blocco_cassa["utile"], 2),
                "utile_competenza": round(float(quota) * blocco_comp["utile"], 2),
            }
            for owner, quota in sorted(quote.items(), key=lambda kv: kv[0].nominativo)
        ]

        # --- Serie multi-anno (per cassa) ------------------------------------
        ricavi_per_anno = {
            row["y"]: row["t"] or Decimal("0")
            for row in Receivable.objects.filter(
                assignment__room__property=prop,
                stato=StatoPagamento.PAGATO,
                data_pagamento__isnull=False,
                causale__in=CAUSALI_OPERATIVE,
            ).annotate(y=ExtractYear("data_pagamento")).values("y").annotate(t=Sum("importo_pagato"))
        }
        spese_per_anno = {
            row["y"]: row["t"] or Decimal("0")
            for row in Expense.objects.filter(property=prop)
            .annotate(y=ExtractYear("data"))
            .values("y").annotate(t=Sum("importo"))
        }
        anni = sorted(set(ricavi_per_anno) | set(spese_per_anno))
        serie_anni = [
            {
                "anno": y,
                "ricavi": float(ricavi_per_anno.get(y, Decimal("0"))),
                "spese": float(spese_per_anno.get(y, Decimal("0"))),
                "utile": float(ricavi_per_anno.get(y, Decimal("0")) - spese_per_anno.get(y, Decimal("0"))),
            }
            for y in anni
        ]

        # --- Occupazione stanze ----------------------------------------------
        finestra_da = datetime.date(anno, 1, 1)
        finestra_a = min(datetime.date(anno, 12, 31), oggi)
        occupazione = []
        if finestra_a >= finestra_da:
            giorni_finestra = (finestra_a - finestra_da).days + 1
            for room in Room.objects.filter(property=prop).order_by("ordinamento"):
                giorni_occupati = 0
                for a in room.assignments.filter(
                    valid_from__lte=finestra_a,
                ).exclude(valid_to__lt=finestra_da).exclude(rinunciata=True):
                    da = max(a.valid_from, finestra_da)
                    a_fine = min(a.valid_to or finestra_a, finestra_a)
                    if a_fine >= da:
                        giorni_occupati += (a_fine - da).days + 1
                giorni_occupati = min(giorni_occupati, giorni_finestra)
                occupazione.append({
                    "stanza": room.nome,
                    "giorni_occupati": giorni_occupati,
                    "giorni_finestra": giorni_finestra,
                    "tasso": round(giorni_occupati / giorni_finestra, 4),
                })
        tasso_medio = (
            round(sum(o["tasso"] for o in occupazione) / len(occupazione), 4)
            if occupazione else None
        )

        return Response({
            "anno": anno,
            "anni_disponibili": anni or [anno],
            "cassa": blocco_cassa,
            "competenza": {
                **blocco_comp,
                "non_incassato": float(non_incassato),
                "non_incassato_voci": non_incassato_voci,
                "insoluti": float(insoluti),
            },
            "spese_dettaglio": {
                "ordinarie": _per_categoria(spese_ord),
                "straordinarie": _per_categoria(spese_straord),
            },
            "utile_pro_quota": utile_pro_quota,
            "serie_anni": serie_anni,
            "occupazione": {
                "tasso_medio": tasso_medio,
                "per_stanza": occupazione,
            },
        })
