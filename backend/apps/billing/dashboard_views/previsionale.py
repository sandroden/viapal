"""
Stima previsionale utenze all'uscita e relativo conguaglio.
"""
import datetime
from decimal import Decimal

from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPropertyMember
from billing.models import Receivable, StatoPagamento
from properties.models import RoomAssignment, TenantProfile

# ---------------------------------------------------------------------------
# Stima previsionale utenze (per restituzione deposito)
# ---------------------------------------------------------------------------


# Marker che identifica un Receivable come "previsionale utenze".
# Salvato come prima riga delle note al momento della creazione (POST).
MARKER_PREVISIONALE = "previsionale_utenze"
MARKER_CONGUAGLIO = "conguaglio_previsionale"


def _calcola_stima_previsionale(tenant: TenantProfile, data_target: datetime.date):
    """Ritorna dict con stima (vedi PrevisionaleUtenzeView) oppure ``None``
    insieme a un messaggio di errore se la stima non è calcolabile.
    """
    utenze_recenti = list(
        Receivable.objects.filter(
            assignment__tenant=tenant,
            causale=Receivable.Causale.UTENZE,
            giorni_presenza__gt=0,
        )
        .select_related("utility_period")
        .order_by("-utility_period__periodo_a")[:2]
    )
    if not utenze_recenti:
        return None, "Nessuna utenza pregressa disponibile per la stima."
    tot_importo = sum((r.importo_dovuto for r in utenze_recenti), Decimal("0"))
    tot_giorni = sum(r.giorni_presenza or 0 for r in utenze_recenti)
    if tot_giorni == 0:
        return None, "giorni_presenza nulli sui Receivable di riferimento."
    media_giornaliera = (tot_importo / Decimal(tot_giorni)).quantize(Decimal("0.01"))
    ultimo_periodo = utenze_recenti[0].utility_period
    data_da = ultimo_periodo.periodo_a if ultimo_periodo else None
    if data_da is None or data_da >= data_target:
        return None, (
            f"Data inizio stima ({data_da}) non precede target "
            f"({data_target}): nessuna utenza prevedibile."
        )
    giorni = (data_target - data_da).days
    importo_stimato = (media_giornaliera * Decimal(giorni)).quantize(Decimal("0.01"))
    return {
        "data_da": data_da,
        "data_a": data_target,
        "giorni": giorni,
        "media_giornaliera": media_giornaliera,
        "importo_stimato": importo_stimato,
        "utenze_recenti": utenze_recenti,
    }, None


