"""
Dashboard inquilino e drilldown per singolo inquilino.
"""
import datetime
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsInquilino
from billing.calc.posizione import posizione_inquilino
from billing.models import Receivable, StatoPagamento, TenantCondominioRate
from properties.models import RoomAssignment, TenantProfile
from properties.serializers import TenantProfileSerializer

from ._common import (
    CAUSALI_OPERATIVE,
    TIPO_PER_CAUSALE,
    _conto_suggerito_id,
    _descrizione_receivable,
    _giorni_ritardo,
)
from .deposito import importo_suggerito, versato_effettivo
from .rendiconto import _resti_per_anno, _sbilancio_progressivo

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

        # Posizione contabile (formula unica, condivisa con le email di
        # sollecito): addebiti aperti, totali e credito non imputato.
        posizione = posizione_inquilino(tenant, oggi)
        assignment_attivo = posizione["assignment_attivo"]

        stanza_corrente = None
        if assignment_attivo:
            stanza_corrente = {
                "id": assignment_attivo.room.id,
                "nome": assignment_attivo.room.nome,
                "canone_mensile": float(assignment_attivo.canone_mensile),
                "valid_from": assignment_attivo.valid_from.isoformat(),
                "tipo_gestione": assignment_attivo.room.property.tipo_gestione,
            }

        da_pagare = posizione["items"]
        netto_da_versare = posizione["netto_da_versare"]

        # Saldo totale "per pareggiare": somma dei residui aperti, con un unico
        # conto bonifico (quello utenze della proprietà) — un pagamento unico
        # può accorpare causali diverse.
        saldo_totale = {
            # `importo` = quanto versare davvero (lordo al netto del credito).
            "importo": float(netto_da_versare),
            "lordo": float(posizione["totale_residuo"]),
            "credito_disponibile": float(posizione["credito_disponibile"]),
            "pagamento": None,
        }
        conto_cum = posizione["conto_cumulativo"]
        if conto_cum and netto_da_versare > 0:
            saldo_totale["pagamento"] = {
                "beneficiario": conto_cum.intestatario,
                "iban": conto_cum.iban,
                "banca": conto_cum.banca,
                "causale": f"Saldo Viapal - {tenant.nominativo}"[:140],
            }

        assignments = RoomAssignment.objects.filter(tenant=tenant)
        ultimi_pagati_qs = (
            Receivable.objects.filter(
                assignment__in=assignments,
                stato=StatoPagamento.PAGATO,
            )
            .filter(
                # Stesse causali della lista "da pagare" qui sopra: operative
                # più le rate di versamento del deposito. Una rata di deposito
                # pagata è un movimento dell'inquilino a tutti gli effetti.
                Q(causale__in=CAUSALI_OPERATIVE)
                | Q(
                    causale=Receivable.Causale.DEPOSITO,
                    importo_dovuto__gt=0,
                )
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
            "saldo_totale": saldo_totale,
            "ultimi_pagamenti": ultimi_pagamenti,
        })



# ---------------------------------------------------------------------------
# Situazione per inquilino (drilldown)
# ---------------------------------------------------------------------------

