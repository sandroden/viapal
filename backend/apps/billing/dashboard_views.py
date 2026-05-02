"""
Endpoint custom per le dashboard inquilino, proprietario e quadro annuale.
"""
import datetime
from decimal import Decimal
from itertools import chain

from django.db.models import Q, Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsInquilino, IsProprietario
from billing.models import ExtraCharge, RentPayment, StatoPagamento, UtilityCharge, UtilityChargePeriod
from properties.models import RoomAssignment, TenantProfile
from properties.serializers import TenantProfileSerializer, RoomAssignmentSerializer


# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

STATI_DA_PAGARE = {
    StatoPagamento.ATTESO,
    StatoPagamento.IN_RITARDO,
    StatoPagamento.INSOLUTO,
    StatoPagamento.DICHIARATO,
}


def _calcola_semaforo(giorni_ritardo: int) -> str:
    """
    Restituisce il colore semaforo in base ai giorni di ritardo.
    giorni_ritardo > 0 → in ritardo; < 0 → mancano giorni.
    """
    if giorni_ritardo > 7:
        return "argilla_scuro"
    if giorni_ritardo > 0:
        return "argilla_chiaro"
    if giorni_ritardo > -7:
        return "miele"
    return "salvia"


def _giorni_ritardo(scadenza: datetime.date, oggi: datetime.date) -> int:
    """
    Positivo = in ritardo di N giorni.
    Negativo = mancano N giorni alla scadenza.
    """
    return (oggi - scadenza).days


def _build_item_da_pagare(
    tipo: str,
    obj_id: int,
    descrizione: str,
    importo: Decimal,
    scadenza: datetime.date,
    stato: str,
    oggi: datetime.date,
) -> dict:
    giorni = _giorni_ritardo(scadenza, oggi)
    return {
        "tipo": tipo,
        "id": obj_id,
        "descrizione": descrizione,
        "importo": float(importo),
        "scadenza": scadenza.isoformat(),
        "stato": stato,
        "giorni_ritardo": giorni,
        "semaforo": _calcola_semaforo(giorni),
    }


# ---------------------------------------------------------------------------
# Dashboard inquilino
# ---------------------------------------------------------------------------

