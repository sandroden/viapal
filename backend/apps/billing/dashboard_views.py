"""
Endpoint custom per le dashboard inquilino, proprietario e quadro annuale.
"""
import datetime
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from rest_framework.permissions import IsAuthenticated  # noqa: F401
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsInquilino, IsProprietario
from billing._dates import format_mese, format_mese_anno
from billing.models import (
    BankTransactionAllocation,
    Receivable,
    StatoPagamento,
    TenantCondominioRate,
    UtilityChargePeriod,
)
from properties.models import Contract, OwnerProfile, RoomAssignment, TenantProfile
from properties.serializers import TenantProfileSerializer  # noqa: F401


# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

STATI_DA_PAGARE = {
    StatoPagamento.ATTESO,
    StatoPagamento.IN_RITARDO,
    StatoPagamento.INSOLUTO,
    StatoPagamento.DICHIARATO,
}

# Mapping causale Receivable -> "tipo" esposto nell'API (compatibilità FE)
TIPO_PER_CAUSALE = {
    Receivable.Causale.AFFITTO: "rent",
    Receivable.Causale.UTENZE: "utility_charge",
    Receivable.Causale.EXTRA: "extra",
}

# Causali "di gestione" mostrate nelle dashboard rendita/pagamenti.
# DEPOSITO è escluso: i depositi cauzionali non sono entrate operative.
CAUSALI_OPERATIVE = (
    Receivable.Causale.AFFITTO,
    Receivable.Causale.UTENZE,
    Receivable.Causale.EXTRA,
)


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


def _descrizione_receivable(r: Receivable) -> str:
    if r.causale == Receivable.Causale.AFFITTO:
        return f"Affitto {format_mese_anno(r.competenza_da)}"
    if r.causale == Receivable.Causale.UTENZE:
        base = r.utility_period.periodo_da if r.utility_period else r.competenza_da
        return f"Utenze {format_mese_anno(base)}"
    return r.descrizione or "Addebito extra"


