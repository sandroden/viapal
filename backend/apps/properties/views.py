"""
ViewSet per l'app properties.
"""
import datetime
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from accounts.permissions import IsInquilinoSelf, IsPropertyMember
from properties.context import get_request_property
from properties.models import (
    Contract,
    OwnerBankAccount,
    OwnerProfile,
    Room,
    RoomAssignment,
    TenantDocument,
    TenantProfile,
)
from properties.serializers import (
    ContractSerializer,
    OwnerBankAccountSerializer,
    OwnerProfileSerializer,
    RoomAssignmentSerializer,
    RoomSerializer,
    TenantDocumentSerializer,
    TenantProfileSerializer,
    TenantSelfUpdateSerializer,
)


def _is_gestione(user):
    """True se l'utente sta dal lato gestione (membro di almeno un immobile)."""
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.property_memberships.exists())
    )


class OwnerProfileViewSet(ReadOnlyModelViewSet):
    """Profili proprietario dei membri dell'immobile attivo."""

    serializer_class = OwnerProfileSerializer
    permission_classes = [IsPropertyMember]
    queryset = OwnerProfile.objects.select_related("user").order_by("nominativo")

    def get_queryset(self):
        prop = get_request_property(self.request)
        return super().get_queryset().filter(
            user__property_memberships__property=prop
        ).distinct()


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
        if not _is_gestione(user):
            return qs.filter(user=user)
        qs = qs.filter(property=get_request_property(self.request))

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
        if not (user.is_authenticated and _is_gestione(user)):
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
        if not _is_gestione(user):
            return qs.filter(tenant__user=user)
        qs = qs.filter(tenant__property=get_request_property(self.request))
        tenant_id = self.request.query_params.get("tenant")
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if _is_gestione(user):
            tenant = serializer.validated_data.get("tenant")
            if tenant is None:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"tenant": "Campo obbligatorio per i proprietari."})
            if tenant.property_id != get_request_property(self.request).pk:
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied("L'inquilino appartiene a un altro immobile.")
        else:
            tenant = getattr(user, "tenant_profile", None)
            if tenant is None:
                from rest_framework.exceptions import PermissionDenied

                raise PermissionDenied("Nessun profilo inquilino associato all'utente.")
        serializer.save(tenant=tenant, caricato_da=user)


class RoomViewSet(ReadOnlyModelViewSet):
    """
    Stanze.
    - Proprietari: tutte.
    - Inquilini: solo le stanze con assignment attivo per sé.
    """

    serializer_class = RoomSerializer

    def get_permissions(self):
        return [IsInquilinoSelf()]

    def get_queryset(self):
        user = self.request.user
        today = datetime.date.today()
        if _is_gestione(user):
            return Room.objects.filter(property=get_request_property(self.request))
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
        if _is_gestione(user):
            return qs.filter(room__property=get_request_property(self.request))
        return qs.filter(tenant__user=user)


class ContractViewSet(ReadOnlyModelViewSet):
    """Contratti di locazione dell'immobile attivo."""

    serializer_class = ContractSerializer
    permission_classes = [IsPropertyMember]
    queryset = Contract.objects.all()

    def get_queryset(self):
        return super().get_queryset().filter(
            property=get_request_property(self.request)
        )


class OwnerBankAccountViewSet(ReadOnlyModelViewSet):
    """Conti bancari dei membri dell'immobile attivo.

    Visibilità fra co-membri (decisione 2026-07-11): chi condivide un
    immobile col titolare vede i suoi conti.
    """

    serializer_class = OwnerBankAccountSerializer
    permission_classes = [IsPropertyMember]
    queryset = OwnerBankAccount.objects.select_related("owner").order_by(
        "owner__nominativo", "ordinamento"
    )

    def get_queryset(self):
        prop = get_request_property(self.request)
        return super().get_queryset().filter(
            owner__user__property_memberships__property=prop
        ).distinct()
