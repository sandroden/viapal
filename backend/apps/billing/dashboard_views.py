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
from billing.models import ExtraCharge, RentPayment, StatoPagamento, TenantCondominioRate, UtilityCharge, UtilityChargePeriod
from properties.models import Contract, RoomAssignment, TenantProfile
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
    """GET /api/v1/dashboard/proprietario/?anno=YYYY&mese=MM — Riepilogo KPI per i proprietari.

    Senza parametri: anno+mese correnti (vista operativa).
    Con `anno` diverso da quello corrente: vista storica, ritardi/in-scadenza vuoti.
    """

    permission_classes = [IsProprietario]

    def get(self, request):
        oggi = datetime.date.today()

        try:
            anno = int(request.query_params.get("anno", oggi.year))
            mese = int(request.query_params.get("mese", oggi.month))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Parametri 'anno' e 'mese' devono essere interi."},
                status=400,
            )
        if not (1 <= mese <= 12):
            return Response(
                {"detail": "Parametro 'mese' deve essere tra 1 e 12."},
                status=400,
            )

        is_storico = anno != oggi.year
        FINESTRA_SCADENZA_GIORNI = 14
        soglia_scadenza = oggi + datetime.timedelta(days=FINESTRA_SCADENZA_GIORNI)

        # KPI: incasso anno (RentPayment pagati)
        incasso_rent_anno = (
            RentPayment.objects.filter(
                stato=StatoPagamento.PAGATO,
                data_pagamento__year=anno,
            ).aggregate(tot=Sum("importo_pagato"))["tot"]
            or Decimal("0")
        )
        incasso_utility_anno = (
            UtilityCharge.objects.filter(
                stato=StatoPagamento.PAGATO,
                data_pagamento__year=anno,
            ).aggregate(tot=Sum("importo_pagato"))["tot"]
            or Decimal("0")
        )
        incasso_extra_anno = (
            ExtraCharge.objects.filter(
                stato=StatoPagamento.PAGATO,
                data_pagamento__year=anno,
            ).aggregate(tot=Sum("importo_pagato"))["tot"]
            or Decimal("0")
        )
        incasso_anno = incasso_rent_anno + incasso_utility_anno + incasso_extra_anno

        # KPI: incasso mese specifico
        incasso_rent_mese = (
            RentPayment.objects.filter(
                stato=StatoPagamento.PAGATO,
                data_pagamento__year=anno,
                data_pagamento__month=mese,
            ).aggregate(tot=Sum("importo_pagato"))["tot"]
            or Decimal("0")
        )
        incasso_utility_mese = (
            UtilityCharge.objects.filter(
                stato=StatoPagamento.PAGATO,
                data_pagamento__year=anno,
                data_pagamento__month=mese,
            ).aggregate(tot=Sum("importo_pagato"))["tot"]
            or Decimal("0")
        )
        incasso_extra_mese = (
            ExtraCharge.objects.filter(
                stato=StatoPagamento.PAGATO,
                data_pagamento__year=anno,
                data_pagamento__month=mese,
            ).aggregate(tot=Sum("importo_pagato"))["tot"]
            or Decimal("0")
        )
        incasso_mese = incasso_rent_mese + incasso_utility_mese + incasso_extra_mese

        # KPI: spese anno
        from billing.models import Expense
        spese_qs = Expense.objects.filter(data__year=anno).select_related(
            "category", "anticipata_da_owner"
        )
        spese_anno = spese_qs.aggregate(tot=Sum("importo"))["tot"] or Decimal("0")

        # Breakdown spese per categoria e per proprietario anticipante
        spese_per_categoria: dict[str, Decimal] = {}
        spese_per_owner: dict[str, Decimal] = {}
        for sp in spese_qs:
            cat = sp.category.nome if sp.category else "Senza categoria"
            spese_per_categoria[cat] = spese_per_categoria.get(cat, Decimal("0")) + sp.importo
            owner = sp.anticipata_da_owner.nominativo if sp.anticipata_da_owner else "—"
            spese_per_owner[owner] = spese_per_owner.get(owner, Decimal("0")) + sp.importo

        spese_dettaglio = {
            "per_categoria": sorted(
                [{"nome": k, "importo": float(v)} for k, v in spese_per_categoria.items()],
                key=lambda x: -x["importo"],
            ),
            "per_owner": sorted(
                [{"nome": k, "importo": float(v)} for k, v in spese_per_owner.items()],
                key=lambda x: -x["importo"],
            ),
            "totale": float(spese_anno),
        }

        # Breakdown incassi per inquilino (annuale)
        breakdown_per_tenant: dict[str, dict[str, Decimal]] = {}

        def _add(nominativo: str, voce: str, importo: Decimal):
            row = breakdown_per_tenant.setdefault(
                nominativo, {"rent": Decimal("0"), "utility": Decimal("0"), "extra": Decimal("0")}
            )
            row[voce] += importo

        for r in RentPayment.objects.filter(
            stato=StatoPagamento.PAGATO, data_pagamento__year=anno
        ).select_related("assignment__tenant"):
            _add(r.assignment.tenant.nominativo, "rent", r.importo_pagato or Decimal("0"))

        for c in UtilityCharge.objects.filter(
            stato=StatoPagamento.PAGATO, data_pagamento__year=anno
        ).select_related("assignment__tenant"):
            _add(c.assignment.tenant.nominativo, "utility", c.importo_pagato or Decimal("0"))

        for e in ExtraCharge.objects.filter(
            stato=StatoPagamento.PAGATO, data_pagamento__year=anno
        ).select_related("assignment__tenant"):
            _add(e.assignment.tenant.nominativo, "extra", e.importo_pagato or Decimal("0"))

        breakdown_incassi = sorted(
            [
                {
                    "tenant": nominativo,
                    "rent": float(d["rent"]),
                    "utility": float(d["utility"]),
                    "extra": float(d["extra"]),
                    "totale": float(d["rent"] + d["utility"] + d["extra"]),
                }
                for nominativo, d in breakdown_per_tenant.items()
            ],
            key=lambda x: x["tenant"],
        )

        # Per anni storici, ritardi/in-scadenza non hanno senso (sono "ad oggi")
        if is_storico:
            ritardi_rent = ritardi_charge = ritardi_extra = []
            scadenza_rent = scadenza_charge = scadenza_extra = []
        else:
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
            "anno": anno,
            "mese": mese,
            "is_storico": is_storico,
            "kpi": {
                "incasso_anno": float(incasso_anno),
                "incasso_mese": float(incasso_mese),
                "spese_anno": float(spese_anno),
                "ritardi_count": len(ritardi),
                "in_scadenza_count": len(in_scadenza),
            },
            "incasso_anno_dettaglio": {
                "rent": float(incasso_rent_anno),
                "utility": float(incasso_utility_anno),
                "extra": float(incasso_extra_anno),
                "totale": float(incasso_anno),
            },
            "incasso_mese_dettaglio": {
                "rent": float(incasso_rent_mese),
                "utility": float(incasso_utility_mese),
                "extra": float(incasso_extra_mese),
                "totale": float(incasso_mese),
            },
            "spese_anno_dettaglio": spese_dettaglio,
            "breakdown_incassi": breakdown_incassi,
            "ritardi": ritardi,
            "in_scadenza": in_scadenza,
            "finestra_scadenza_giorni": FINESTRA_SCADENZA_GIORNI,
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


