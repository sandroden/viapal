"""API dei lead: una per il bot che li deposita, una per chi li lavora.

L'immobile è quello attivo della richiesta (header ``X-Property-Id``, o unico
accessibile): il bot lo dichiara come qualunque altro client, e la membership
viene verificata lato server come sempre — nessun percorso di autorizzazione
nuovo da mantenere.
"""
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from accounts.permissions import IsPropertyMember
from billing.views import BillingPagination
from properties.context import get_request_property

from .models import Lead
from .serializers import (
    CAMPI_BOT,
    LeadBulkUpsertSerializer,
    LeadLavorazioneSerializer,
    LeadSerializer,
)


class LeadViewSet(ModelViewSet):
    """/api/v1/leads/ — la lista su cui si lavora, in due.

    Sola lettura più il PATCH di lavorazione: i lead nascono dal bot, non si
    creano a mano. Filtri: ``stato``, ``gruppo`` (id del gruppo Facebook),
    ``preso_da`` (id utente, oppure ``me``/``nessuno``).
    """

    permission_classes = [IsPropertyMember]
    pagination_class = BillingPagination
    # Niente POST/DELETE sulle risorse: i lead li crea il bot e li cancella
    # la chiusura di campagna. Il POST serve solo alle action qui sotto.
    http_method_names = ["get", "patch", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action == "partial_update":
            return LeadLavorazioneSerializer
        return LeadSerializer

    def get_queryset(self):
        prop = get_request_property(self.request)
        qs = Lead.objects.filter(property=prop).select_related("preso_da")
        p = self.request.query_params
        if stato := p.get("stato"):
            qs = qs.filter(stato__in=stato.split(","))
        if gruppo := p.get("gruppo"):
            qs = qs.filter(group_id=gruppo)
        preso = p.get("preso_da")
        if preso == "me":
            qs = qs.filter(preso_da=self.request.user)
        elif preso == "nessuno":
            qs = qs.filter(preso_da__isnull=True)
        elif preso:
            qs = qs.filter(preso_da_id=preso)
        return qs

    def partial_update(self, request, *args, **kwargs):
        # Il PATCH torna il lead intero: la pagina aggiorna la card senza
        # dover rileggere la lista.
        super().partial_update(request, *args, **kwargs)
        istanza = self.get_object()
        return Response(LeadSerializer(istanza).data)

    @action(detail=True, methods=["post"])
    def prendi(self, request, pk=None):
        """Presa in carico: «lo contatto io».

        Assegna sempre a chi chiama — nessuno prende in carico al posto di un
        altro. Se il lead è già di qualcun altro risponde 409 con il nome:
        l'altro ci sta scrivendo adesso, e due messaggi alla stessa persona
        sono esattamente ciò che questa pagina serve a evitare.
        """
        lead = self.get_object()
        if lead.preso_da_id and lead.preso_da_id != request.user.pk:
            nome = lead.preso_da.get_full_name() or lead.preso_da.username
            return Response(
                {"detail": f"Già preso in carico da {nome}.", "preso_da_nome": nome},
                status=status.HTTP_409_CONFLICT,
            )
        lead.preso_da = request.user
        lead.preso_at = timezone.now()
        lead.save(update_fields=["preso_da", "preso_at", "updated_at"])
        return Response(LeadSerializer(lead).data)

    @action(detail=True, methods=["post"])
    def rilascia(self, request, pk=None):
        """Lascia il lead a disposizione degli altri."""
        lead = self.get_object()
        if lead.preso_da_id and lead.preso_da_id != request.user.pk:
            if not request.user.is_superuser:
                nome = lead.preso_da.get_full_name() or lead.preso_da.username
                return Response(
                    {"detail": f"È in carico a {nome}: solo chi l'ha preso può lasciarlo."},
                    status=status.HTTP_409_CONFLICT,
                )
        lead.preso_da = None
        lead.preso_at = None
        lead.save(update_fields=["preso_da", "preso_at", "updated_at"])
        return Response(LeadSerializer(lead).data)

    @action(detail=False)
    def riepilogo(self, request):
        """Conteggi per stato — i numeri sui filtri della pagina."""
        prop = get_request_property(request)
        qs = Lead.objects.filter(property=prop)
        per_stato = {s: 0 for s, _ in Lead.Stato.choices}
        for riga in qs.values("stato").annotate(n=Count("id")):
            per_stato[riga["stato"]] = riga["n"]
        gruppi = sorted(
            {
                (l["group_id"], l["group_label"])
                for l in qs.exclude(group_id="").values("group_id", "group_label")
            }
        )
        return Response(
            {
                "totale": sum(per_stato.values()),
                "per_stato": per_stato,
                "gruppi": [{"id": g, "nome": n} for g, n in gruppi],
            }
        )

    @action(detail=False, methods=["post"], url_path="chiudi-campagna")
    def chiudi_campagna(self, request):
        """Fine campagna: i lead si cancellano.

        Sono dati di terze persone raccolti da un gruppo pubblico e tenuti solo
        finché servono a riempire le stanze. La spec del bot dice «a campagna
        chiusa si cancella il database, punto»: qui la stessa regola vale per
        la copia sul server, altrimenti il principio resta scritto e i dati no.

        Serve ``{"conferma": true}``: cancella davvero, e non c'è cestino.
        """
        if request.data.get("conferma") is not True:
            return Response(
                {"detail": "Serve conferma esplicita: {\"conferma\": true}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        prop = get_request_property(request)
        cancellati, _ = Lead.objects.filter(property=prop).delete()
        return Response({"cancellati": cancellati})


class LeadBulkUpsertView(APIView):
    """POST /api/v1/leads/bulk-upsert/ — il bot deposita il giro appena fatto.

    Idempotente su ``(immobile, post_id)``: lo stesso post ripassato in un giro
    successivo aggiorna i campi del bot e **non tocca** stato, presa in carico
    e note. È ciò che rende il push ritentabile all'infinito senza rovinare il
    lavoro fatto dalle persone nel frattempo.

    ``BasicAuthentication`` è abilitata di proposito, come per l'import dei
    movimenti bancari: il bot è uno script, non ha una sessione da cui prendere
    il CSRF.
    """

    permission_classes = [IsPropertyMember]
    authentication_classes = [SessionAuthentication, BasicAuthentication]

    def post(self, request):
        serializer = LeadBulkUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prop = get_request_property(request)

        creati = aggiornati = 0
        with transaction.atomic():
            for dati in serializer.validated_data["leads"]:
                valori = {c: dati.get(c, "") for c in CAMPI_BOT if c in dati}
                _lead, nuovo = Lead.objects.update_or_create(
                    property=prop,
                    post_id=dati["post_id"],
                    defaults=valori,
                )
                creati += nuovo
                aggiornati += not nuovo
        return Response(
            {"creati": creati, "aggiornati": aggiornati},
            status=status.HTTP_200_OK,
        )
