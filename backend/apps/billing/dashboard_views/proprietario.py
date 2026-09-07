"""
Dashboard proprietario e dettaglio bilancio per proprietario.
"""
import datetime
from decimal import Decimal

from django.db.models import Q, Sum
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPropertyMember
from billing.models import Receivable, StatoPagamento
from properties.models import OwnerProfile, TenantProfile

from ._common import (
    CAUSALI_OPERATIVE,
    TIPO_PER_CAUSALE,
    _conto_suggerito_id,
    _descrizione_receivable,
    _giorni_ritardo,
)

# ---------------------------------------------------------------------------
# Dashboard proprietario
# ---------------------------------------------------------------------------

class DashboardProprietarioView(APIView):
    """GET /api/v1/dashboard/proprietario/?anno=YYYY&mese=MM — Riepilogo KPI per i proprietari.

    Senza parametri: anno+mese correnti (vista operativa).
    Con `anno` diverso da quello corrente: vista storica, ritardi/in-scadenza vuoti.
    """

    permission_classes = [IsPropertyMember]

    def get(self, request):
        from properties.context import get_request_property

        prop = get_request_property(request)
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
                assignment__room__property=prop,
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
        spese_qs = Expense.objects.filter(
            property=prop, data__year=anno,
        ).select_related("category", "anticipata_da_owner")
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
        for o in OwnerProfile.objects.filter(
            user__property_memberships__property=prop
        ).distinct():
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
            Receivable.Causale.REGISTRAZIONE: "entrate_extra",
        }
        for r in Receivable.objects.filter(
            assignment__room__property=prop,
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
            Receivable.Causale.REGISTRAZIONE: "extra",
        }
        for r in Receivable.objects.filter(
            assignment__room__property=prop,
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
            # Ritardo = fatto temporale (scadenza passata) su Receivable non
            # ancora chiusi. Escludiamo PAGATO e INSOLUTO (insoluti storici
            # che non beccheremo più: non vogliamo ingolfare la dashboard).
            # Stesse causali della home inquilino: operative + le rate di
            # versamento del deposito (positive). Un deposito dichiarato e mai
            # confermato deve comparire qui, perché questa è l'unica pagina da
            # cui si conferma o si rifiuta una dichiarazione. Le restituzioni
            # (importo negativo) non sono un debito e restano fuori.
            causali_dovute = Q(causale__in=CAUSALI_OPERATIVE) | Q(
                causale=Receivable.Causale.DEPOSITO, importo_dovuto__gt=0
            )
            ritardi_qs = (
                Receivable.objects.filter(
                    causali_dovute,
                    assignment__room__property=prop,
                    scadenza__lt=oggi,
                )
                .exclude(stato__in=[StatoPagamento.PAGATO, StatoPagamento.INSOLUTO])
                .select_related(
                    "assignment__tenant",
                    "assignment__room__property__bank_account_utenze",
                    "assignment__bank_account_affitto",
                    "utility_period",
                )
            )
            scadenza_qs = (
                Receivable.objects.filter(
                    causali_dovute,
                    assignment__room__property=prop,
                    stato__in=[StatoPagamento.ATTESO, StatoPagamento.DICHIARATO],
                    scadenza__lte=soglia_scadenza,
                    scadenza__gte=oggi,
                )
                .select_related(
                    "assignment__tenant",
                    "assignment__room__property__bank_account_utenze",
                    "assignment__bank_account_affitto",
                    "utility_period",
                )
            )

        # Chi occupa una stanza *ora*: gli scoperti di chi se n'è andato sono
        # storia da ricostruire, non solleciti da mandare, e il frontend li
        # tiene fuori di default. Stessa regola del badge "ex inquilino"
        # (``assegnazione_in_corso_q``), così le due schermate concordano.
        tenant_attivi_ids = set(
            TenantProfile.objects.attivi(oggi, property=prop).values_list("id", flat=True)
        )

        def _fmt(r: Receivable) -> dict:
            giorni = _giorni_ritardo(r.scadenza, oggi)
            dovuto = r.importo_dovuto
            pagato = r.importo_pagato or Decimal("0")
            return {
                "tipo": TIPO_PER_CAUSALE[r.causale],
                "id": r.id,
                "tenant": r.assignment.tenant.nominativo,
                "tenant_id": r.assignment.tenant_id,
                "tenant_attivo": r.assignment.tenant_id in tenant_attivi_ids,
                "descrizione": _descrizione_receivable(r),
                # `importo` resta il dovuto pieno per retrocompatibilità.
                "importo": float(dovuto),
                "importo_dovuto": float(dovuto),
                "importo_pagato": float(pagato),
                # Quanto manca davvero: senza, un addebito coperto al 94%
                # sembra del tutto scoperto.
                "residuo": float(dovuto - pagato),
                "parziale": bool(0 < pagato < dovuto),
                "scadenza": r.scadenza.isoformat(),
                "stato": r.stato,
                "giorni_ritardo": giorni,
                # Servono al dialog di registrazione incasso aperto da qui:
                # il conto proposto è quello su cui l'addebito doveva entrare,
                # mai quello di chi sta guardando la pagina.
                "bank_account_destinazione_id": r.bank_account_destinazione_id,
                "conto_suggerito_id": _conto_suggerito_id(r),
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

    permission_classes = [IsPropertyMember]

    CAUSALE_LABEL = {
        Receivable.Causale.AFFITTO: "Affitto",
        Receivable.Causale.UTENZE: "Utenze",
        Receivable.Causale.EXTRA: "Addebito extra",
        Receivable.Causale.REGISTRAZIONE: "Addebito extra",
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

        from properties.context import get_request_property

        prop = get_request_property(request)
        try:
            owner = OwnerProfile.objects.filter(
                user__property_memberships__property=prop
            ).get(pk=owner_id)
        except OwnerProfile.DoesNotExist:
            return Response({"detail": "Proprietario non trovato."}, status=404)

        if tipo == "entrate":
            righe_qs = (
                Receivable.objects.filter(
                    assignment__room__property=prop,
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
                Expense.objects.filter(
                    property=prop, data__year=anno, anticipata_da_owner_id=owner_id,
                )
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