class PrevisionaleUtenzeView(APIView):
    """
    GET /api/v1/tenants/<tenant_id>/previsionale-utenze/?data_target=YYYY-MM-DD
        → stima dell'importo per utenze previsionali a fine locazione.
    POST /api/v1/tenants/<tenant_id>/previsionale-utenze/
        body: {assignment, data_da, data_a, importo, descrizione?}
        → crea un Receivable EXTRA marcato come previsionale, con
        competenza_da/competenza_a valorizzate sul range coperto.

    Il marker ``previsionale_utenze`` nella prima riga delle note serve poi
    a identificare il Receivable in fase di conguaglio (vedi
    ConguagliaPrevisionaleView).
    """

    permission_classes = [IsPropertyMember]

    def get(self, request, tenant_id: int):
        from properties.context import get_request_property

        try:
            tenant = TenantProfile.objects.get(
                pk=tenant_id, property=get_request_property(request),
            )
        except TenantProfile.DoesNotExist:
            return Response({"detail": "Inquilino non trovato."}, status=404)

        oggi = datetime.date.today()
        data_target_raw = request.query_params.get("data_target")
        if data_target_raw:
            try:
                data_target = datetime.date.fromisoformat(data_target_raw)
            except ValueError:
                return Response(
                    {"detail": "data_target non valida (ISO YYYY-MM-DD)."},
                    status=400,
                )
        elif tenant.data_restituzione_prevista:
            data_target = tenant.data_restituzione_prevista
        else:
            data_target = oggi

        stima, err = _calcola_stima_previsionale(tenant, data_target)
        if err:
            return Response({"detail": err}, status=409)

        return Response({
            "tenant_id": tenant.id,
            "data_da": stima["data_da"].isoformat(),
            "data_a": stima["data_a"].isoformat(),
            "giorni": stima["giorni"],
            "media_giornaliera": float(stima["media_giornaliera"]),
            "importo_stimato": float(stima["importo_stimato"]),
            "basato_su": [
                {
                    "receivable_id": r.id,
                    "periodo_da": r.utility_period.periodo_da.isoformat()
                    if r.utility_period else None,
                    "periodo_a": r.utility_period.periodo_a.isoformat()
                    if r.utility_period else None,
                    "importo_dovuto": float(r.importo_dovuto),
                    "giorni_presenza": r.giorni_presenza,
                }
                for r in stima["utenze_recenti"]
            ],
        })

    def post(self, request, tenant_id: int):
        from properties.context import get_request_property

        try:
            tenant = TenantProfile.objects.get(
                pk=tenant_id, property=get_request_property(request),
            )
        except TenantProfile.DoesNotExist:
            return Response({"detail": "Inquilino non trovato."}, status=404)

        try:
            assignment_id = int(request.data["assignment"])
            data_da = datetime.date.fromisoformat(request.data["data_da"])
            data_a = datetime.date.fromisoformat(request.data["data_a"])
            importo = Decimal(str(request.data["importo"]))
        except (KeyError, TypeError, ValueError):
            return Response(
                {
                    "detail": (
                        "Body malformato: servono assignment, data_da, "
                        "data_a, importo."
                    )
                },
                status=400,
            )
        if importo <= 0:
            return Response(
                {"detail": "L'importo del previsionale deve essere positivo."},
                status=400,
            )
        if data_a <= data_da:
            return Response(
                {"detail": "data_a deve essere successiva a data_da."},
                status=400,
            )
        try:
            assignment = RoomAssignment.objects.get(
                pk=assignment_id, tenant=tenant
            )
        except RoomAssignment.DoesNotExist:
            return Response(
                {"detail": "Assignment non trovato per questo inquilino."},
                status=404,
            )

        descrizione = (request.data.get("descrizione") or "").strip()
        if not descrizione:
            descrizione = (
                f"Previsionale utenze "
                f"{data_da.isoformat()} → {data_a.isoformat()}"
            )

        rec = Receivable.objects.create(
            assignment=assignment,
            causale=Receivable.Causale.EXTRA,
            descrizione=descrizione[:300],
            competenza_da=data_da,
            competenza_a=data_a,
            scadenza=data_a,
            importo_dovuto=importo.quantize(Decimal("0.01")),
            stato=StatoPagamento.ATTESO,
            note=MARKER_PREVISIONALE,
        )
        return Response(
            {
                "id": rec.id,
                "assignment": rec.assignment_id,
                "descrizione": rec.descrizione,
                "competenza_da": rec.competenza_da.isoformat(),
                "competenza_a": rec.competenza_a.isoformat(),
                "scadenza": rec.scadenza.isoformat(),
                "importo": float(rec.importo_dovuto),
                "stato": rec.stato,
            },
            status=201,
        )



