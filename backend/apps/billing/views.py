"""
ViewSet per l'app billing.
"""
import datetime

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from accounts.permissions import IsInquilinoSelf, IsProprietario, IsProprietarioOrReadOnly
from billing.models import (
    BankTransaction,
    Expense,
    ExtraCharge,
    RentPayment,
    StatoPagamento,
    UtilityBill,
    UtilityCharge,
    UtilityChargePeriod,
)
from billing.serializers import (
    BankTransactionSerializer,
    ExpenseSerializer,
    ExtraChargeSerializer,
    RentPaymentSerializer,
    UtilityBillSerializer,
    UtilityChargeSerializer,
    UtilityChargePeriodSerializer,
)


class BillingPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 200


def _is_proprietario(user) -> bool:
    return user.is_superuser or user.groups.filter(name="proprietari").exists()


def _is_inquilino(user) -> bool:
    return user.groups.filter(name="inquilini").exists()


class RentPaymentViewSet(ModelViewSet):
    """
    Pagamenti affitto.
    - GET: proprietari = tutti; inquilini = solo i propri.
    - POST/PATCH: solo proprietari.
    - action dichiara_pagato: inquilino marca come dichiarato.
    - action conferma_pagato: proprietario conferma come pagato.
    """

    serializer_class = RentPaymentSerializer
    pagination_class = BillingPagination

    def get_permissions(self):
        if self.action in ("dichiara_pagato", "conferma_pagato"):
            from rest_framework.permissions import IsAuthenticated
            return [IsAuthenticated()]
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsProprietario()]
        return [IsInquilinoSelf()]

    def get_queryset(self):
        user = self.request.user
        qs = RentPayment.objects.select_related(
            "assignment__tenant__user",
            "assignment__room",
            "incassato_da_owner",
            "bank_account_destinazione",
        ).order_by("-scadenza")
        if _is_proprietario(user):
            return qs
        return qs.filter(assignment__tenant__user=user)

    @action(detail=True, methods=["post"], url_path="dichiara_pagato")
    def dichiara_pagato(self, request, pk=None):
        """
        Inquilino dichiara di aver pagato.
        Imposta stato='dichiarato', data_pagamento=oggi, importo_pagato=importo_dovuto.
        Solo l'inquilino associato al pagamento può eseguire questa azione.
        """
        payment = self.get_object()

        # Verifica che sia l'inquilino del pagamento
        if not _is_proprietario(request.user):
            if payment.assignment.tenant.user != request.user:
                return Response(
                    {"detail": "Puoi dichiarare solo i tuoi pagamenti."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if payment.stato == StatoPagamento.PAGATO:
            return Response(
                {"detail": "Pagamento gia' confermato dai proprietari."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment.stato = StatoPagamento.DICHIARATO
        payment.data_pagamento = datetime.date.today()
        payment.importo_pagato = payment.importo_dovuto
        payment.save(update_fields=["stato", "data_pagamento", "importo_pagato"])

        return Response(
            RentPaymentSerializer(payment).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="conferma_pagato")
    def conferma_pagato(self, request, pk=None):
        """
        Proprietario conferma il pagamento dichiarato dall'inquilino.
        Imposta stato='pagato'.
        """
        if not _is_proprietario(request.user):
            return Response(
                {"detail": "Solo i proprietari possono confermare un pagamento."},
                status=status.HTTP_403_FORBIDDEN,
            )

        payment = self.get_object()

        if payment.stato not in (StatoPagamento.DICHIARATO, StatoPagamento.ATTESO,
                                  StatoPagamento.IN_RITARDO):
            return Response(
                {"detail": f"Impossibile confermare un pagamento in stato '{payment.stato}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment.stato = StatoPagamento.PAGATO
        if not payment.importo_pagato:
            payment.importo_pagato = payment.importo_dovuto
        if not payment.data_pagamento:
            payment.data_pagamento = datetime.date.today()
        payment.save(update_fields=["stato", "importo_pagato", "data_pagamento"])

        return Response(
            RentPaymentSerializer(payment).data,
            status=status.HTTP_200_OK,
        )


class UtilityChargeViewSet(ModelViewSet):
    """
    Conguagli utenze per inquilino.
    - GET: proprietari = tutti; inquilini = solo i propri.
    - POST/PATCH: solo proprietari.
    - action dichiara_pagato / conferma_pagato analogue a RentPayment.
    """

    serializer_class = UtilityChargeSerializer
    pagination_class = BillingPagination

    def get_permissions(self):
        if self.action in ("dichiara_pagato", "conferma_pagato"):
            from rest_framework.permissions import IsAuthenticated
            return [IsAuthenticated()]
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsProprietario()]
        return [IsInquilinoSelf()]

    def get_queryset(self):
        user = self.request.user
        qs = UtilityCharge.objects.select_related(
            "period",
            "assignment__tenant__user",
            "assignment__room",
        ).prefetch_related("lines").order_by("-period__periodo_da")
        if _is_proprietario(user):
            return qs
        return qs.filter(assignment__tenant__user=user)

    @action(detail=True, methods=["post"], url_path="dichiara_pagato")
    def dichiara_pagato(self, request, pk=None):
        """Inquilino dichiara di aver pagato il conguaglio."""
        charge = self.get_object()

        if not _is_proprietario(request.user):
            if charge.assignment.tenant.user != request.user:
                return Response(
                    {"detail": "Puoi dichiarare solo i tuoi conguagli."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if charge.stato == StatoPagamento.PAGATO:
            return Response(
                {"detail": "Conguaglio gia' confermato dai proprietari."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        charge.stato = StatoPagamento.DICHIARATO
        charge.data_pagamento = datetime.date.today()
        charge.importo_pagato = charge.importo_totale
        charge.save(update_fields=["stato", "data_pagamento", "importo_pagato"])

        return Response(
            UtilityChargeSerializer(charge).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="conferma_pagato")
    def conferma_pagato(self, request, pk=None):
        """Proprietario conferma il conguaglio dichiarato."""
        if not _is_proprietario(request.user):
            return Response(
                {"detail": "Solo i proprietari possono confermare un conguaglio."},
                status=status.HTTP_403_FORBIDDEN,
            )

        charge = self.get_object()

        if charge.stato not in (StatoPagamento.DICHIARATO, StatoPagamento.ATTESO,
                                 StatoPagamento.IN_RITARDO):
            return Response(
                {"detail": f"Impossibile confermare un conguaglio in stato '{charge.stato}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        charge.stato = StatoPagamento.PAGATO
        if not charge.importo_pagato:
            charge.importo_pagato = charge.importo_totale
        if not charge.data_pagamento:
            charge.data_pagamento = datetime.date.today()
        charge.save(update_fields=["stato", "importo_pagato", "data_pagamento"])

        return Response(
            UtilityChargeSerializer(charge).data,
            status=status.HTTP_200_OK,
        )


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


class ExtraChargeViewSet(ModelViewSet):
    """
    Addebiti extra.
    - GET: proprietari = tutti; inquilini = solo i propri.
    - POST/PATCH/DELETE: solo proprietari.
    """

    serializer_class = ExtraChargeSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsProprietario()]
        return [IsInquilinoSelf()]

    def get_queryset(self):
        user = self.request.user
        qs = ExtraCharge.objects.select_related(
            "assignment__tenant__user", "assignment__room"
        ).order_by("-scadenza")
        if _is_proprietario(user):
            return qs
        return qs.filter(assignment__tenant__user=user)


class BankTransactionViewSet(ReadOnlyModelViewSet):
    """Transazioni bancarie. Solo proprietari."""

    serializer_class = BankTransactionSerializer
    permission_classes = [IsProprietario]
    pagination_class = BillingPagination
    queryset = BankTransaction.objects.select_related("owner_account").order_by("-data")