class TenantSituazioneView(APIView):
    """
    GET /api/v1/tenants/<tenant_id>/situazione/?anno=YYYY

    Riepilogo completo per un inquilino: anagrafica, assignment storici,
    affitti, utenze (con voci dettagliate) e addebiti extra dell'anno.
    Accessibile ai proprietari (qualunque inquilino) e all'inquilino stesso
    (solo il proprio profilo).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, tenant_id: int):
        oggi = datetime.date.today()
        try:
            anno = int(request.query_params.get("anno", oggi.year))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Parametro 'anno' deve essere un intero."}, status=400
            )

        try:
            tenant = TenantProfile.objects.select_related("user", "property").get(pk=tenant_id)
        except TenantProfile.DoesNotExist:
            return Response(
                {"detail": "Inquilino non trovato."}, status=404
            )

        user = request.user
        is_gestione = user.is_superuser or user.property_memberships.filter(
            property_id=tenant.property_id
        ).exists()
        if not is_gestione and tenant.user_id != user.id:
            return Response(
                {"detail": "Puoi accedere solo ai tuoi dati."}, status=403
            )

        assignments_qs = (
            RoomAssignment.objects.filter(tenant=tenant)
            .select_related("room", "contract")
            .order_by("-valid_from")
        )
        assignments_payload = [
            {
                "id": a.id,
                "room_id": a.room.id,
                "room_nome": a.room.nome,
                "contract": a.contract_id,
                "contract_nome": (
                    (a.contract.nome or f"Contratto dal {a.contract.data_decorrenza}")
                    if a.contract_id
                    else ""
                ),
                "valid_from": a.valid_from.isoformat(),
                "valid_to": a.valid_to.isoformat() if a.valid_to else None,
                "rinunciata": a.rinunciata,
                "data_rinuncia": a.data_rinuncia.isoformat()
                if a.data_rinuncia
                else None,
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
            .select_related(
                "assignment__bank_account_affitto",
                "assignment__room__property__bank_account_utenze",
            )
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
                "conto_suggerito_id": _conto_suggerito_id(r),
            })
            rent_dovuto += r.importo_dovuto
            if r.importo_pagato:
                rent_pagato += r.importo_pagato

        # Utenze dell'anno (per utility_period.periodo_da). Il previsionale
        # d'uscita e la sua rettifica non hanno periodo: per loro conta
        # ``competenza_da``.
        utility_qs = (
            Receivable.objects.filter(
                assignment__tenant=tenant,
                causale=Receivable.Causale.UTENZE,
            )
            .filter(
                Q(utility_period__periodo_da__year=anno)
                | Q(utility_period__isnull=True, competenza_da__year=anno)
            )
            .select_related(
                "utility_period", "assignment__room__property__bank_account_utenze"
            )
            .annotate(n_conguagli=Count("conguagli"))
            .order_by(Coalesce("utility_period__periodo_da", "competenza_da"), "id")
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
                "conto_suggerito_id": _conto_suggerito_id(r),
                # Previsionale d'uscita e relativa rettifica (vedi
                # dashboard_views/previsionale.py): descrizione al posto
                # del periodo, che qui manca.
                "descrizione": r.descrizione,
                "previsionale": r.previsionale,
                "previsionale_conguagliato": r.previsionale and r.n_conguagli > 0,
                "conguaglio_di": r.conguaglio_di_id,
            })
            utility_dovuto += r.importo_dovuto
            if r.importo_pagato:
                utility_pagato += r.importo_pagato

        # Addebiti extra dell'anno (filtra su competenza_da come data dell'addebito).
        # La registrazione contratto viaggia qui sotto "extra": è un addebito
        # una-tantum dell'inquilino e così entra anche in ``extra_totale`` →
        # ``totale_dovuto``, coerente con lo sbilancio reale che già la include.
        extra_qs = (
            Receivable.objects.filter(
                assignment__tenant=tenant,
                causale__in=(
                    Receivable.Causale.EXTRA,
                    Receivable.Causale.REGISTRAZIONE,
                ),
                competenza_da__year=anno,
            )
            .select_related("assignment__room__property__bank_account_utenze")
            .order_by("competenza_da")
        )
        extra_righe = []
        extra_totale = Decimal("0")
        extra_pagato = Decimal("0")
        for r in extra_qs:
            extra_righe.append({
                "id": r.id,
                "data": r.competenza_da.isoformat(),
                "competenza_a": r.competenza_a.isoformat() if r.competenza_a else None,
                "descrizione": r.descrizione,
                "importo": float(r.importo_dovuto),
                "importo_pagato": float(r.importo_pagato or 0),
                "scadenza": r.scadenza.isoformat() if r.scadenza else None,
                "stato": r.stato,
                "data_pagamento": r.data_pagamento.isoformat() if r.data_pagamento else None,
                "bank_account_destinazione_id": r.bank_account_destinazione_id,
                "conto_suggerito_id": _conto_suggerito_id(r),
            })
            extra_totale += r.importo_dovuto
            if r.importo_pagato:
                extra_pagato += r.importo_pagato

        # Deposito dell'anno: il versamento è sempre esposto. La riga di
        # restituzione (importo negativo) compare solo dopo la chiusura
        # (``data_restituzione_prevista`` valorizzata). Il deposito NON entra
        # nei totali dovuto/pagato dell'anno (vedi più sotto), coerente con
        # ``saldi`` che già esclude la causale DEPOSITO.
        deposito_righe: list[dict] = []
        deposito_dovuto = Decimal("0")
        deposito_pagato = Decimal("0")
        deposito_qs = Receivable.objects.filter(
            assignment__tenant=tenant,
            causale=Receivable.Causale.DEPOSITO,
            competenza_da__year=anno,
        )
        if not tenant.data_restituzione_prevista:
            # Senza data di restituzione mostriamo solo il versamento
            # (importo positivo), mai la restituzione.
            deposito_qs = deposito_qs.filter(importo_dovuto__gt=0)
        deposito_qs = deposito_qs.select_related(
            "assignment__room__property__bank_account_utenze"
        ).order_by("competenza_da")
        for r in deposito_qs:
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
                "conto_suggerito_id": _conto_suggerito_id(r),
            })
            deposito_dovuto += r.importo_dovuto
            if r.importo_pagato:
                deposito_pagato += r.importo_pagato

        # Ritardo medio: tutti i Receivable dell'anno con scadenza valida.
        # Pagati: ritardo storico (data_pagamento - scadenza).
        # Non pagati: ritardo in essere (oggi - scadenza).
        #
        # NOTA (2026-06-04): la card che espone questo dato è nascosta nel
        # frontend perché poco significativo e spesso fuorviante. Limiti noti:
        #   1. La media considera solo i ritardi positivi (d > 0): gli anticipi
        #      non la compensano mai, quindi un singolo ritardo domina il valore.
        #   2. `data_pagamento` = Max(data BT allocata) (vedi signals.py): un
        #      residuo di matching (es. saldo di 20€ con un bonifico del mese
        #      dopo) sposta in avanti la data dell'intero addebito.
        #   3. Le scadenze utenze sono spesso più strette del ciclo reale di
        #      emissione/invio, generando ritardi fittizi sistematici.
        # Ha senso solo se misurato rispetto alla scadenza reale *dell'addebito*:
        # prima di quella data è anticipo, non ritardo. Calcolo lasciato per
        # eventuale riattivazione futura.
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

        # Il deposito è escluso dai totali dell'anno: è un movimento
        # cauzionale, non una partita di competenza, e ``saldi`` lo esclude già.
        totale_dovuto = rent_dovuto + utility_dovuto + extra_totale
        totale_pagato = rent_pagato + utility_pagato + extra_pagato

        # Saldi "globali" = sbilancio reale (saldo-imputazioni + resti dei
        # bonifici), coerente con il rendiconto. ``saldi.anno`` è lo
        # sbilancio dell'anno selezionato; ``saldi.totale`` è il
        # progressivo cumulato *fino a quell'anno* (non conosce il futuro:
        # nella pagina del 2025 non entrano i movimenti del 2026).
        receivable_base = (
            Receivable.objects.filter(assignment__tenant=tenant)
            .exclude(causale=Receivable.Causale.DEPOSITO)
        )
        dovuto_pagato_anno: dict[int, list] = {}
        for row in (
            receivable_base.values("competenza_da__year").annotate(
                d=Coalesce(Sum("importo_dovuto"), Decimal("0")),
                p=Coalesce(Sum("importo_pagato"), Decimal("0")),
            )
        ):
            y = row["competenza_da__year"] or 0
            dovuto_pagato_anno[y] = [row["d"], row["p"]]
        per_anno_sit, _ = _sbilancio_progressivo(
            dovuto_pagato_anno, _resti_per_anno(tenant)
        )
        ent_anno = next(
            (x for x in per_anno_sit if x["anno"] == anno), None
        )
        saldo_anno_globale = ent_anno["saldo_anno"] if ent_anno else 0.0
        saldo_totale_globale = 0.0
        for x in per_anno_sit:
            if x["anno"] <= anno:
                saldo_totale_globale = x["saldo_progressivo"]

        contract_attivo = tenant.property.contratto_attivo(oggi)
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

        # Quota condominio: dell'immobile dell'inquilino, contratto o meno.
        # Solo la base (tenant vuoto) e le eventuali eccezioni di QUESTO
        # inquilino: mai le eccezioni di altri.
        quota_condominio = {
            "corrente": None,
            "storico": [],
        }
        quote_qs = (
            TenantCondominioRate.objects
            .filter(property=tenant.property)
            .filter(Q(tenant__isnull=True) | Q(tenant=tenant))
            .order_by("-valid_from")
        )
        quote_storico = []
        attive_specifiche = []
        attive_generiche = []
        for q in quote_qs:
            specifica = q.tenant_id is not None
            row = {
                "id": q.id,
                "valid_from": q.valid_from.isoformat(),
                "valid_to": q.valid_to.isoformat() if q.valid_to else None,
                "importo_mensile": float(q.importo_mensile),
                "note": q.note,
                "specifica": specifica,
            }
            quote_storico.append(row)
            attiva = q.valid_from <= oggi and (q.valid_to is None or q.valid_to >= oggi)
            if attiva:
                (attive_specifiche if specifica else attive_generiche).append(row)
        quota_condominio["storico"] = quote_storico
        # La quota specifica dell'inquilino prevale sulla base dell'immobile;
        # tra righe valide alla stessa data vince quella con valid_from più
        # recente (quote_qs è ordinato -valid_from).
        if attive_specifiche:
            quota_condominio["corrente"] = attive_specifiche[0]
        elif attive_generiche:
            quota_condominio["corrente"] = attive_generiche[0]

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
                # Fuori dall'anno: il pattuito in anagrafica, quanto è
                # entrato davvero (rate pagate) e il lordo che si renderebbe
                # oggi (override o incassato). La simulazione di uscita
                # ragiona su questi, non su ``tenant.deposito_versato``.
                "pattuito": float(tenant.deposito_versato or 0),
                "incassato": float(versato_effettivo(tenant)),
                "da_rendere": float(importo_suggerito(tenant)),
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
