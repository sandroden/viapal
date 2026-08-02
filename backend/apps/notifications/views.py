"""
ViewSet per l'app notifications.
Ogni utente vede e gestisce solo le proprie notifiche/subscription.
"""
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from accounts.permissions import IsPropertyMember
from billing.views import BillingPagination
from properties.context import get_request_property
from properties.views import ProtectedDestroyMixin
from notifications.models import (
    MessageTemplate,
    Notification,
    PushSubscription,
    ReminderRule,
)
from notifications.push import invia_push, push_configurato
from notifications.serializers import (
    ComunicazioneDettaglioSerializer,
    ComunicazioneSerializer,
    MessageTemplateSerializer,
    NotificationSerializer,
    PushSubscriptionSerializer,
    ReminderRuleSerializer,
)


class NotificationViewSet(ReadOnlyModelViewSet):
    """
    Notifiche: l'utente vede solo le proprie.
    """

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by("-created_at")


class ComunicazioniViewSet(ReadOnlyModelViewSet):
    """GET /api/v1/comunicazioni/ — registro delle comunicazioni agli inquilini.

    Vista **di gestione**, distinta da ``NotificationViewSet`` che resta la
    vista personale (``user=request.user``): qui un membro dell'immobile legge
    cosa è stato mandato ai *suoi* inquilini.

    Il filtro passa dal join ``user__tenant_profile__property``, che esclude
    automaticamente le comunicazioni verso proprietari e gestori (note sugli
    addebiti, inviti membro): non c'entrano con "cosa ho inviato agli
    inquilini".

    Filtri (query string): ``tenant``, ``da``/``a`` (YYYY-MM-DD su
    ``created_at``), ``canale``, ``tipo`` (= ``codice``), ``esito``
    (``inviato``/``errore``), ``attivi`` (solo inquilini che occupano una
    stanza *oggi*).

    ``attivi`` guarda l'inquilino **adesso**, non a quando la comunicazione
    partì: un'email mandata a chi allora era in casa sparisce dall'elenco
    quando quello se ne va. È voluto — serve a rispondere a "cosa ho scritto
    alla gente che ho in casa", non a ricostruire la storia.

    Nota: gli avvisi utenze scrivono due righe per lo stesso evento (una push
    e una email). Non si deduplica lato server: la colonna canale le
    distingue e il filtro le separa.
    """

    permission_classes = [IsPropertyMember]
    # Stessa paginazione delle liste billing: a regime questa tabella cresce
    # di N righe al mese e una lista non paginata prima o poi tronca in
    # silenzio (già successo in riconciliazione).
    pagination_class = BillingPagination

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ComunicazioneDettaglioSerializer
        return ComunicazioneSerializer

    def get_queryset(self):
        prop = get_request_property(self.request)
        qs = (
            Notification.objects.filter(user__tenant_profile__property=prop)
            .select_related("user__tenant_profile")
            .order_by("-created_at")
        )

        params = self.request.query_params

        tenant = params.get("tenant")
        if tenant:
            qs = qs.filter(user__tenant_profile__id=tenant)

        if params.get("attivi") in ("1", "true", "True"):
            from properties.models import TenantProfile

            qs = qs.filter(
                user__tenant_profile__in=TenantProfile.objects.attivi(
                    property=prop
                )
            )

        da = params.get("da")
        if da:
            qs = qs.filter(created_at__date__gte=da)
        a = params.get("a")
        if a:
            qs = qs.filter(created_at__date__lte=a)

        canale = params.get("canale")
        if canale:
            qs = qs.filter(canale=canale)

        tipo = params.get("tipo")
        if tipo:
            qs = qs.filter(codice=tipo)

        esito = params.get("esito")
        if esito == "errore":
            qs = qs.exclude(errore="")
        elif esito == "inviato":
            qs = qs.filter(errore="", inviata_at__isnull=False)

        return qs


class MessageTemplateViewSet(ProtectedDestroyMixin, ModelViewSet):
    """Template messaggi dell'immobile attivo (CRUD per i membri operativi;
    la property è assegnata dal server)."""

    serializer_class = MessageTemplateSerializer
    permission_classes = [IsPropertyMember]
    queryset = MessageTemplate.objects.all().order_by("codice")

    def get_queryset(self):
        return super().get_queryset().filter(
            property=get_request_property(self.request)
        )

    def _valida_codice_univoco(self, serializer):
        """Anticipa il vincolo unique (property, codice) con un 400 chiaro."""
        from rest_framework.exceptions import ValidationError

        codice = serializer.validated_data.get("codice")
        if codice is None:
            return
        qs = MessageTemplate.objects.filter(
            property=get_request_property(self.request), codice=codice
        )
        if serializer.instance is not None:
            qs = qs.exclude(pk=serializer.instance.pk)
        if qs.exists():
            raise ValidationError(
                {"codice": "Esiste già un template con questo codice."}
            )

    def perform_create(self, serializer):
        self._valida_codice_univoco(serializer)
        serializer.save(property=get_request_property(self.request))

    def perform_update(self, serializer):
        self._valida_codice_univoco(serializer)
        serializer.save()


class ReminderRuleViewSet(ProtectedDestroyMixin, ModelViewSet):
    """Regole di sollecito dell'immobile attivo (CRUD per i membri
    operativi; la property è assegnata dal server)."""

    serializer_class = ReminderRuleSerializer
    permission_classes = [IsPropertyMember]
    queryset = ReminderRule.objects.select_related("template").order_by(
        "applicabile_a", "giorni_offset"
    )

    def get_queryset(self):
        return super().get_queryset().filter(
            property=get_request_property(self.request)
        )

    def _valida_template(self, serializer):
        """Il template collegato deve appartenere all'immobile attivo."""
        from rest_framework.exceptions import ValidationError

        template = serializer.validated_data.get("template")
        if (
            template is not None
            and template.property_id != get_request_property(self.request).pk
        ):
            raise ValidationError(
                {"template": "Il template appartiene a un altro immobile."}
            )

    def perform_create(self, serializer):
        self._valida_template(serializer)
        serializer.save(property=get_request_property(self.request))

    def perform_update(self, serializer):
        self._valida_template(serializer)
        serializer.save()


class PushSubscriptionViewSet(ModelViewSet):
    """
    Subscription push: CRUD limitato all'utente corrente.
    """

    serializer_class = PushSubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PushSubscription.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """Upsert per ``endpoint``: il browser può ri-sottoscrivere lo stesso
        device (stesso endpoint) dopo un logout/login, anche con un altro
        utente — l'endpoint è unique, quindi si aggiorna invece di dare 400.
        """
        endpoint = request.data.get("endpoint")
        esistente = (
            PushSubscription.objects.filter(endpoint=endpoint).first()
            if endpoint
            else None
        )
        if esistente is None:
            return super().create(request, *args, **kwargs)
        serializer = self.get_serializer(esistente, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="vapid-public-key")
    def vapid_public_key(self, request):
        """Chiave pubblica VAPID per ``pushManager.subscribe`` nel frontend.

        ``abilitato=False`` (chiavi non configurate) → il frontend nasconde
        il toggle notifiche.
        """
        return Response(
            {
                "abilitato": push_configurato(),
                "public_key": settings.VAPID_PUBLIC_KEY,
            }
        )

    @action(detail=False, methods=["post"], url_path="test")
    def test(self, request):
        """Invia una push di prova ai device dell'utente corrente."""
        esito = invia_push(
            request.user,
            titolo="Viapal — notifica di prova",
            corpo="Le notifiche push funzionano su questo dispositivo. 🎉",
            url="/",
            salva_notification=False,
        )
        return Response(esito)
