"""
URL router per le API dell'app billing.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from billing.views import (
    BankTransactionBulkImportView,
    BankTransactionViewSet,
    ExpenseCategoryViewSet,
    ExpenseViewSet,
    ExtraChargeViewSet,
    ReceivableViewSet,
    ReconciliationBulkView,
    RegistraPagamentoReceivableView,
    RentPaymentViewSet,
    UtenzeInquilinoView,
    UtilityBillViewSet,
    UtilityChargeViewSet,
    UtilityChargePeriodViewSet,
)

router = DefaultRouter()
router.register(r"rent-payments", RentPaymentViewSet, basename="rent-payment")
router.register(r"utility-charges", UtilityChargeViewSet, basename="utility-charge")
router.register(r"utility-periods", UtilityChargePeriodViewSet, basename="utility-charge-period")
router.register(r"utility-bills", UtilityBillViewSet, basename="utility-bill")
router.register(r"expense-categories", ExpenseCategoryViewSet, basename="expense-category")
router.register(r"expenses", ExpenseViewSet, basename="expense")
router.register(r"extra-charges", ExtraChargeViewSet, basename="extra-charge")
router.register(r"bank-transactions", BankTransactionViewSet, basename="bank-transaction")
router.register(r"receivables", ReceivableViewSet, basename="receivable")

urlpatterns = [
    # Prima del router: altrimenti la regex detail `bank-transactions/<pk>/`
    # cattura "bulk-import" come pk.
    path(
        "bank-transactions/bulk-import/",
        BankTransactionBulkImportView.as_view(),
        name="bank-transaction-bulk-import",
    ),
] + router.urls + [
    path(
        "reconciliations/",
        ReconciliationBulkView.as_view(),
        name="reconciliations-bulk",
    ),
    path(
        "receivables/<int:pk>/registra-pagamento/",
        RegistraPagamentoReceivableView.as_view(),
        name="receivable-registra-pagamento",
    ),
    path(
        "utenze-inquilino/",
        UtenzeInquilinoView.as_view(),
        name="utenze-inquilino-list",
    ),
    path(
        "utenze-inquilino/<int:period_id>/",
        UtenzeInquilinoView.as_view(),
        name="utenze-inquilino-detail",
    ),
]
