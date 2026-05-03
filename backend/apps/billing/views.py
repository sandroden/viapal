"""
ViewSet per l'app billing.

I tre endpoint storici (rent-payments, utility-charges, extra-charges)
ora si appoggiano al modello unico Receivable filtrando per causale.
"""
import datetime

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from accounts.permissions import IsInquilinoSelf, IsProprietario  # noqa: F401
from billing.models import (
    BankTransaction,
    Expense,
    Receivable,
    StatoPagamento,
    UtilityBill,
    UtilityChargePeriod,
)
from billing.serializers import (
    BankTransactionSerializer,
    ExpenseSerializer,
    ExtraChargeSerializer,
    RentPaymentSerializer,
    UtilityBillSerializer,
    UtilityChargePeriodSerializer,
    UtilityChargeSerializer,
)


class BillingPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 200


def _is_proprietario(user) -> bool:
    return user.is_superuser or user.groups.filter(name="proprietari").exists()


def _is_inquilino(user) -> bool:
    return user.groups.filter(name="inquilini").exists()


class _ReceivableMixin:
    """Comportamenti comuni dei tre ViewSet su Receivable.

    Le sottoclassi specificano `causale` e `serializer_class`.
    """

    causale: str
    pagination_class = BillingPagination

    def get_permissions(self):
        if self.action in ("dichiara_pagato", "conferma_pagato"):
            from rest_framework.permissions import IsAuthenticated
            return [IsAuthenticated()]
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsProprietario()]
        return [IsInquilinoSelf()]

    def _base_queryset(self):
        return Receivable.objects.filter(causale=self.causale).select_related(
            "assignment__tenant__user",
            "assignment__room",
            "incassato_da_owner",
            "bank_account_destinazione",
            "utility_period",
        )

    def get_queryset(self):
        qs = self._base_queryset().order_by("-scadenza")
        if _is_proprietario(self.request.user):
            return qs
        return qs.filter(assignment__tenant__user=self.request.user)

    @action(detail=True, methods=["post"], url_path="dichiara_pagato")
    def dichiara_pagato(self, request, pk=None):
        """Inquilino marca come dichiarato. Solo l'inquilino del receivable."""
        receivable = self.get_object()

        if not _is_proprietario(request.user):
            if receivable.assignment.tenant.user != request.user:
                return Response(
                    {"detail": "Puoi dichiarare solo i tuoi addebiti."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if receivable.stato == StatoPagamento.PAGATO:
            return Response(
                {"detail": "Addebito gia' confermato dai proprietari."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        receivable.stato = StatoPagamento.DICHIARATO
        receivable.data_pagamento = datetime.date.today()
        receivable.importo_pagato = receivable.importo_dovuto
        receivable.save(update_fields=["stato", "data_pagamento", "importo_pagato"])

        return Response(
            self.get_serializer(receivable).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="conferma_pagato")
    def conferma_pagato(self, request, pk=None):
        """Proprietario conferma il pagamento dichiarato."""
        if not _is_proprietario(request.user):
            return Response(
                {"detail": "Solo i proprietari possono confermare un pagamento."},
                status=status.HTTP_403_FORBIDDEN,
            )

        receivable = self.get_object()

        if receivable.stato not in (
            StatoPagamento.DICHIARATO,
            StatoPagamento.ATTESO,
            StatoPagamento.IN_RITARDO,
        ):
            return Response(
                {"detail": f"Impossibile confermare un addebito in stato '{receivable.stato}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        receivable.stato = StatoPagamento.PAGATO
        if not receivable.importo_pagato:
            receivable.importo_pagato = receivable.importo_dovuto
        if not receivable.data_pagamento:
            receivable.data_pagamento = datetime.date.today()
        receivable.save(update_fields=["stato", "importo_pagato", "data_pagamento"])

        return Response(
            self.get_serializer(receivable).data,
            status=status.HTTP_200_OK,
        )


class RentPaymentViewSet(_ReceivableMixin, ModelViewSet):
    """Pagamenti affitto (Receivable causale=affitto)."""

    causale = Receivable.Causale.AFFITTO
    serializer_class = RentPaymentSerializer


class UtilityChargeViewSet(_ReceivableMixin, ModelViewSet):
    """Conguagli utenze (Receivable causale=utenze)."""

    causale = Receivable.Causale.UTENZE
    serializer_class = UtilityChargeSerializer

    def _base_queryset(self):
        return super()._base_queryset().prefetch_related("utility_lines")

    def get_queryset(self):
        qs = self._base_queryset().order_by("-utility_period__periodo_da")
        if _is_proprietario(self.request.user):
            return qs
        return qs.filter(assignment__tenant__user=self.request.user)


class ExtraChargeViewSet(_ReceivableMixin, ModelViewSet):
    """Addebiti extra (Receivable causale=extra)."""

    causale = Receivable.Causale.EXTRA
    serializer_class = ExtraChargeSerializer
    pagination_class = None  # comportamento legacy: lista plain


class UtilityChargePeriodViewSet(ReadOnlyModelViewSet):
    """Periodi di conguaglio utenze. Solo proprietari."""

    serializer_class = UtilityChargePeriodSerializer
    permission_classes = [IsProprietario]
    queryset = UtilityChargePeriod.objects.all().order_by("-periodo_da")


class UtilityBillViewSet(ReadOnlyModelViewSet):
    """Bollette utenze. Solo proprietari."""

    serializer_class = UtilityBillSerializer
    permission_classes = [IsProprietario]
    queryset = UtilityBill.objects.select_related("supplier", "pagata_da_owner").order_by(
        "-data_emissione"
    )


class ExpenseViewSet(ModelViewSet):
    """Spese immobile. Solo proprietari (full CRUD)."""

    serializer_class = ExpenseSerializer
    permission_classes = [IsProprietario]
    queryset = Expense.objects.select_related(
        "category", "supplier", "anticipata_da_owner", "riferimento_quota_owner"
    ).order_by("-data")


class BankTransactionViewSet(ReadOnlyModelViewSet):
    """Transazioni bancarie. Solo proprietari."""

    serializer_class = BankTransactionSerializer
    permission_classes = [IsProprietario]
    pagination_class = BillingPagination
    queryset = (
        BankTransaction.objects
        .select_related("owner_account")
        .prefetch_related("allocations__receivable__assignment__tenant", "allocations__receivable__utility_period")
        .order_by("-data")
    )
