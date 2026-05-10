from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"
    verbose_name = "Pagamenti e bollette"

    def ready(self):
        # Registra i signal handler che riallineano Receivable.stato quando
        # le BankTransactionAllocation vengono create/modificate/eliminate.
        from billing import signals  # noqa: F401

        # Patch JumboModelAdmin.Media perché upstream non include
        # `jmb/js/jmb.jadmin.js` sulla changelist (lo include solo via
        # change_form.html). Senza la JS `jmb.extra_action_fields_init()`
        # non gira sulla lista e i campi del JumboActionForm restano sempre
        # visibili invece di comparire solo per l'azione selezionata.
        # Pattern allineato a thx-admin-tools (ActionClassMixin.Media.js).
        from jmb.jadmin import JumboModelAdmin

        existing_js = tuple(getattr(JumboModelAdmin.Media, "js", ()) or ())
        target = "jmb/js/jmb.jadmin.js"
        if target not in existing_js:
            JumboModelAdmin.Media = type(
                "Media", (), {"js": existing_js + (target,)},
            )
