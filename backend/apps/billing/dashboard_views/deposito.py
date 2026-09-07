"""
Restituzione esplicita del deposito cauzionale.
"""
import datetime
from decimal import Decimal

from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPropertyMember
from billing.models import Receivable, StatoPagamento
from properties.models import TenantProfile


class RestituzioneDepositoView(APIView):
    """Gestione esplicita dell'addebito (negativo) di restituzione deposito.

    Sostituisce il trigger implicito ``data_restituzione_prevista`` con
    un'operazione comandata dal frontend, idempotente e *correggibile*: se la
    riga esiste già la aggiorna (data/importo), invece di lasciarla cristallizzata
    al primo salvataggio come fa il signal. Mantiene allineato anche il profilo.

    GET /api/v1/tenants/<tenant_id>/restituzione-deposito/
        → stato corrente + valori suggeriti (data = fine occupazione,
        importo lordo = override o deposito versato).
    POST /api/v1/tenants/<tenant_id>/restituzione-deposito/
        body: {data_restituzione, importo}
        → crea o aggiorna il Receivable DEPOSITO negativo.
    """

    permission_classes = [IsPropertyMember]

    def _riga_restituzione(self, tenant: TenantProfile):
        return (
            Receivable.objects.filter(
                assignment__tenant=tenant,
                causale=Receivable.Causale.DEPOSITO,
                importo_dovuto__lt=0,
            )
            .order_by("-competenza_da", "-id")
            .first()
        )

    def _importo_suggerito(self, tenant: TenantProfile) -> Decimal:
        override = tenant.deposito_da_restituire or Decimal("0")
        if override > 0:
            return override
        return tenant.deposito_versato or Decimal("0")

    def get(self, request, tenant_id: int):
        from properties.context import get_request_property

        try:
            tenant = TenantProfile.objects.get(
                pk=tenant_id, property=get_request_property(request),
            )
        except TenantProfile.DoesNotExist:
            return Response({"detail": "Inquilino non trovato."}, status=404)

        ultimo = tenant.assignments.order_by("-valid_from", "-id").first()
        riga = self._riga_restituzione(tenant)
        return Response({
            "tenant_id": tenant.id,
            "esiste": riga is not None,
            "receivable_id": riga.id if riga else None,
            "data_corrente": riga.competenza_da.isoformat() if riga else None,
            "importo_corrente": float(-riga.importo_dovuto) if riga else None,
            "pagato": bool(riga and riga.stato == StatoPagamento.PAGATO),
            "ha_allocazioni": bool(riga and riga.allocations.exists()),
            "data_suggerita": (
                tenant.data_restituzione_prevista.isoformat()
                if tenant.data_restituzione_prevista
                else ultimo.valid_to.isoformat()
                if ultimo and ultimo.valid_to
                else None
            ),
            "importo_suggerito": float(self._importo_suggerito(tenant)),
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
            data_rest = datetime.date.fromisoformat(request.data["data_restituzione"])
            importo = Decimal(str(request.data["importo"]))
        except (KeyError, TypeError, ValueError):
            return Response(
                {"detail": "Body malformato: servono data_restituzione, importo."},
                status=400,
            )
        if importo <= 0:
            return Response(
                {"detail": "L'importo da restituire deve essere positivo."},
                status=400,
            )

        ultimo = tenant.assignments.order_by("-valid_from", "-id").first()
        if ultimo is None:
            return Response(
                {"detail": "Nessuna assegnazione: impossibile generare la restituzione."},
                status=409,
            )

        importo = importo.quantize(Decimal("0.01"))
        riga = self._riga_restituzione(tenant)

        if riga is not None:
            # Guardia allocations: una riga già riconciliata con bonifici non
            # si tocca da qui (vedi invariante allocations).
            if riga.allocations.exists():
                return Response(
                    {
                        "detail": (
                            "La restituzione è già riconciliata con dei bonifici: "
                            "modificala dalla riconciliazione, non da qui."
                        )
                    },
                    status=409,
                )
            riga.competenza_da = data_rest
            riga.scadenza = data_rest
            riga.importo_dovuto = -importo
            riga.save(update_fields=["competenza_da", "scadenza", "importo_dovuto"])
            creato = False
        else:
            riga = Receivable.objects.create(
                assignment=ultimo,
                causale=Receivable.Causale.DEPOSITO,
                descrizione="Deposito (restituzione)",
                competenza_da=data_rest,
                competenza_a=None,
                scadenza=data_rest,
                importo_dovuto=-importo,
                stato=StatoPagamento.ATTESO,
            )
            creato = True

        # Allinea il profilo. Il signal post_save vede che la riga negativa
        # esiste già e non interferisce (resta idempotente).
        tenant.data_restituzione_prevista = data_rest
        tenant.deposito_da_restituire = importo
        tenant.save(update_fields=["data_restituzione_prevista", "deposito_da_restituire"])

        return Response(
            {
                "receivable_id": riga.id,
                "creato": creato,
                "data_restituzione": data_rest.isoformat(),
                "importo": float(importo),
                "stato": riga.stato,
            },
            status=201 if creato else 200,
        )
