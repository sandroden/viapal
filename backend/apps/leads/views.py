"""API dei lead: una per il bot che li deposita, una per chi li lavora.

L'immobile è quello attivo della richiesta (header ``X-Property-Id``, o unico
accessibile): il bot lo dichiara come qualunque altro client, e la membership
viene verificata lato server come sempre — nessun percorso di autorizzazione
nuovo da mantenere.
"""
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from accounts.permissions import IsPropertyMember, IsPropertyProprietario
from billing.views import BillingPagination
from properties.context import get_request_property

from .models import Lead
from .serializers import (
    CAMPI_BOT,
    LeadBotSerializer,
    LeadBulkUpsertSerializer,
    LeadLavorazioneSerializer,
    LeadManualeSerializer,
    LeadSerializer,
)


class LeadViewSet(ModelViewSet):
    """/api/v1/leads/ — la lista su cui si lavora, in due.

    I lead del bot arrivano dal bulk-upsert e qui si lavorano (PATCH di stato,
    note, foto). Quelli **manuali** — gli altri canali: risposte a un post
    nostro, Subito, Idealista — si creano, si modificano e si cancellano da
    qui, perché non c'è un bot che li possieda.

    Filtri: ``stato`` (uno o più separati da virgola, oppure ``attivi``),
    ``canale``, ``gruppo`` (id del gruppo Facebook), ``preso_da`` (id utente,
    oppure ``me``/``nessuno``).
    """

    permission_classes = [IsPropertyMember]
    pagination_class = BillingPagination
    http_method_names = ["get", "patch", "post", "delete", "head", "options"]

    def get_permissions(self):
        # Cancellare la campagna butta via anche le note e la presa in carico
        # degli altri, e non c'è cestino: è una decisione da proprietario, non
        # da chiunque abbia accesso all'immobile (l'utente del bot compreso,
        # che ha la password in chiaro nel TOML sul portatile).
        if self.action == "chiudi_campagna":
            return [IsPropertyProprietario()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return LeadManualeSerializer
        if self.action == "partial_update":
            # Su un lead del bot i campi descrittivi restano suoi: il PATCH
            # umano tocca solo la lavorazione. Su un manuale, tutto.
            if self.get_object().manuale:
                return LeadManualeSerializer
            return LeadLavorazioneSerializer
        return LeadSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["property"] = get_request_property(self.request)
        return ctx

    def get_queryset(self):
        prop = get_request_property(self.request)
        qs = Lead.objects.filter(property=prop).select_related("preso_da")
        p = self.request.query_params
        if stato := p.get("stato"):
            if stato == "attivi":
                qs = qs.filter(stato__in=Lead.STATI_ATTIVI)
            else:
                qs = qs.filter(stato__in=stato.split(","))
        if canale := p.get("canale"):
            qs = qs.filter(canale=canale)
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

    def create(self, request, *args, **kwargs):
        # Torna il lead intero, come il PATCH: la pagina lo mette in cima
        # alla lista senza rileggerla.
        riga = LeadManualeSerializer(data=request.data, context=self.get_serializer_context())
        riga.is_valid(raise_exception=True)
        lead = riga.save()
        return Response(LeadSerializer(lead).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        # Il PATCH torna il lead intero: la pagina aggiorna la card senza
        # dover rileggere la lista.
        super().partial_update(request, *args, **kwargs)
        istanza = self.get_object()
        return Response(LeadSerializer(istanza).data)

    def destroy(self, request, *args, **kwargs):
        """Solo i manuali: un lead del bot cancellato ricomparirebbe al giro
        dopo con l'upsert, e comunque sparisce con la campagna. Per toglierlo
        di mezzo c'è «scartato»."""
        lead = self.get_object()
        if not lead.manuale:
            return Response(
                {"detail": "I contatti trovati dal bot non si cancellano: si scartano."},
                status=status.HTTP_409_CONFLICT,
            )
        lead.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

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
        """Conteggi per stato e canali presenti — i numeri sui filtri."""
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
        etichette = dict(Lead.Canale.choices)
        canali = [
            {"id": r["canale"], "nome": etichette.get(r["canale"], r["canale"]), "n": r["n"]}
            for r in qs.values("canale").annotate(n=Count("id")).order_by("-n", "canale")
        ]
        return Response(
            {
                "totale": sum(per_stato.values()),
                "attivi": sum(per_stato[s] for s in Lead.STATI_ATTIVI),
                "per_stato": per_stato,
                "gruppi": [{"id": g, "nome": n} for g, n in gruppi],
                "canali": canali,
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
        involucro = LeadBulkUpsertSerializer(data=request.data)
        involucro.is_valid(raise_exception=True)
        prop = get_request_property(request)

        creati = aggiornati = 0
        scartati = []
        with transaction.atomic():
            for grezzo in involucro.validated_data["leads"]:
                riga = LeadBotSerializer(data=grezzo)
                if not riga.is_valid():
                    # Una riga storta non deve bloccare le altre: il bot
                    # ritenta sempre lo stesso blocco, e rifiutarlo tutto
                    # fermerebbe la coda per sempre su quel lead.
                    scartati.append(
                        {"post_id": grezzo.get("post_id", ""), "errori": riga.errors}
                    )
                    continue
                dati = riga.validated_data
                valori = {c: dati.get(c, "") for c in CAMPI_BOT if c in dati}
                _lead, nuovo = Lead.objects.update_or_create(
                    property=prop,
                    post_id=dati["post_id"],
                    defaults=valori,
                )
                creati += nuovo
                aggiornati += not nuovo
        return Response(
            {"creati": creati, "aggiornati": aggiornati, "scartati": scartati},
            status=status.HTTP_200_OK,
        )
