"""
ViewSet per l'app properties.
"""
import datetime
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.generics import RetrieveAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from accounts.permissions import IsProprietario, IsInquilinoSelf
from properties.models import (
    Contract,
    GalleryImage,
    OwnerBankAccount,
    OwnerProfile,
    Property,
    Room,
    RoomAssignment,
    TenantDocument,
    TenantProfile,
)
from properties.serializers import (
    ContractSerializer,
    GalleryImageSerializer,
    OwnerBankAccountSerializer,
    OwnerProfileSerializer,
    PropertySerializer,
    PublicGallerySerializer,
    RoomAssignmentSerializer,
    RoomSerializer,
    TenantDocumentSerializer,
    TenantProfileSerializer,
    TenantSelfUpdateSerializer,
)


def _is_proprietario(user):
    return bool(
        user
        and user.is_authenticated
        and (user.groups.filter(name="proprietari").exists() or user.is_superuser)
    )


class OwnerProfileViewSet(ReadOnlyModelViewSet):
    """Lista i 3 profili proprietario. Accesso solo ai proprietari."""

    serializer_class = OwnerProfileSerializer
    permission_classes = [IsProprietario]
    queryset = OwnerProfile.objects.select_related("user").order_by("nominativo")


class TenantProfileViewSet(ReadOnlyModelViewSet):
    """
    Profili inquilini.
    - Proprietari: vedono tutti. Per default solo gli attivi (con assignment in
      corso oggi); query param ``?solo_attivi=0`` per includere anche gli storici.
      In alternativa, ``?anno=YYYY`` filtra gli inquilini con almeno un
      assignment che si sovrappone all'anno indicato (ha la precedenza su
      ``solo_attivi``).
    - Inquilini: vedono solo il proprio.
    """

    serializer_class = TenantProfileSerializer

    def get_permissions(self):
        return [IsInquilinoSelf()]

    def get_queryset(self):
        user = self.request.user
        qs = TenantProfile.objects.select_related("user").order_by("nominativo")
        is_proprietario = (
            user.groups.filter(name="proprietari").exists() or user.is_superuser
        )
        if not is_proprietario:
            return qs.filter(user=user)

        anno_param = self.request.query_params.get("anno")
        if anno_param:
            try:
                anno = int(anno_param)
            except (TypeError, ValueError):
                anno = None
            if anno is not None:
                self._anno_filtro = anno
                inizio = datetime.date(anno, 1, 1)
                fine = datetime.date(anno, 12, 31)
                return qs.filter(
                    assignments__valid_from__lte=fine,
                ).filter(
                    Q(assignments__valid_to__isnull=True)
                    | Q(assignments__valid_to__gt=inizio)
                ).distinct()

        solo_attivi = self.request.query_params.get("solo_attivi", "1")
        if solo_attivi in ("0", "false", "False"):
            return qs

        oggi = datetime.date.today()
        return qs.filter(
            assignments__valid_from__lte=oggi,
        ).filter(
            Q(assignments__valid_to__isnull=True)
            | Q(assignments__valid_to__gt=oggi)
        ).distinct()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        user = self.request.user
        is_proprietario = (
            user.is_authenticated
            and (user.groups.filter(name="proprietari").exists() or user.is_superuser)
        )
        if not is_proprietario:
            return ctx

        from billing.dashboard_views import _resti_per_anno, _sbilancio_progressivo
        from billing.models import Receivable

        anno_filtro = getattr(self, "_anno_filtro", None)
        tenants = list(self.filter_queryset(self.get_queryset()))
        if not tenants:
            ctx["saldi_totali"] = {}
            if anno_filtro is not None:
                ctx["saldi_anno"] = {}
            return ctx

        tenant_ids = [t.id for t in tenants]
        base_qs = (
            Receivable.objects
            .filter(assignment__tenant_id__in=tenant_ids)
            .exclude(causale=Receivable.Causale.DEPOSITO)
        )

        # Dovuto/pagato per (tenant, anno di competenza) in un colpo solo.
        dovuto_pagato: dict[int, dict[int, list]] = {}
        for row in base_qs.values(
            "assignment__tenant_id", "competenza_da__year"
        ).annotate(
            d=Coalesce(Sum("importo_dovuto"), Decimal("0")),
            p=Coalesce(Sum("importo_pagato"), Decimal("0")),
        ):
            t = row["assignment__tenant_id"]
            y = row["competenza_da__year"] or 0
            dovuto_pagato.setdefault(t, {})[y] = [row["d"], row["p"]]

        # Sbilancio reale (= pagato − dovuto + resti dei bonifici) per ogni
        # inquilino. Coerente con TenantSituazioneView: ``saldo_totale`` è il
        # progressivo cumulato fino all'anno selezionato (non conosce il
        # futuro); senza filtro anno è il totale complessivo.
        saldi_totali: dict[int, float] = {}
        saldi_anno: dict[int, float] = {}
        for t in tenants:
            per_anno, totale = _sbilancio_progressivo(
                dovuto_pagato.get(t.id, {}), _resti_per_anno(t)
            )
            if anno_filtro is not None:
                prog = 0.0
                for x in per_anno:
                    if x["anno"] <= anno_filtro:
                        prog = x["saldo_progressivo"]
                saldi_totali[t.id] = prog
                ent = next((x for x in per_anno if x["anno"] == anno_filtro), None)
                saldi_anno[t.id] = ent["saldo_anno"] if ent else 0.0
            else:
                saldi_totali[t.id] = totale["sbilancio_reale"]

        ctx["saldi_totali"] = saldi_totali
        if anno_filtro is not None:
            ctx["saldi_anno"] = saldi_anno
        return ctx

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """Profilo dell'inquilino loggato, con aggiornamento self-service.

        GET restituisce i propri dati; PATCH consente di modificare solo i
        campi concessi (nominativo, telefono, codice fiscale) tramite
        ``TenantSelfUpdateSerializer``.
        """
        tenant = getattr(request.user, "tenant_profile", None)
        if tenant is None:
            return Response(
                {"detail": "Nessun profilo inquilino associato all'utente."},
                status=404,
            )
        if request.method == "PATCH":
            serializer = TenantSelfUpdateSerializer(
                tenant, data=request.data, partial=True, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            serializer = TenantSelfUpdateSerializer(
                tenant, context={"request": request}
            )
        return Response(serializer.data)


class TenantDocumentViewSet(ModelViewSet):
    """
    Documenti degli inquilini (CI, CF, passaporto, permesso, contratto lavoro).
    - Inquilini: vedono, caricano ed eliminano solo i propri (il ``tenant`` è
      forzato al proprio profilo, indipendentemente dal payload).
    - Proprietari: vedono tutti, filtrabili con ``?tenant=<id>``; in scrittura
      devono indicare il ``tenant`` nel payload.
    """

    serializer_class = TenantDocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        return [IsInquilinoSelf()]

    def get_queryset(self):
        user = self.request.user
        qs = TenantDocument.objects.select_related("tenant", "tenant__user")
        if not _is_proprietario(user):
            return qs.filter(tenant__user=user)
        tenant_id = self.request.query_params.get("tenant")
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if _is_proprietario(user):
            tenant = serializer.validated_data.get("tenant")
            if tenant is None:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"tenant": "Campo obbligatorio per i proprietari."})
        else:
            tenant = getattr(user, "tenant_profile", None)
            if tenant is None:
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied("Nessun profilo inquilino associato all'utente.")
        serializer.save(tenant=tenant, caricato_da=user)


