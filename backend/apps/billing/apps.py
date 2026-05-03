from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"
    verbose_name = "Pagamenti e bollette"

    def ready(self):
        # Patch jmb.filters per Django >= 5.1 (vedi core/_jmb_filters_compat.py)
        from core._jmb_filters_compat import install_filter_params_patch
        install_filter_params_patch()
