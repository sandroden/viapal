from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"
    verbose_name = "Pagamenti e bollette"

    def ready(self):
        # Registra i signal handler che riallineano Receivable.stato quando
        # le BankTransactionAllocation vengono create/modificate/eliminate.
        from billing import signals  # noqa: F401

        # Aggiunge `viapal/admin/actions_inline.css` alla `class Media` di
        # `JumboModelAdmin` per il layout inline della action bar (azione +
        # campi extra + Vai sulla stessa riga). Scelta di stile locale a
        # viapal: jmb.jadmin upstream non impone CSS opinionati. Iniettato
        # via Media così vale per tutte le changelist senza toccare ogni
        # singolo ModelAdmin.
        from jmb.jadmin import JumboModelAdmin

        existing_js = tuple(getattr(JumboModelAdmin.Media, "js", ()) or ())
        existing_css = dict(getattr(JumboModelAdmin.Media, "css", {}) or {})
        target_css = "viapal/admin/actions_inline.css"
        all_css = tuple(existing_css.get("all", ()))
        if target_css not in all_css:
            existing_css["all"] = all_css + (target_css,)
            JumboModelAdmin.Media = type(
                "Media", (), {"js": existing_js, "css": existing_css},
            )
