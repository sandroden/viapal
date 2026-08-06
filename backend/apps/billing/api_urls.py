"""
URL router per le API dell'app billing.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from billing.views import (
    AnnualUtilityCostViewSet,
    BankTransactionBulkImportView,
    BankTransactionViewSet,
    DepositChargeViewSet,
    ExpenseCategoryViewSet,
    ExpenseViewSet,
    ExtraChargeViewSet,
    PropertyUtilityServiceViewSet,
    ReceivableViewSet,
    ReconciliationBulkView,
    ReceivableCommentiView,
    RegistraPagamentoReceivableView,
    RentPaymentViewSet,
    RiepilogoAddebitiInviaView,
    SupplierViewSet,
    TenantCondominioRateViewSet,
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
router.register(r"suppliers", SupplierViewSet, basename="supplier")
router.register(
    r"quote-condominio", TenantCondominioRateViewSet, basename="quota-condominio"
)
router.register(
    r"annual-utility-costs", AnnualUtilityCostViewSet, basename="annual-utility-cost"
)
router.register(
    r"utenze-config", PropertyUtilityServiceViewSet, basename="utenze-config"
)
router.register(r"expenses", ExpenseViewSet, basename="expense")
router.register(r"extra-charges", ExtraChargeViewSet, basename="extra-charge")
router.register(r"deposit-charges", DepositChargeViewSet, basename="deposit-charge")
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
        "receivables/<int:pk>/commenti/",
        ReceivableCommentiView.as_view(),
        name="receivable-commenti",
    ),
    path(
        "riepilogo-addebiti/invia/",
        RiepilogoAddebitiInviaView.as_view(),
        name="riepilogo-addebiti-invia",
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
