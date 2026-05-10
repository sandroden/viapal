from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"
    verbose_name = "Pagamenti e bollette"

    def ready(self):
        # Registra i signal handler che riallineano Receivable.stato quando
        # le BankTransactionAllocation vengono create/modificate/eliminate.
        from billing import signals  # noqa: F401

        # Estende `JumboModelAdmin.Media` con:
        #
        # 1) `jmb/js/jmb.jadmin.js`: necessario alla changelist per il
        #    toggle dei campi extra del JumboActionForm via
        #    `jmb.extra_action_fields_init()`. Bug upstream fixato in
        #    `jmb-jadmin` 2.1.11 — quando viapal sarà aggiornato, il check
        #    `if target_js not in existing_js` rende questo passo no-op.
        # 2) `viapal/admin/actions_inline.css`: scelta di stile locale —
        #    layout inline della action bar (azione + campi extra + Vai
        #    sulla stessa riga). Resta in viapal: jmb.jadmin upstream non
        #    impone CSS opinionati.
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
