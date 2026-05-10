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
        existing_css = dict(getattr(JumboModelAdmin.Media, "css", {}) or {})
        target_js = "jmb/js/jmb.jadmin.js"
        target_css = "viapal/admin/actions_inline.css"

        new_js = existing_js if target_js in existing_js else existing_js + (target_js,)
        all_css = tuple(existing_css.get("all", ()))
        if target_css not in all_css:
            existing_css["all"] = all_css + (target_css,)

        if new_js != existing_js or "all" in existing_css:
            JumboModelAdmin.Media = type(
                "Media", (), {"js": new_js, "css": existing_css},
            )