class ConguagliaPrevisionaleView(APIView):
    """
    GET /api/v1/tenants/<tenant_id>/conguaglia-previsionale/?previsionale_id=N
        → anteprima: lista utenze reali nel periodo del previsionale e
        rettifica proposta.
    POST /api/v1/tenants/<tenant_id>/conguaglia-previsionale/
        body: {previsionale_id}
        → crea Receivable EXTRA di rettifica con importo = -somma_utenze
        e marca il previsionale come conguagliato.
    """

    permission_classes = [IsPropertyMember]

    def _load_previsionale(self, tenant: TenantProfile, previsionale_id):
        try:
            prev = Receivable.objects.select_related("assignment").get(
                pk=previsionale_id,
                assignment__tenant=tenant,
            )
        except Receivable.DoesNotExist:
            return None, Response(
                {"detail": "Previsionale non trovato per questo inquilino."},
                status=404,
            )
        if MARKER_PREVISIONALE not in (prev.note or ""):
            return None, Response(
                {"detail": "Il Receivable indicato non è un previsionale."},
                status=400,
            )
        if MARKER_CONGUAGLIO in (prev.note or ""):
            return None, Response(
                {"detail": "Previsionale già conguagliato."},
                status=409,
            )
        if not prev.competenza_da or not prev.competenza_a:
            return None, Response(
                {
                    "detail": (
                        "Il previsionale non ha competenza_da/competenza_a "
                        "valorizzate."
                    )
                },
                status=400,
            )
        return prev, None

    def _utenze_nel_periodo(self, tenant: TenantProfile, data_da, data_a):
        # Receivable utenze del tenant da conguagliare contro il previsionale.
        #
        # ``data_da`` del previsionale coincide con la fine dell'ultima bolletta
        # già fatturata (vedi _calcola_stima_previsionale), quindi:
        #   * si includono i periodi che FINISCONO dopo data_da (periodo_a__gt):
        #     quello che finisce esattamente su data_da è già stato addebitato a
        #     parte e non va riconguagliato (evita la riga di bordo a 1 giorno);
        #   * NON si ri-ripartisce: ``importo_dovuto`` è già la quota
        #     dell'inquilino ripartita sui suoi giorni di presenza, quindi si
        #     somma per intero (niente secondo pro-rata).
        candidate = (
            Receivable.objects.filter(
                assignment__tenant=tenant,
                causale=Receivable.Causale.UTENZE,
                utility_period__periodo_da__lte=data_a,
                utility_period__periodo_a__gt=data_da,
            )
            .select_related("utility_period")
            .order_by("utility_period__periodo_da")
        )
        righe = []
        somma = Decimal("0")
        for r in candidate:
            p = r.utility_period
            if not p:
                continue
            importo = r.importo_dovuto.quantize(Decimal("0.01"))
            giorni_totali = (p.periodo_a - p.periodo_da).days + 1
            righe.append({
                "receivable_id": r.id,
                "periodo_da": p.periodo_da.isoformat(),
                "periodo_a": p.periodo_a.isoformat(),
                "importo_dovuto": float(importo),
                "giorni_presenza": r.giorni_presenza,
                "giorni_totali": giorni_totali,
                "quota_nel_periodo": float(importo),
            })
            somma += importo
        return righe, somma

    def get(self, request, tenant_id: int):
        from properties.context import get_request_property

        try:
            tenant = TenantProfile.objects.get(
                pk=tenant_id, property=get_request_property(request),
            )
        except TenantProfile.DoesNotExist:
            return Response({"detail": "Inquilino non trovato."}, status=404)

        prev_id = request.query_params.get("previsionale_id")
        if not prev_id:
            return Response(
                {"detail": "previsionale_id obbligatorio."}, status=400
            )
        prev, err_resp = self._load_previsionale(tenant, prev_id)
        if err_resp:
            return err_resp

        righe, somma = self._utenze_nel_periodo(
            tenant, prev.competenza_da, prev.competenza_a
        )
        rettifica = -somma  # segno opposto al previsionale
        netto = prev.importo_dovuto + rettifica
        return Response({
            "previsionale_id": prev.id,
            "previsionale_importo": float(prev.importo_dovuto),
            "data_da": prev.competenza_da.isoformat(),
            "data_a": prev.competenza_a.isoformat(),
            "utenze_reali": righe,
            "somma_utenze_reali": float(somma),
            "rettifica_proposta": float(rettifica),
            "netto_a_favore_inquilino": float(netto),
        })

    def post(self, request, tenant_id: int):
        from properties.context import get_request_property

        try:
            tenant = TenantProfile.objects.get(
                pk=tenant_id, property=get_request_property(request),
            )
        except TenantProfile.DoesNotExist:
            return Response({"detail": "Inquilino non trovato."}, status=404)

        prev_id = request.data.get("previsionale_id")
        if not prev_id:
            return Response(
                {"detail": "previsionale_id obbligatorio."}, status=400
            )
        prev, err_resp = self._load_previsionale(tenant, prev_id)
        if err_resp:
            return err_resp

        righe, somma = self._utenze_nel_periodo(
            tenant, prev.competenza_da, prev.competenza_a
        )
        if somma == 0:
            return Response(
                {
                    "detail": (
                        "Nessuna utenza reale nel periodo del previsionale: "
                        "niente da conguagliare."
                    )
                },
                status=409,
            )

        from django.db import transaction
        with transaction.atomic():
            rettifica = Receivable.objects.create(
                assignment=prev.assignment,
                causale=Receivable.Causale.EXTRA,
                descrizione=(
                    f"Conguaglio previsionale {prev.competenza_da.isoformat()} "
                    f"→ {prev.competenza_a.isoformat()}"
                )[:300],
                competenza_da=prev.competenza_da,
                competenza_a=prev.competenza_a,
                scadenza=prev.competenza_a,
                importo_dovuto=(-somma).quantize(Decimal("0.01")),
                stato=StatoPagamento.ATTESO,
                note=f"{MARKER_CONGUAGLIO}:{prev.id}",
            )
            # Marca il previsionale come conguagliato.
            note_aggiornate = (prev.note or "") + f"\n{MARKER_CONGUAGLIO}:{rettifica.id}"
            prev.note = note_aggiornate.strip()
            prev.save(update_fields=["note", "updated_at"])

        return Response(
            {
                "rettifica_id": rettifica.id,
                "importo_rettifica": float(rettifica.importo_dovuto),
                "somma_utenze_reali": float(somma),
                "utenze_reali": righe,
                "netto_a_favore_inquilino": float(
                    prev.importo_dovuto + rettifica.importo_dovuto
                ),
            },
            status=201,
        )
