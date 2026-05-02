"""
AjaxInline definite in billing ma esposte ad admin di altre app (es. properties).
Caricate quando properties.admin importa da qui.
"""
from jmb.jadmin import AjaxInline, ConstrainedModelForm, register_inline

from .models import TenantCondominioRate


class TenantCondominioRateForm(ConstrainedModelForm):
    class Meta:
        model = TenantCondominioRate
        fields = "__all__"

    hidden_fields = ("contract",)


class TenantCondominioRateAjaxInline(AjaxInline):
    model = TenantCondominioRate
    fk_name = "contract"
    width = 700
    list_display = (
        "valid_from",
        "valid_to",
        "importo_mensile",
        "note",
        "get_edit_icon_iframe",
        "get_delete_icon_iframe",
    )


register_inline(TenantCondominioRateAjaxInline)