def _build_item_da_pagare(r: Receivable, oggi: datetime.date) -> dict:
    giorni = _giorni_ritardo(r.scadenza, oggi)
    return {
        "tipo": TIPO_PER_CAUSALE[r.causale],
        "id": r.id,
        "descrizione": _descrizione_receivable(r),
        "importo": float(r.importo_dovuto),
        "scadenza": r.scadenza.isoformat(),
        "stato": r.stato,
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

        try:
            tenant = TenantProfile.objects.select_related("user").get(user=user)
        except TenantProfile.DoesNotExist:
            return Response(
                {"detail": "Profilo inquilino non trovato."},
                status=404,
            )

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

        assignments = RoomAssignment.objects.filter(tenant=tenant)

        da_pagare_qs = (
            Receivable.objects.filter(
                assignment__in=assignments,
                stato__in=STATI_DA_PAGARE,
                causale__in=CAUSALI_OPERATIVE,
            )
            .select_related("assignment__room", "utility_period")
            .order_by("scadenza")
        )

        da_pagare = [_build_item_da_pagare(r, oggi) for r in da_pagare_qs]

        ultimi_pagati_qs = (
            Receivable.objects.filter(
                assignment__in=assignments,
                stato=StatoPagamento.PAGATO,
                causale__in=[Receivable.Causale.AFFITTO, Receivable.Causale.UTENZE],
            )
            .select_related("assignment__room", "utility_period")
            .order_by("-data_pagamento")[:10]
        )
        ultimi_pagamenti = []
        for r in ultimi_pagati_qs:
            ultimi_pagamenti.append({
                "tipo": TIPO_PER_CAUSALE[r.causale],
                "id": r.id,
                "descrizione": _descrizione_receivable(r),
                "importo": float(r.importo_pagato or r.importo_dovuto),
                "data_pagamento": r.data_pagamento.isoformat() if r.data_pagamento else None,
                "stato": r.stato,
            })
        ultimi_pagamenti.sort(key=lambda x: x["data_pagamento"] or "", reverse=True)

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

        def _incasso_per_causale(causale: str, anno_: int, mese_: int | None = None) -> Decimal:
            qs = Receivable.objects.filter(
                causale=causale,
                stato=StatoPagamento.PAGATO,
                data_pagamento__year=anno_,
            )
            if mese_ is not None:
                qs = qs.filter(data_pagamento__month=mese_)
            return qs.aggregate(tot=Sum("importo_pagato"))["tot"] or Decimal("0")

        incasso_rent_anno = _incasso_per_causale(Receivable.Causale.AFFITTO, anno)
        incasso_utility_anno = _incasso_per_causale(Receivable.Causale.UTENZE, anno)
        incasso_extra_anno = _incasso_per_causale(Receivable.Causale.EXTRA, anno)
        incasso_anno = incasso_rent_anno + incasso_utility_anno + incasso_extra_anno

        incasso_rent_mese = _incasso_per_causale(Receivable.Causale.AFFITTO, anno, mese)
        incasso_utility_mese = _incasso_per_causale(Receivable.Causale.UTENZE, anno, mese)
        incasso_extra_mese = _incasso_per_causale(Receivable.Causale.EXTRA, anno, mese)
        incasso_mese = incasso_rent_mese + incasso_utility_mese + incasso_extra_mese

        # KPI: spese anno
        from billing.models import Expense
        spese_qs = Expense.objects.filter(data__year=anno).select_related(
            "category", "anticipata_da_owner"
        )
        spese_anno = spese_qs.aggregate(tot=Sum("importo"))["tot"] or Decimal("0")

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

        # Bilancio per proprietario (entrate - uscite) — anno selezionato.
        bilancio_per_owner: dict[int, dict] = {}
        for o in OwnerProfile.objects.all():
            bilancio_per_owner[o.id] = {
                "owner_id": o.id,
                "nominativo": o.nominativo,
                "entrate_rent": Decimal("0"),
                "entrate_utility": Decimal("0"),
                "entrate_extra": Decimal("0"),
                "uscite": Decimal("0"),
                "uscite_dettaglio": {},
            }

        VOCE_KEY_PER_CAUSALE = {
            Receivable.Causale.AFFITTO: "entrate_rent",
            Receivable.Causale.UTENZE: "entrate_utility",
            Receivable.Causale.EXTRA: "entrate_extra",
        }
        for r in Receivable.objects.filter(
            stato=StatoPagamento.PAGATO,
            data_pagamento__year=anno,
            incassato_da_owner__isnull=False,
            causale__in=CAUSALI_OPERATIVE,
        ):
            if r.incassato_da_owner_id in bilancio_per_owner:
                voce_key = VOCE_KEY_PER_CAUSALE[r.causale]
                bilancio_per_owner[r.incassato_da_owner_id][voce_key] += (
                    r.importo_pagato or Decimal("0")
                )

        for sp in spese_qs:
            if sp.anticipata_da_owner_id and sp.anticipata_da_owner_id in bilancio_per_owner:
                bilancio_per_owner[sp.anticipata_da_owner_id]["uscite"] += sp.importo
                cat_nome = sp.category.nome if sp.category else "Altro"
                d = bilancio_per_owner[sp.anticipata_da_owner_id]["uscite_dettaglio"]
                d[cat_nome] = d.get(cat_nome, Decimal("0")) + sp.importo

        bilancio_proprietari = []
        for o_data in bilancio_per_owner.values():
            entrate_tot = (
                o_data["entrate_rent"] + o_data["entrate_utility"] + o_data["entrate_extra"]
            )
            saldo = entrate_tot - o_data["uscite"]
            bilancio_proprietari.append({
                "owner_id": o_data["owner_id"],
                "nominativo": o_data["nominativo"],
                "entrate_rent": float(o_data["entrate_rent"]),
                "entrate_utility": float(o_data["entrate_utility"]),
                "entrate_extra": float(o_data["entrate_extra"]),
                "entrate_totali": float(entrate_tot),
                "uscite": float(o_data["uscite"]),
                "uscite_dettaglio": {
                    k: float(v) for k, v in o_data["uscite_dettaglio"].items()
                },
                "saldo": float(saldo),
            })
        bilancio_proprietari.sort(key=lambda x: x["nominativo"])

        # Breakdown incassi per inquilino (annuale)
        breakdown_per_tenant: dict[str, dict[str, Decimal]] = {}

        VOCE_BREAKDOWN_PER_CAUSALE = {
            Receivable.Causale.AFFITTO: "rent",
            Receivable.Causale.UTENZE: "utility",
            Receivable.Causale.EXTRA: "extra",
        }
        for r in Receivable.objects.filter(
            stato=StatoPagamento.PAGATO,
            data_pagamento__year=anno,
            causale__in=CAUSALI_OPERATIVE,
        ).select_related("assignment__tenant"):
            row = breakdown_per_tenant.setdefault(
                r.assignment.tenant.nominativo,
                {"rent": Decimal("0"), "utility": Decimal("0"), "extra": Decimal("0")},
            )
            row[VOCE_BREAKDOWN_PER_CAUSALE[r.causale]] += r.importo_pagato or Decimal("0")

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

        # Ritardi e in-scadenza (vista operativa, no storico)
        if is_storico:
            ritardi_qs = scadenza_qs = Receivable.objects.none()
        else:
            ritardi_qs = (
                Receivable.objects.filter(
                    stato__in=[StatoPagamento.IN_RITARDO, StatoPagamento.INSOLUTO],
                    causale__in=CAUSALI_OPERATIVE,
                )
                .select_related(
                    "assignment__tenant", "assignment__room", "utility_period"
                )
            )
            scadenza_qs = (
                Receivable.objects.filter(
                    stato__in=[StatoPagamento.ATTESO, StatoPagamento.DICHIARATO],
                    scadenza__lte=soglia_scadenza,
                    scadenza__gte=oggi,
                    causale__in=CAUSALI_OPERATIVE,
                )
                .select_related(
                    "assignment__tenant", "assignment__room", "utility_period"
                )
            )

        def _fmt(r: Receivable) -> dict:
            giorni = _giorni_ritardo(r.scadenza, oggi)
            return {
                "tipo": TIPO_PER_CAUSALE[r.causale],
                "id": r.id,
                "tenant": r.assignment.tenant.nominativo,
                "descrizione": _descrizione_receivable(r),
                "importo": float(r.importo_dovuto),
                "scadenza": r.scadenza.isoformat(),
                "stato": r.stato,
                "giorni_ritardo": giorni,
            }

        ritardi = sorted([_fmt(r) for r in ritardi_qs], key=lambda x: x["scadenza"])
        in_scadenza = sorted([_fmt(r) for r in scadenza_qs], key=lambda x: x["scadenza"])

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
            "bilancio_proprietari": bilancio_proprietari,
            "breakdown_incassi": breakdown_incassi,
            "ritardi": ritardi,
            "in_scadenza": in_scadenza,
            "finestra_scadenza_giorni": FINESTRA_SCADENZA_GIORNI,
        })


