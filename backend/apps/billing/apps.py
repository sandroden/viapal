from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"
    verbose_name = "Pagamenti e bollette"

    def ready(self):
        # Registra i signal handler che riallineano Receivable.stato quando
        # le BankTransactionAllocation vengono create/modificate/eliminate.
        from billing import signals  # noqa: F401
