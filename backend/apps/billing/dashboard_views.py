"""
Endpoint custom per le dashboard inquilino, proprietario e quadro annuale.
"""
import datetime
from decimal import Decimal

from django.db.models import Q, Sum
from rest_framework.permissions import IsAuthenticated  # noqa: F401
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsInquilino, IsProprietario
from billing._dates import format_mese, format_mese_anno
from billing.models import Receivable, StatoPagamento, TenantCondominioRate, UtilityChargePeriod
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
# CAPARRA è esclusa: i depositi cauzionali non sono entrate operative.
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

        # Caparra dell'anno: esposta solo dopo la chiusura (data di restituzione
        # valorizzata). Senza, il versamento incassato in passato apparirebbe come
        # credito permanente dell'inquilino.
        caparra_righe: list[dict] = []
        caparra_dovuto = Decimal("0")
        caparra_pagato = Decimal("0")
        caparra_qs_list: list[Receivable] = []
        if tenant.data_restituzione_deposito:
            caparra_qs = (
                Receivable.objects.filter(
                    assignment__tenant=tenant,
                    causale=Receivable.Causale.CAPARRA,
                    competenza_da__year=anno,
                )
                .order_by("competenza_da")
            )
            caparra_qs_list = list(caparra_qs)
            for r in caparra_qs_list:
                caparra_righe.append({
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
                caparra_dovuto += r.importo_dovuto
                if r.importo_pagato:
                    caparra_pagato += r.importo_pagato

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

        totale_dovuto = rent_dovuto + utility_dovuto + extra_totale + caparra_dovuto
        totale_pagato = rent_pagato + utility_pagato + extra_pagato + caparra_pagato

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
            "caparra": {
                "dovuto_anno": float(caparra_dovuto),
                "pagato_anno": float(caparra_pagato),
                "saldo": float(caparra_pagato - caparra_dovuto),
                "righe": caparra_righe,
            },
            "totali_anno": {
                "dovuto": float(totale_dovuto),
                "pagato": float(totale_pagato),
                "saldo": float(totale_pagato - totale_dovuto),
            },
            "ritardo_medio_giorni": ritardo_medio,
        })
