"""
View admin custom per chiamare il servizio genera_settlement da browser.
"""
import datetime

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.urls import reverse

from accounting.models import OwnerSettlement
from accounting.services.settlement import (
    SettlementGiaEsistente,
    genera_settlement,
)
from properties.models import Property


class GeneraSettlementForm(forms.Form):
    property = forms.ModelChoiceField(
        queryset=Property.objects.all().order_by("nome"),
        label="Immobile",
    )
    anno = forms.IntegerField(
        min_value=2020,
        max_value=2099,
        label="Anno da chiudere",
        help_text="Periodo: 1 gennaio – 31 dicembre dell'anno indicato.",
    )
    descrizione = forms.CharField(
        max_length=300,
        required=False,
        label="Descrizione (opzionale)",
    )
    reset = forms.BooleanField(
        required=False,
        label="Reset",
        help_text="Cancella le voci esistenti del settlement e ricrea (idempotente).",
    )
    dry_run = forms.BooleanField(
        required=False,
        label="Dry-run (solo simulazione)",
        help_text="Esegue tutto in transazione e fa rollback alla fine.",
    )


@staff_member_required
def genera_settlement_view(request):
    """Form admin che chiama accounting.services.settlement.genera_settlement."""
    risultato = None
    if request.method == "POST":
        form = GeneraSettlementForm(request.POST)
        if form.is_valid():
            anno = form.cleaned_data["anno"]
            try:
                settlement = genera_settlement(
                    form.cleaned_data["property"],
                    datetime.date(anno, 1, 1),
                    datetime.date(anno, 12, 31),
                    descrizione=form.cleaned_data["descrizione"] or None,
                    reset=form.cleaned_data["reset"],
                    dry_run=form.cleaned_data["dry_run"],
                )
                if form.cleaned_data["dry_run"]:
                    messages.info(
                        request,
                        f"DRY-RUN OK per anno {anno}. Nessuna scrittura effettuata. "
                        f"Snapshot calcolato: {settlement.snapshot}",
                    )
                    risultato = {"snapshot": settlement.snapshot, "anno": anno}
                else:
                    messages.success(
                        request,
                        f"Settlement {anno} generato (id {settlement.pk}).",
                    )
                    return redirect(
                        reverse(
                            "admin:accounting_ownersettlement_change",
                            args=[settlement.pk],
                        ),
                    )
            except SettlementGiaEsistente as exc:
                form.add_error(None, str(exc))
            except ValueError as exc:
                form.add_error(None, str(exc))
    else:
        form = GeneraSettlementForm()

    return render(
        request,
        "admin/accounting/genera_settlement.html",
        {
            **admin.site.each_context(request),
            "form": form,
            "risultato": risultato,
            "title": "Genera settlement annuale",
            "opts": OwnerSettlement._meta,
            "has_view_permission": True,
        },
    )
