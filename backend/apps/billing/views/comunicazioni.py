"""
Invio comunicazioni agli inquilini.
"""

from accounts.permissions import (
    IsPropertyMember,
)
from properties.context import get_request_property
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class RiepilogoAddebitiInviaView(APIView):
    """POST /api/v1/riepilogo-addebiti/invia/ — anteprima o invio.

    Body JSON::

        {"dry_run": true, "escludi": [<tenant_id>, ...], "giorni": 15}

    Un solo endpoint con ``dry_run`` nel body, come
    ``utility-periods/<id>/invia-avvisi/``: il frontend lo chiama in
    ``dry_run=true`` al mount per mostrare l'anteprima reale delle email, poi
    con ``dry_run=false`` per spedire.

    L'immobile è quello attivo della richiesta (``X-Property-Id`` validato):
    lo scoping non è falsificabile dal client. Il ruolo ``sola_lettura`` è già
    escluso da ``IsPropertyMember``, che nega i metodi non-safe — anteprima
    compresa, essendo una POST.

    Risposta non paginata di proposito: la lista dei destinatari deve
    arrivare intera, un troncamento silenzioso qui significherebbe non
    accorgersi di chi non riceve.
    """

    permission_classes = [IsPropertyMember]

    def post(self, request):
        from billing.calc.riepilogo import GIORNI_PENDENTI, invia_riepiloghi

        prop = get_request_property(request)
        dry_run = bool(request.data.get("dry_run", True))

        escludi = request.data.get("escludi") or []
        if not isinstance(escludi, list) or not all(
            isinstance(x, int) for x in escludi
        ):
            return Response(
                {"detail": "'escludi' deve essere una lista di id inquilino."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Deroga esplicita: ex inquilini spuntati a mano, che l'invio
        # automatico salta. Solo da qui — la CLI non la espone.
        includi = request.data.get("includi") or []
        if not isinstance(includi, list) or not all(
            isinstance(x, int) for x in includi
        ):
            return Response(
                {"detail": "'includi' deve essere una lista di id inquilino."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        giorni = request.data.get("giorni", GIORNI_PENDENTI)
        try:
            giorni = int(giorni)
        except (TypeError, ValueError):
            return Response(
                {"detail": "'giorni' deve essere un intero."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if giorni < 0:
            return Response(
                {"detail": "'giorni' non può essere negativo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        risultato = invia_riepiloghi(
            prop,
            dry_run=dry_run,
            escludi_ids=escludi,
            includi_ids=includi,
            giorni=giorni,
        )
        return Response(risultato)