# ---------------------------------------------------------------------------
# Dettaglio bilancio per proprietario (voci singole entrate/uscite)
# ---------------------------------------------------------------------------

class BilancioOwnerDettaglioView(APIView):
    """GET /api/v1/dashboard/proprietario/<owner_id>/dettaglio-bilancio/?anno=YYYY&tipo=entrate|uscite

    Restituisce le righe singole (non aggregate) che compongono entrate o
    uscite di un proprietario per un dato anno. Stessa logica di filtro usata
    in `DashboardProprietarioView` per gli aggregati: la somma delle righe
    deve quindi quadrare con la cella della dashboard.
    """

    permission_classes = [IsProprietario]

    CAUSALE_LABEL = {
        Receivable.Causale.AFFITTO: "Affitto",
        Receivable.Causale.UTENZE: "Utenze",
        Receivable.Causale.EXTRA: "Addebito extra",
    }

    def get(self, request, owner_id: int):
        try:
            anno = int(request.query_params.get("anno"))
        except (TypeError, ValueError):
            return Response({"detail": "Parametro 'anno' obbligatorio (intero)."}, status=400)

        tipo = request.query_params.get("tipo")
        if tipo not in ("entrate", "uscite"):
            return Response(
                {"detail": "Parametro 'tipo' deve essere 'entrate' o 'uscite'."},
                status=400,
            )

        try:
            owner = OwnerProfile.objects.get(pk=owner_id)
        except OwnerProfile.DoesNotExist:
            return Response({"detail": "Proprietario non trovato."}, status=404)

        if tipo == "entrate":
            righe_qs = (
                Receivable.objects.filter(
                    stato=StatoPagamento.PAGATO,
                    data_pagamento__year=anno,
                    incassato_da_owner_id=owner_id,
                    causale__in=CAUSALI_OPERATIVE,
                )
                .select_related("assignment__tenant", "utility_period")
                .order_by("-data_pagamento", "-id")
            )
            righe = [
                {
                    "id": r.id,
                    "tipo": TIPO_PER_CAUSALE[r.causale],
                    "causale": r.causale,
                    "causale_label": self.CAUSALE_LABEL[r.causale],
                    "tenant": r.assignment.tenant.nominativo,
                    "descrizione": _descrizione_receivable(r),
                    "importo_dovuto": float(r.importo_dovuto),
                    "importo_pagato": float(r.importo_pagato or 0),
                    "scadenza": r.scadenza.isoformat() if r.scadenza else None,
                    "data_pagamento": (
                        r.data_pagamento.isoformat() if r.data_pagamento else None
                    ),
                    "stato": r.stato,
                }
                for r in righe_qs
            ]
            totale = sum((r["importo_pagato"] for r in righe), 0.0)
        else:
            from billing.models import Expense
            spese_qs = (
                Expense.objects.filter(data__year=anno, anticipata_da_owner_id=owner_id)
                .select_related("category", "supplier", "utility_bill")
                .order_by("-data", "-id")
            )
            righe = []
            for sp in spese_qs:
                bolletta = getattr(sp, "utility_bill", None)
                file_pdf_url = None
                if bolletta and bolletta.file_pdf:
                    # URL relativo (/media/...) → il frontend lo carica nella
                    # sua origine via proxy, stesso-origin per l'iframe.
                    file_pdf_url = bolletta.file_pdf.url
                righe.append({
                    "id": sp.id,
                    "data": sp.data.isoformat(),
                    "categoria": sp.category.nome if sp.category else "—",
                    "supplier": sp.supplier.nome if sp.supplier else None,
                    "descrizione": sp.descrizione,
                    "importo": float(sp.importo),
                    "bolletta_id": bolletta.id if bolletta else None,
                    "bolletta_numero": bolletta.numero_fattura if bolletta else None,
                    "bolletta_prodotto": bolletta.prodotto if bolletta else None,
                    "file_pdf": file_pdf_url,
                })
            totale = sum((r["importo"] for r in righe), 0.0)

        return Response({
            "owner_id": owner.id,
            "owner_nominativo": owner.nominativo,
            "anno": anno,
            "tipo": tipo,
            "totale": totale,
            "righe": righe,
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
        periods = UtilityChargePeriod.objects.filter(
            periodo_da__year=anno
        ).order_by("periodo_da")

        if not periods.exists():
            periods = UtilityChargePeriod.objects.filter(
                periodo_a__year=anno
            ).order_by("periodo_da")

        receivables = (
            Receivable.objects.filter(
                causale=Receivable.Causale.UTENZE,
                utility_period__in=periods,
            )
            .select_related("assignment__tenant", "utility_period")
            .order_by("utility_period__periodo_da", "assignment__tenant__nominativo")
        )

        tenant_names_set = set()
        for r in receivables:
            tenant_names_set.add(r.assignment.tenant.nominativo)
        tenant_names = sorted(tenant_names_set)

        receivable_index = {}
        for r in receivables:
            key = (r.utility_period_id, r.assignment.tenant.nominativo)
            receivable_index[key] = r

        righe = []
        totale_anno_per_tenant: dict[str, Decimal] = {n: Decimal("0") for n in tenant_names}
        totale_anno = Decimal("0")

        for period in periods:
            if period.periodo_da.month == period.periodo_a.month:
                label = format_mese_anno(period.periodo_da)
            else:
                label = (
                    f"{format_mese(period.periodo_da)} - "
                    f"{format_mese_anno(period.periodo_a)}"
                )

            totale_periodo = Decimal("0")
            per_tenant = {}

            for nome in tenant_names:
                r = receivable_index.get((period.id, nome))
                if r:
                    importo = r.importo_dovuto
                    stato = r.stato
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
    affitti, utenze (con voci dettagliate) e addebiti extra dell'anno.
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
                "data_atto_cessione": a.data_atto_cessione.isoformat()
                if getattr(a, "data_atto_cessione", None)
                else None,
            }
            for a in assignments_qs
        ]

        # Affitti dell'anno (per competenza_da)
        rent_qs = (
            Receivable.objects.filter(
                assignment__tenant=tenant,
                causale=Receivable.Causale.AFFITTO,
                competenza_da__year=anno,
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
                "competenza_a": r.competenza_a.isoformat() if r.competenza_a else None,
                "importo_dovuto": float(r.importo_dovuto),
                "importo_pagato": float(r.importo_pagato or 0),
                "scadenza": r.scadenza.isoformat(),
                "stato": r.stato,
                "giorni_ritardo": giorni,
                "data_pagamento": r.data_pagamento.isoformat() if r.data_pagamento else None,
                "is_aggiustamento": r.is_aggiustamento,
                "bank_account_destinazione_id": r.bank_account_destinazione_id,
            })
            rent_dovuto += r.importo_dovuto
            if r.importo_pagato:
                rent_pagato += r.importo_pagato

        # Utenze dell'anno (per utility_period.periodo_da)
        utility_qs = (
            Receivable.objects.filter(
                assignment__tenant=tenant,
                causale=Receivable.Causale.UTENZE,
                utility_period__periodo_da__year=anno,
            )
            .select_related("utility_period")
            .order_by("utility_period__periodo_da")
        )
        utility_righe = []
        utility_dovuto = Decimal("0")
        utility_pagato = Decimal("0")
        for r in utility_qs:
            # Breakdown per voce: ripartizione proporzionale dei totali del periodo
            # sulla quota dell'inquilino (giorni_presenza / giorni_totali).
            lines = []
            p = r.utility_period
            if p and r.giorni_presenza and p.giorni_totali:
                frazione = Decimal(r.giorni_presenza) / Decimal(p.giorni_totali)
                for voce, tot in (
                    ("luce", p.tot_luce), ("gas", p.tot_gas),
                    ("tari", p.tot_tari), ("altro", p.tot_altro),
                ):
                    if tot and tot > 0:
                        lines.append({
                            "voce": voce,
                            "importo": float((tot * frazione).quantize(Decimal("0.01"))),
                        })
            period = r.utility_period
            utility_righe.append({
                "id": r.id,
                "period_id": period.id if period else None,
                "period_da": period.periodo_da.isoformat() if period else r.competenza_da.isoformat(),
                "period_a": period.periodo_a.isoformat() if period else (
                    r.competenza_a.isoformat() if r.competenza_a else None
                ),
                "importo_totale": float(r.importo_dovuto),
                "importo_pagato": float(r.importo_pagato or 0),
                "scadenza": r.scadenza.isoformat() if r.scadenza else None,
                "stato": r.stato,
                "data_pagamento": r.data_pagamento.isoformat() if r.data_pagamento else None,
                "lines": lines,
                "bank_account_destinazione_id": r.bank_account_destinazione_id,
            })
            utility_dovuto += r.importo_dovuto
            if r.importo_pagato:
                utility_pagato += r.importo_pagato

        # Addebiti extra dell'anno (filtra su competenza_da come data dell'addebito)
        extra_qs = (
            Receivable.objects.filter(
                assignment__tenant=tenant,
                causale=Receivable.Causale.EXTRA,
                competenza_da__year=anno,
            )
            .order_by("competenza_da")
        )
        extra_righe = []
        extra_totale = Decimal("0")
        extra_pagato = Decimal("0")
        for r in extra_qs:
            extra_righe.append({
                "id": r.id,
                "data": r.competenza_da.isoformat(),
                "descrizione": r.descrizione,
                "importo": float(r.importo_dovuto),
                "importo_pagato": float(r.importo_pagato or 0),
                "scadenza": r.scadenza.isoformat() if r.scadenza else None,
                "stato": r.stato,
                "data_pagamento": r.data_pagamento.isoformat() if r.data_pagamento else None,
                "bank_account_destinazione_id": r.bank_account_destinazione_id,
            })
            extra_totale += r.importo_dovuto
            if r.importo_pagato:
                extra_pagato += r.importo_pagato

        # Deposito dell'anno: esposto solo dopo la chiusura (data di restituzione
        # valorizzata). Senza, il versamento incassato in passato apparirebbe come
        # credito permanente dell'inquilino.
        deposito_righe: list[dict] = []
        deposito_dovuto = Decimal("0")
        deposito_pagato = Decimal("0")
        deposito_qs_list: list[Receivable] = []
        if tenant.data_restituzione_prevista:
            deposito_qs = (
                Receivable.objects.filter(
                    assignment__tenant=tenant,
                    causale=Receivable.Causale.DEPOSITO,
                    competenza_da__year=anno,
                )
                .order_by("competenza_da")
            )
            deposito_qs_list = list(deposito_qs)
            for r in deposito_qs_list:
                deposito_righe.append({
                    "id": r.id,
                    "data": r.competenza_da.isoformat(),
                    "descrizione": r.descrizione or r.get_causale_display(),
                    "importo": float(r.importo_dovuto),
                    "importo_pagato": float(r.importo_pagato or 0),
                    "scadenza": r.scadenza.isoformat() if r.scadenza else None,
                    "stato": r.stato,
                    "data_pagamento": r.data_pagamento.isoformat() if r.data_pagamento else None,
                    "bank_account_destinazione_id": r.bank_account_destinazione_id,
                })
                deposito_dovuto += r.importo_dovuto
                if r.importo_pagato:
                    deposito_pagato += r.importo_pagato

        # Ritardo medio: tutti i Receivable dell'anno con scadenza valida.
        # Pagati: ritardo storico (data_pagamento - scadenza).
        # Non pagati: ritardo in essere (oggi - scadenza).
        ritardi_giorni = []
        for r in list(rent_qs) + list(utility_qs) + list(extra_qs):
            if not r.scadenza:
                continue
            riferimento = r.data_pagamento or oggi
            d = (riferimento - r.scadenza).days
            if d > 0:
                ritardi_giorni.append(d)
        ritardo_medio = (
            float(sum(ritardi_giorni) / len(ritardi_giorni))
            if ritardi_giorni
            else 0.0
        )

        totale_dovuto = rent_dovuto + utility_dovuto + extra_totale + deposito_dovuto
        totale_pagato = rent_pagato + utility_pagato + extra_pagato + deposito_pagato

        # Saldi "globali" allineati alla colonna Saldo della lista inquilini:
        # somma su tutti i Receivable !DEPOSITO, filtrati per competenza_da__year
        # (anno selezionato) o senza filtro (cumulativo).
        receivable_base = (
            Receivable.objects.filter(assignment__tenant=tenant)
            .exclude(causale=Receivable.Causale.DEPOSITO)
        )
        agg_anno = receivable_base.filter(competenza_da__year=anno).aggregate(
            dovuto=Coalesce(Sum("importo_dovuto"), Decimal("0")),
            pagato=Coalesce(Sum("importo_pagato"), Decimal("0")),
        )
        agg_totale = receivable_base.aggregate(
            dovuto=Coalesce(Sum("importo_dovuto"), Decimal("0")),
            pagato=Coalesce(Sum("importo_pagato"), Decimal("0")),
        )
        saldo_anno_globale = float(agg_anno["pagato"] - agg_anno["dovuto"])
        saldo_totale_globale = float(agg_totale["pagato"] - agg_totale["dovuto"])

        # Quota condominio: dal contratto attivo
        contract_attivo = (
            Contract.objects.filter(data_decorrenza__lte=oggi)
            .select_related("default_pagatore_bollette")
            .order_by("-data_decorrenza")
            .first()
        )
        quota_condominio = {
            "corrente": None,
            "storico": [],
        }
        contract_payload = None
        if contract_attivo:
            contract_payload = {
                "id": contract_attivo.id,
                "data_decorrenza": contract_attivo.data_decorrenza.isoformat(),
                "default_pagatore_bollette": (
                    contract_attivo.default_pagatore_bollette.nominativo
                    if contract_attivo.default_pagatore_bollette
                    else None
                ),
            }
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
            "contract": contract_payload,
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
                "pagato_anno": float(extra_pagato),
                "saldo": float(extra_pagato - extra_totale),
                "righe": extra_righe,
            },
            "deposito": {
                "dovuto_anno": float(deposito_dovuto),
                "pagato_anno": float(deposito_pagato),
                "saldo": float(deposito_pagato - deposito_dovuto),
                "righe": deposito_righe,
            },
            "totali_anno": {
                "dovuto": float(totale_dovuto),
                "pagato": float(totale_pagato),
                "saldo": float(totale_pagato - totale_dovuto),
            },
            "saldi": {
                "anno": saldo_anno_globale,
                "totale": saldo_totale_globale,
            },
            "ritardo_medio_giorni": ritardo_medio,
        })