# ---------------------------------------------------------------------------
# Situazione per inquilino (drilldown)
# ---------------------------------------------------------------------------

class TenantSituazioneView(APIView):
    """
    GET /api/v1/tenants/<tenant_id>/situazione/?anno=YYYY

    Riepilogo completo per un inquilino: anagrafica, assignment storici,
    affitti, conguagli (con voci dettagliate) e addebiti extra dell'anno.
    Riservato ai proprietari.
    """

    permission_classes = [IsProprietario]

    def get(self, request, tenant_id: int):
        oggi = datetime.date.today()
        try:
            anno = int(request.query_params.get("anno", oggi.year))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Parametro 'anno' deve essere un intero."}, status=400
            )

        try:
            tenant = TenantProfile.objects.select_related("user").get(pk=tenant_id)
        except TenantProfile.DoesNotExist:
            return Response(
                {"detail": "Inquilino non trovato."}, status=404
            )

        assignments_qs = (
            RoomAssignment.objects.filter(tenant=tenant)
            .select_related("room")
            .order_by("-valid_from")
        )
        assignments_payload = [
            {
                "id": a.id,
                "room_id": a.room.id,
                "room_nome": a.room.nome,
                "valid_from": a.valid_from.isoformat(),
                "valid_to": a.valid_to.isoformat() if a.valid_to else None,
                "canone_mensile": float(a.canone_mensile),
                "deposito_versato": float(a.deposito_versato or 0),
                "deposito_restituito": float(a.deposito_restituito or 0)
                if hasattr(a, "deposito_restituito") and a.deposito_restituito
                else None,
                "data_atto_cessione": a.data_atto_cessione.isoformat()
                if getattr(a, "data_atto_cessione", None)
                else None,
            }
            for a in assignments_qs
        ]

        # Affitti dell'anno (per competenza_da)
        rent_qs = (
            RentPayment.objects.filter(
                assignment__tenant=tenant, competenza_da__year=anno
            )
            .select_related("assignment__room")
            .order_by("competenza_da")
        )
        rent_righe = []
        rent_dovuto = Decimal("0")
        rent_pagato = Decimal("0")
        for r in rent_qs:
            giorni = _giorni_ritardo(r.scadenza, oggi)
            rent_righe.append({
                "id": r.id,
                "competenza_da": r.competenza_da.isoformat(),
                "competenza_a": r.competenza_a.isoformat(),
                "importo_dovuto": float(r.importo_dovuto),
                "importo_pagato": float(r.importo_pagato or 0),
                "scadenza": r.scadenza.isoformat(),
                "stato": r.stato,
                "giorni_ritardo": giorni,
                "data_pagamento": r.data_pagamento.isoformat() if r.data_pagamento else None,
                "is_aggiustamento": getattr(r, "is_aggiustamento", False),
            })
            rent_dovuto += r.importo_dovuto
            if r.importo_pagato:
                rent_pagato += r.importo_pagato

        # Conguagli utenze dell'anno (per period.periodo_da)
        utility_qs = (
            UtilityCharge.objects.filter(
                assignment__tenant=tenant, period__periodo_da__year=anno
            )
            .select_related("period")
            .prefetch_related("lines")
            .order_by("period__periodo_da")
        )
        utility_righe = []
        utility_dovuto = Decimal("0")
        utility_pagato = Decimal("0")
        for c in utility_qs:
            lines = [
                {"voce": ln.voce, "importo": float(ln.importo)}
                for ln in c.lines.all()
            ]
            utility_righe.append({
                "id": c.id,
                "period_id": c.period_id,
                "period_da": c.period.periodo_da.isoformat(),
                "period_a": c.period.periodo_a.isoformat(),
                "importo_totale": float(c.importo_totale),
                "importo_pagato": float(c.importo_pagato or 0),
                "scadenza": c.scadenza.isoformat() if c.scadenza else None,
                "stato": c.stato,
                "data_pagamento": c.data_pagamento.isoformat() if c.data_pagamento else None,
                "lines": lines,
            })
            utility_dovuto += c.importo_totale
            if c.importo_pagato:
                utility_pagato += c.importo_pagato

        # Addebiti extra dell'anno
        extra_qs = (
            ExtraCharge.objects.filter(assignment__tenant=tenant, data__year=anno)
            .order_by("data")
        )
        extra_righe = []
        extra_totale = Decimal("0")
        for e in extra_qs:
            extra_righe.append({
                "id": e.id,
                "data": e.data.isoformat(),
                "descrizione": e.descrizione,
                "importo": float(e.importo),
                "scadenza": e.scadenza.isoformat() if e.scadenza else None,
                "stato": e.stato,
            })
            extra_totale += e.importo

        # Ritardo medio (giorni positivi su rent pagati nell'anno)
        ritardi_giorni = []
        for r in rent_qs:
            if r.data_pagamento and r.scadenza:
                d = (r.data_pagamento - r.scadenza).days
                if d > 0:
                    ritardi_giorni.append(d)
        ritardo_medio = (
            float(sum(ritardi_giorni) / len(ritardi_giorni))
            if ritardi_giorni
            else 0.0
        )

        totale_dovuto = rent_dovuto + utility_dovuto + extra_totale
        totale_pagato = rent_pagato + utility_pagato

        # Quota condominio: dal contratto attivo (in vigore alla data oggi)
        contract_attivo = (
            Contract.objects.filter(data_decorrenza__lte=oggi)
            .order_by("-data_decorrenza")
            .first()
        )
        quota_condominio = {
            "corrente": None,
            "storico": [],
        }
        if contract_attivo:
            quote_qs = (
                TenantCondominioRate.objects
                .filter(contract=contract_attivo)
                .order_by("-valid_from")
            )
            quote_storico = []
            for q in quote_qs:
                row = {
                    "valid_from": q.valid_from.isoformat(),
                    "valid_to": q.valid_to.isoformat() if q.valid_to else None,
                    "importo_mensile": float(q.importo_mensile),
                    "note": q.note,
                }
                quote_storico.append(row)
                attiva = q.valid_from <= oggi and (q.valid_to is None or q.valid_to >= oggi)
                if attiva and not quota_condominio["corrente"]:
                    quota_condominio["corrente"] = row
            quota_condominio["storico"] = quote_storico

        return Response({
            "tenant": TenantProfileSerializer(tenant).data,
            "anno": anno,
            "assignments": assignments_payload,
            "quota_condominio": quota_condominio,
            "rent": {
                "dovuto_anno": float(rent_dovuto),
                "pagato_anno": float(rent_pagato),
                "saldo": float(rent_pagato - rent_dovuto),
                "righe": rent_righe,
            },
            "utility": {
                "dovuto_anno": float(utility_dovuto),
                "pagato_anno": float(utility_pagato),
                "saldo": float(utility_pagato - utility_dovuto),
                "righe": utility_righe,
            },
            "extra": {
                "totale_anno": float(extra_totale),
                "righe": extra_righe,
            },
            "totali_anno": {
                "dovuto": float(totale_dovuto),
                "pagato": float(totale_pagato),
                "saldo": float(totale_pagato - totale_dovuto),
            },
            "ritardo_medio_giorni": ritardo_medio,
        })
