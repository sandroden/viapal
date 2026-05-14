"""
ViewSet per l'app properties.
"""
import datetime
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from rest_framework.viewsets import ReadOnlyModelViewSet

from accounts.permissions import IsProprietario, IsInquilinoSelf
from properties.models import Contract, OwnerBankAccount, OwnerProfile, Room, RoomAssignment, TenantProfile
from properties.serializers import (
    ContractSerializer,
    OwnerBankAccountSerializer,
    OwnerProfileSerializer,
    RoomAssignmentSerializer,
    RoomSerializer,
    TenantProfileSerializer,
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

        from billing.models import Receivable

        tenant_ids = list(self.filter_queryset(self.get_queryset()).values_list("id", flat=True))
        if not tenant_ids:
            ctx["saldi_totali"] = {}
            if getattr(self, "_anno_filtro", None) is not None:
                ctx["saldi_anno"] = {}
            return ctx

        base_qs = (
            Receivable.objects
            .filter(assignment__tenant_id__in=tenant_ids)
            .exclude(causale=Receivable.Causale.CAPARRA)
        )

        agg_totale = base_qs.values("assignment__tenant_id").annotate(
            dovuto=Coalesce(Sum("importo_dovuto"), Decimal("0")),
            pagato=Coalesce(Sum("importo_pagato"), Decimal("0")),
        )
        ctx["saldi_totali"] = {
            row["assignment__tenant_id"]: float(row["pagato"] - row["dovuto"])
            for row in agg_totale
        }

        anno = getattr(self, "_anno_filtro", None)
        if anno is not None:
            agg_anno = (
                base_qs.filter(competenza_da__year=anno)
                .values("assignment__tenant_id")
                .annotate(
                    dovuto=Coalesce(Sum("importo_dovuto"), Decimal("0")),
                    pagato=Coalesce(Sum("importo_pagato"), Decimal("0")),
                )
            )
            ctx["saldi_anno"] = {
                row["assignment__tenant_id"]: float(row["pagato"] - row["dovuto"])
                for row in agg_anno
            }
        return ctx


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