class DashboardInquilinoView(APIView):
    """GET /api/v1/dashboard/inquilino/ — Home dell'inquilino."""

    permission_classes = [IsInquilino]

    def get(self, request):
        user = request.user
        oggi = datetime.date.today()

        # Profilo inquilino
        try:
            tenant = TenantProfile.objects.select_related("user").get(user=user)
        except TenantProfile.DoesNotExist:
            return Response(
                {"detail": "Profilo inquilino non trovato."},
                status=404,
            )

        # Assignment attivo
        assignment_attivo = (
            RoomAssignment.objects.select_related("room", "tenant")
            .filter(tenant=tenant, valid_from__lte=oggi)
            .filter(Q(valid_to__isnull=True) | Q(valid_to__gt=oggi))
            .first()
        )

        stanza_corrente = None
        if assignment_attivo:
            stanza_corrente = {
                "id": assignment_attivo.room.id,
                "nome": assignment_attivo.room.nome,
                "canone_mensile": float(assignment_attivo.canone_mensile),
                "valid_from": assignment_attivo.valid_from.isoformat(),
            }

        # Tutti gli assignment dell'inquilino (per rent + charge + extra)
        assignments = RoomAssignment.objects.filter(tenant=tenant)

        # Da pagare: RentPayment
        rent_da_pagare = RentPayment.objects.filter(
            assignment__in=assignments,
            stato__in=STATI_DA_PAGARE,
        ).select_related("assignment__room").order_by("scadenza")

        # Da pagare: UtilityCharge
        charge_da_pagare = UtilityCharge.objects.filter(
            assignment__in=assignments,
            stato__in=STATI_DA_PAGARE,
        ).select_related("assignment__room", "period").order_by("scadenza")

        # Da pagare: ExtraCharge
        extra_da_pagare = ExtraCharge.objects.filter(
            assignment__in=assignments,
            stato__in=STATI_DA_PAGARE,
        ).select_related("assignment__room").order_by("scadenza")

        da_pagare = []

        for r in rent_da_pagare:
            mese = r.competenza_da.strftime("%B %Y")
            da_pagare.append(_build_item_da_pagare(
                tipo="rent",
                obj_id=r.id,
                descrizione=f"Affitto {mese}",
                importo=r.importo_dovuto,
                scadenza=r.scadenza,
                stato=r.stato,
                oggi=oggi,
            ))

        for c in charge_da_pagare:
            mese = c.period.periodo_da.strftime("%B %Y")
            da_pagare.append(_build_item_da_pagare(
                tipo="utility_charge",
                obj_id=c.id,
                descrizione=f"Conguaglio utenze {mese}",
                importo=c.importo_totale,
                scadenza=c.scadenza,
                stato=c.stato,
                oggi=oggi,
            ))

        for e in extra_da_pagare:
            da_pagare.append(_build_item_da_pagare(
                tipo="extra",
                obj_id=e.id,
                descrizione=e.descrizione,
                importo=e.importo,
                scadenza=e.scadenza,
                stato=e.stato,
                oggi=oggi,
            ))

        # Ordina per scadenza
        da_pagare.sort(key=lambda x: x["scadenza"])

        # Ultimi 10 pagamenti confermati (rent + charge)
        ultimi_rent = (
            RentPayment.objects.filter(assignment__in=assignments, stato=StatoPagamento.PAGATO)
            .select_related("assignment__room")
            .order_by("-data_pagamento")[:5]
        )
        ultimi_charge = (
            UtilityCharge.objects.filter(assignment__in=assignments, stato=StatoPagamento.PAGATO)
            .select_related("assignment__room", "period")
            .order_by("-data_pagamento")[:5]
        )

        ultimi_pagamenti = []
        for r in ultimi_rent:
            ultimi_pagamenti.append({
                "tipo": "rent",
                "id": r.id,
                "descrizione": f"Affitto {r.competenza_da.strftime('%B %Y')}",
                "importo": float(r.importo_pagato or r.importo_dovuto),
                "data_pagamento": r.data_pagamento.isoformat() if r.data_pagamento else None,
                "stato": r.stato,
            })
        for c in ultimi_charge:
            ultimi_pagamenti.append({
                "tipo": "utility_charge",
                "id": c.id,
                "descrizione": f"Conguaglio {c.period.periodo_da.strftime('%B %Y')}",
                "importo": float(c.importo_pagato or c.importo_totale),
                "data_pagamento": c.data_pagamento.isoformat() if c.data_pagamento else None,
                "stato": c.stato,
            })
        ultimi_pagamenti.sort(key=lambda x: x["data_pagamento"] or "", reverse=True)
        ultimi_pagamenti = ultimi_pagamenti[:10]

        return Response({
            "tenant": TenantProfileSerializer(tenant).data,
            "stanza_corrente": stanza_corrente,
            "da_pagare": da_pagare,
            "ultimi_pagamenti": ultimi_pagamenti,
        })


# ---------------------------------------------------------------------------
# Dashboard proprietario
# ---------------------------------------------------------------------------

