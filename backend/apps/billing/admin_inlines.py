"""
AjaxInline definite in billing ma esposte ad admin di altre app (es. properties).
Caricate quando properties.admin importa da qui.
"""
from jmb.jadmin import AjaxInline, ConstrainedModelForm, register_inline

from .models import TenantCondominioRate


class TenantCondominioRateForm(ConstrainedModelForm):
    """Form dell'inline sul contratto: l'immobile non si chiede, lo deduce
    ``TenantCondominioRate.save()`` dal contratto del parent."""

    class Meta:
        model = TenantCondominioRate
        exclude = ("property",)

    hidden_fields = ("contract",)


class TenantCondominioRateAjaxInline(AjaxInline):
    model = TenantCondominioRate
    fk_name = "contract"
    width = 700
    list_display = (
        "valid_from",
        "valid_to",
        "tenant",
        "importo_mensile",
        "note",
        "get_edit_icon_iframe",
        "get_delete_icon_iframe",
    )


register_inline(TenantCondominioRateAjaxInline)