class RoomViewSet(ModelViewSet):
    """
    Stanze.
    - Proprietari: tutte; possono aggiornare i campi galleria (PATCH).
    - Inquilini: solo le stanze con assignment attivo per sé (sola lettura).
    """

    serializer_class = RoomSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.request.method in ("PATCH",):
            return [IsProprietario()]
        return [IsInquilinoSelf()]

    def get_queryset(self):
        user = self.request.user
        today = datetime.date.today()
        if user.groups.filter(name="proprietari").exists() or user.is_superuser:
            return Room.objects.all()
        # Stanze dove l'inquilino ha un assignment attivo oggi
        return Room.objects.filter(
            assignments__tenant__user=user,
            assignments__valid_from__lte=today,
        ).filter(
            Q(assignments__valid_to__isnull=True) | Q(assignments__valid_to__gt=today)
        ).distinct()


class RoomAssignmentViewSet(ReadOnlyModelViewSet):
    """
    Assegnazioni stanza.
    - Proprietari: tutte.
    - Inquilini: solo le proprie.
    """

    serializer_class = RoomAssignmentSerializer

    def get_permissions(self):
        return [IsInquilinoSelf()]

    def get_queryset(self):
        user = self.request.user
        qs = RoomAssignment.objects.select_related("room", "tenant", "tenant__user").order_by(
            "-valid_from"
        )
        if user.groups.filter(name="proprietari").exists() or user.is_superuser:
            return qs
        return qs.filter(tenant__user=user)


class ContractViewSet(ReadOnlyModelViewSet):
    """Contratto unico di locazione. Accesso solo ai proprietari."""

    serializer_class = ContractSerializer
    permission_classes = [IsProprietario]
    queryset = Contract.objects.all()


class OwnerBankAccountViewSet(ReadOnlyModelViewSet):
    """Conti bancari dei proprietari. Accesso solo ai proprietari."""

    serializer_class = OwnerBankAccountSerializer
    permission_classes = [IsProprietario]
    queryset = OwnerBankAccount.objects.select_related("owner").order_by(
        "owner__nominativo", "ordinamento"
    )


class PropertyViewSet(ModelViewSet):
    """Immobili. Accesso e scrittura riservati ai proprietari.

    Consente il PATCH dei campi della galleria pubblica: testi
    (``testi_pubblici``), toggle ``pubblica`` e immagini singleton
    (hero/planimetria/mappa).
    """

    serializer_class = PropertySerializer
    permission_classes = [IsProprietario]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "patch", "head", "options"]
    queryset = Property.objects.all()


class GalleryImageViewSet(ModelViewSet):
    """Foto della galleria pubblica (spazi comuni e stanze).

    Scrittura riservata ai proprietari. L'upload accetta sia file (``q-file``,
    drag&drop) sia blob incollati (Ctrl-V): è sempre una POST multipart.
    """

    serializer_class = GalleryImageSerializer
    permission_classes = [IsProprietario]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        qs = GalleryImage.objects.select_related("property", "room")
        property_id = self.request.query_params.get("property")
        if property_id:
            qs = qs.filter(property_id=property_id)
        room_id = self.request.query_params.get("room")
        if room_id:
            qs = qs.filter(room_id=room_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(caricato_da=self.request.user)


class PublicGalleryView(RetrieveAPIView):
    """Payload pubblico della galleria di un immobile, senza autenticazione.

    Unica view AllowAny del progetto: espone solo i campi pubblici tramite
    ``PublicGallerySerializer``. 404 se l'immobile non è pubblicato.
    """

    serializer_class = PublicGallerySerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    lookup_field = "slug"

    def get_queryset(self):
        return Property.objects.filter(pubblica=True).prefetch_related(
            "rooms", "rooms__gallery_images", "gallery_images"
        )
