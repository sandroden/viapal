"""
URL router per le API dell'app billing.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from billing.views import (
    BankTransactionViewSet,
    ExpenseCategoryViewSet,
    ExpenseViewSet,
    ExtraChargeViewSet,
    ReceivableViewSet,
    ReconciliationBulkView,
    RegistraPagamentoReceivableView,
    RentPaymentViewSet,
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

urlpatterns = router.urls + [
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
]