class DashboardProprietarioView(APIView):
    """GET /api/v1/dashboard/proprietario/ — Riepilogo KPI per i proprietari."""

    permission_classes = [IsProprietario]

    def get(self, request):
        oggi = datetime.date.today()
        anno = oggi.year
        mese = oggi.month
        soglia_scadenza = oggi + datetime.timedelta(days=7)

        # KPI: incasso anno corrente (RentPayment pagati)
        incasso_anno = (
            RentPayment.objects.filter(
                stato=StatoPagamento.PAGATO,
                data_pagamento__year=anno,
            ).aggregate(tot=Sum("importo_pagato"))["tot"]
            or Decimal("0")
        )

        # KPI: incasso mese corrente
        incasso_mese = (
            RentPayment.objects.filter(
                stato=StatoPagamento.PAGATO,
                data_pagamento__year=anno,
                data_pagamento__month=mese,
            ).aggregate(tot=Sum("importo_pagato"))["tot"]
            or Decimal("0")
        )

        # KPI: spese anno corrente
        from billing.models import Expense
        spese_anno = (
            Expense.objects.filter(data__year=anno).aggregate(tot=Sum("importo"))["tot"]
            or Decimal("0")
        )

        # Pagamenti in ritardo (rent + charge + extra)
        ritardi_rent = list(
            RentPayment.objects.filter(
                stato__in=[StatoPagamento.IN_RITARDO, StatoPagamento.INSOLUTO],
            ).select_related("assignment__tenant", "assignment__room")
        )
        ritardi_charge = list(
            UtilityCharge.objects.filter(
                stato__in=[StatoPagamento.IN_RITARDO, StatoPagamento.INSOLUTO],
            ).select_related("assignment__tenant", "assignment__room", "period")
        )
        ritardi_extra = list(
            ExtraCharge.objects.filter(
                stato__in=[StatoPagamento.IN_RITARDO, StatoPagamento.INSOLUTO],
            ).select_related("assignment__tenant")
        )

        # Pagamenti in scadenza entro 7gg (stati: atteso, dichiarato)
        scadenza_rent = list(
            RentPayment.objects.filter(
                stato__in=[StatoPagamento.ATTESO, StatoPagamento.DICHIARATO],
                scadenza__lte=soglia_scadenza,
                scadenza__gte=oggi,
            ).select_related("assignment__tenant", "assignment__room")
        )
        scadenza_charge = list(
            UtilityCharge.objects.filter(
                stato__in=[StatoPagamento.ATTESO, StatoPagamento.DICHIARATO],
                scadenza__lte=soglia_scadenza,
                scadenza__gte=oggi,
            ).select_related("assignment__tenant", "assignment__room", "period")
        )
        scadenza_extra = list(
            ExtraCharge.objects.filter(
                stato__in=[StatoPagamento.ATTESO, StatoPagamento.DICHIARATO],
                scadenza__lte=soglia_scadenza,
                scadenza__gte=oggi,
            ).select_related("assignment__tenant")
        )

        def _fmt_rent(r):
            giorni = _giorni_ritardo(r.scadenza, oggi)
            return {
                "tipo": "rent",
                "id": r.id,
                "tenant": r.assignment.tenant.nominativo,
                "descrizione": f"Affitto {r.competenza_da.strftime('%B %Y')}",
                "importo": float(r.importo_dovuto),
                "scadenza": r.scadenza.isoformat(),
                "stato": r.stato,
                "giorni_ritardo": giorni,
            }

        def _fmt_charge(c):
            giorni = _giorni_ritardo(c.scadenza, oggi)
            return {
                "tipo": "utility_charge",
                "id": c.id,
                "tenant": c.assignment.tenant.nominativo,
                "descrizione": f"Conguaglio {c.period.periodo_da.strftime('%B %Y')}",
                "importo": float(c.importo_totale),
                "scadenza": c.scadenza.isoformat(),
                "stato": c.stato,
                "giorni_ritardo": giorni,
            }

        def _fmt_extra(e):
            giorni = _giorni_ritardo(e.scadenza, oggi)
            return {
                "tipo": "extra",
                "id": e.id,
                "tenant": e.assignment.tenant.nominativo,
                "descrizione": e.descrizione,
                "importo": float(e.importo),
                "scadenza": e.scadenza.isoformat(),
                "stato": e.stato,
                "giorni_ritardo": giorni,
            }

        ritardi = (
            [_fmt_rent(r) for r in ritardi_rent]
            + [_fmt_charge(c) for c in ritardi_charge]
            + [_fmt_extra(e) for e in ritardi_extra]
        )
        ritardi.sort(key=lambda x: x["scadenza"])

        in_scadenza = (
            [_fmt_rent(r) for r in scadenza_rent]
            + [_fmt_charge(c) for c in scadenza_charge]
            + [_fmt_extra(e) for e in scadenza_extra]
        )
        in_scadenza.sort(key=lambda x: x["scadenza"])

        return Response({
            "kpi": {
                "incasso_anno_corrente": float(incasso_anno),
                "incasso_mese_corrente": float(incasso_mese),
                "spese_anno_corrente": float(spese_anno),
                "ritardi_count": len(ritardi),
                "in_scadenza_count": len(in_scadenza),
            },
            "ritardi": ritardi,
            "in_scadenza": in_scadenza,
        })