# ---------------------------------------------------------------------------
# Rendiconto deposito (storico completo da consegnare all'uscita)
# ---------------------------------------------------------------------------

def _nota_riga(dovuto: Decimal, pagato: Decimal) -> str:
    """Codice nota automatica per una riga del rendiconto."""
    if dovuto <= 0:
        return "ok"
    if pagato <= 0:
        return "non_pagata"
    if pagato < dovuto:
        return "parziale"
    if pagato > dovuto:
        return "eccesso"
    return "ok"


def _descr_rendiconto(r: Receivable):
    """(descrizione, data) coerenti per riga di rendiconto e imputazione."""
    p = r.utility_period
    if r.causale == Receivable.Causale.UTENZE and p:
        return (
            f"Utenze {p.periodo_da.isoformat()} → {p.periodo_a.isoformat()}",
            p.periodo_da,
        )
    if r.causale == Receivable.Causale.AFFITTO:
        return (
            r.descrizione or f"Affitto {format_mese_anno(r.competenza_da)}",
            r.competenza_da,
        )
    return (r.descrizione or r.get_causale_display(), r.competenza_da)


class RendicontoView(APIView):
    """
    GET /api/v1/tenants/<tenant_id>/rendiconto/

    Storico completo (tutti gli anni) dei Receivable non-DEPOSITO
    dell'inquilino, raggruppati per causale, con differenze per riga,
    imputazioni dei bonifici (ledger), parziali per anno e chiusura del
    deposito. Pensato per essere consegnato alla restituzione.
    Riservato ai proprietari.
    """

    permission_classes = [IsProprietario]

    _SEZIONI = (
        (Receivable.Causale.AFFITTO, "Affitti"),
        (Receivable.Causale.UTENZE, "Utenze"),
        (Receivable.Causale.EXTRA, "Addebiti extra"),
        (Receivable.Causale.REGISTRAZIONE, "Registrazione contratto"),
    )

    def get(self, request, tenant_id: int):
        oggi = datetime.date.today()
        try:
            tenant = TenantProfile.objects.select_related("user").get(pk=tenant_id)
        except TenantProfile.DoesNotExist:
            return Response({"detail": "Inquilino non trovato."}, status=404)

        assignments = list(
            RoomAssignment.objects.filter(tenant=tenant).order_by("valid_from")
        )
        periodo_da = assignments[0].valid_from.isoformat() if assignments else None
        if assignments and all(a.valid_to for a in assignments):
            periodo_a = max(a.valid_to for a in assignments).isoformat()
        else:
            periodo_a = None  # rapporto ancora in corso

        # Tutte le allocazioni bonifico→addebito dell'inquilino, in un'unica
        # query. Servono sia per le note di copertura sulle righe sia per il
        # ledger "Versamenti e imputazioni".
        allocs = list(
            BankTransactionAllocation.objects.filter(
                receivable__assignment__tenant=tenant
            )
            .exclude(receivable__causale=Receivable.Causale.DEPOSITO)
            .select_related(
                "bank_transaction",
                "receivable",
                "receivable__utility_period",
            )
            .order_by("bank_transaction__data", "bank_transaction_id", "id")
        )
        alloc_per_receivable: dict[int, list] = {}
        for a in allocs:
            alloc_per_receivable.setdefault(a.receivable_id, []).append(a)

        # parziali per anno (senza deposito): anno della "data" della riga
        parziali: dict[int, list[Decimal]] = {}

        sezioni = []
        tot_dovuto = Decimal("0")
        tot_pagato = Decimal("0")
        for causale, label in self._SEZIONI:
            qs = (
                Receivable.objects.filter(
                    assignment__tenant=tenant, causale=causale
                )
                .select_related("utility_period")
                .order_by("competenza_da", "id")
            )
            righe = []
            # meta[i] = (mese 'YYYY-MM', dovuto, {bt_id: bt_importo}) per la
            # diff mensile degli affitti (gestisce 2 righe nello stesso mese
            # per cambio stanza a metà mese).
            meta: list[tuple] = []
            sez_dovuto = Decimal("0")
            sez_pagato = Decimal("0")
            for r in qs:
                dovuto = r.importo_dovuto
                pagato = r.importo_pagato or Decimal("0")
                descr, data = _descr_rendiconto(r)
                righe_alloc = alloc_per_receivable.get(r.id, [])
                allocazioni = [
                    {
                        "data": a.bank_transaction.data.isoformat(),
                        "bonifico_totale": float(a.bank_transaction.importo),
                        "quota": float(a.importo),
                        # bonifico "split": ha coperto più del solo importo
                        # imputato a questa riga (eccedenza andata altrove).
                        "split": a.bank_transaction.importo != a.importo,
                    }
                    for a in righe_alloc
                ]
                mese = f"{data.year:04d}-{data.month:02d}" if data else None
                righe.append({
                    "data": data.isoformat() if data else None,
                    "mese": mese,
                    "scadenza": r.scadenza.isoformat() if r.scadenza else None,
                    "descrizione": descr,
                    "dovuto": float(dovuto),
                    "pagato": float(pagato),
                    "diff": float(pagato - dovuto),
                    # Valorizzata solo per gli affitti, solo sull'ultima riga
                    "diff_mese": None,
                    "nota": _nota_riga(dovuto, pagato),
                    "stato": r.stato,
                    "data_pagamento": r.data_pagamento.isoformat()
                    if r.data_pagamento else None,
                    "allocazioni": allocazioni,
                })
                meta.append((
                    mese,
                    dovuto,
                    {
                        a.bank_transaction_id: a.bank_transaction.importo
                        for a in righe_alloc
                    },
                ))
                sez_dovuto += dovuto
                sez_pagato += pagato
                if data:
                    acc = parziali.setdefault(
                        data.year, [Decimal("0"), Decimal("0")]
                    )
                    acc[0] += dovuto
                    acc[1] += pagato
            if not righe:
                continue
            if causale == Receivable.Causale.AFFITTO:
                # Diff per mese di competenza: somma dei bonifici (distinti)
                # che hanno pagato l'affitto del mese, meno l'affitto dovuto
                # del mese. L'eventuale eccedenza è il sovra-versato che è
                # andato a coprire le utenze. Mostrata sull'ultima riga del
                # mese; le altre righe del mese restano senza diff.
                ultimo_idx_per_mese: dict[str, int] = {}
                dovuto_per_mese: dict[str, Decimal] = {}
                bt_per_mese: dict[str, dict] = {}
                for idx, (mese, dovuto, bts) in enumerate(meta):
                    if mese is None:
                        continue
                    ultimo_idx_per_mese[mese] = idx
                    dovuto_per_mese.setdefault(mese, Decimal("0"))
                    dovuto_per_mese[mese] += dovuto
                    bt_per_mese.setdefault(mese, {}).update(bts)
                for mese, idx in ultimo_idx_per_mese.items():
                    versato_lordo = sum(
                        bt_per_mese[mese].values(), Decimal("0")
                    )
                    righe[idx]["diff_mese"] = float(
                        versato_lordo - dovuto_per_mese[mese]
                    )
            sezioni.append({
                "causale": causale,
                "label": label,
                "righe": righe,
                "dovuto": float(sez_dovuto),
                "pagato": float(sez_pagato),
                "saldo": float(sez_pagato - sez_dovuto),
            })
            tot_dovuto += sez_dovuto
            tot_pagato += sez_pagato

        saldo = tot_pagato - tot_dovuto

        parziali_anno = [
            {
                "anno": anno,
                "dovuto": float(d),
                "pagato": float(p),
                "saldo": float(p - d),
            }
            for anno, (d, p) in sorted(parziali.items())
        ]

        # --- Ledger: versamenti (bonifici) e loro imputazioni ---
        versamenti_map: dict[int, dict] = {}
        for a in allocs:
            bt = a.bank_transaction
            v = versamenti_map.get(bt.id)
            if v is None:
                v = {
                    "data": bt.data.isoformat(),
                    "descrizione": (bt.descrizione or "").strip()[:120],
                    "importo": float(bt.importo),
                    "imputato": Decimal("0"),
                    "imputazioni": [],
                }
                versamenti_map[bt.id] = v
            descr_r, _ = _descr_rendiconto(a.receivable)
            v["imputazioni"].append({
                "descrizione": descr_r,
                "causale": a.receivable.causale,
                "quota": float(a.importo),
            })
            v["imputato"] += a.importo
        versamenti = []
        tot_versato = Decimal("0")
        for v in sorted(versamenti_map.values(), key=lambda x: x["data"]):
            imputato = v.pop("imputato")
            v["imputato"] = float(imputato)
            tot_versato += imputato
            versamenti.append(v)

        # --- Chiusura deposito ---
        versato = tenant.deposito_versato or Decimal("0")
        override = tenant.deposito_da_restituire or Decimal("0")
        da_restituire = override if override > 0 else versato

        dep_qs = Receivable.objects.filter(
            assignment__tenant=tenant, causale=Receivable.Causale.DEPOSITO
        ).order_by("competenza_da", "id")
        riga_restituzione = next(
            (r for r in dep_qs if r.importo_dovuto < 0), None
        )
        restituito_effettivo = bool(
            riga_restituzione
            and riga_restituzione.stato == StatoPagamento.PAGATO
        )
        netto = Decimal("0") if restituito_effettivo else (da_restituire + saldo)
        residuo_debito = -netto if (not restituito_effettivo and netto < 0) else Decimal("0")

        deposito_movimenti = [
            {
                "data": r.competenza_da.isoformat() if r.competenza_da else None,
                "descrizione": r.descrizione or r.get_causale_display(),
                "importo": float(r.importo_dovuto),
                "pagato": float(r.importo_pagato or 0),
                "stato": r.stato,
            }
            for r in dep_qs
        ]

        return Response({
            "tenant": {
                "id": tenant.id,
                "nominativo": tenant.nominativo,
                "codice_fiscale": tenant.codice_fiscale or None,
                "email": (tenant.user.email or None) if tenant.user_id else None,
            },
            "periodo": {"da": periodo_da, "a": periodo_a},
            "emesso_il": oggi.isoformat(),
            "sezioni": sezioni,
            "totali": {
                "dovuto": float(tot_dovuto),
                "pagato": float(tot_pagato),
                "saldo": float(saldo),
            },
            "parziali_anno": parziali_anno,
            "versamenti": versamenti,
            "totale_versato": float(tot_versato),
            "deposito": {
                "versato": float(versato),
                "data_versamento": tenant.data_versamento_deposito.isoformat()
                if tenant.data_versamento_deposito else None,
                "da_restituire": float(da_restituire),
                "override": override > 0,
                "data_restituzione_prevista":
                    tenant.data_restituzione_prevista.isoformat()
                    if tenant.data_restituzione_prevista else None,
                "restituito_effettivo": restituito_effettivo,
                "netto_da_restituire": float(max(netto, Decimal("0"))),
                "residuo_debito": float(residuo_debito),
                "movimenti": deposito_movimenti,
            },
        })