# ---------------------------------------------------------------------------
# Quadro annuale
# ---------------------------------------------------------------------------

class QuadroAnnualeView(APIView):
    """
    GET /api/v1/quadro-annuale/<anno>/ — Riproduce il foglio Excel delle utenze.
    Solo proprietari.
    """

    permission_classes = [IsProprietario]

    def get(self, request, anno: int):
        # Periodi dell'anno
        periods = UtilityChargePeriod.objects.filter(
            periodo_da__year=anno
        ).order_by("periodo_da")

        if not periods.exists():
            # Prova anche con periodo_a
            periods = UtilityChargePeriod.objects.filter(
                periodo_a__year=anno
            ).order_by("periodo_da")

        # Tutti i charge per questi periodi
        charges = (
            UtilityCharge.objects.filter(period__in=periods)
            .select_related(
                "assignment__tenant",
                "period",
            )
            .order_by("period__periodo_da", "assignment__tenant__nominativo")
        )

        # Raccoglie i nomi degli inquilini coinvolti (ordinati)
        tenant_names_set = set()
        for c in charges:
            tenant_names_set.add(c.assignment.tenant.nominativo)
        tenant_names = sorted(tenant_names_set)

        # Indicizzazione: {(period_id, tenant_nominativo): charge}
        charge_index = {}
        for c in charges:
            key = (c.period_id, c.assignment.tenant.nominativo)
            charge_index[key] = c

        righe = []
        totale_anno_per_tenant: dict[str, Decimal] = {n: Decimal("0") for n in tenant_names}
        totale_anno = Decimal("0")

        for period in periods:
            # Label periodo
            if period.periodo_da.month == period.periodo_a.month:
                label = period.periodo_da.strftime("%B %Y")
            else:
                label = (
                    f"{period.periodo_da.strftime('%B')} - "
                    f"{period.periodo_a.strftime('%B %Y')}"
                )

            totale_periodo = Decimal("0")
            per_tenant = {}

            for nome in tenant_names:
                charge = charge_index.get((period.id, nome))
                if charge:
                    importo = charge.importo_totale
                    stato = charge.stato
                    # Giorni di presenza: da valid_from e valid_to del periodo
                    giorni = (period.periodo_a - period.periodo_da).days + 1
                else:
                    importo = Decimal("0")
                    stato = None
                    giorni = 0

                per_tenant[nome] = {
                    "giorni": giorni,
                    "importo": float(importo),
                    "stato": stato,
                }
                totale_periodo += importo
                totale_anno_per_tenant[nome] += importo

            totale_anno += totale_periodo

            righe.append({
                "periodo_id": period.id,
                "periodo_label": label,
                "periodo_da": period.periodo_da.isoformat(),
                "periodo_a": period.periodo_a.isoformat(),
                "totale_periodo": float(totale_periodo),
                "per_tenant": per_tenant,
            })

        return Response({
            "anno": anno,
            "tenants": tenant_names,
            "righe": righe,
            "totale_anno_per_tenant": {k: float(v) for k, v in totale_anno_per_tenant.items()},
            "totale_anno": float(totale_anno),
        })
