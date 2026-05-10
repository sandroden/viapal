"""
View admin custom dell'app billing.
"""
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from billing.calc.rent import genera_pagamenti_mese
from billing.models import Receivable
from properties.models import TenantProfile


class GeneraReceivableAffittoForm(forms.Form):
    """Form della pagina admin standalone per generare i Receivable affitto.

    Stesso payload dell'action ``rigenera_receivables_affitto`` su
    ``UtilityChargePeriod`` ma senza dover selezionare un period: l'utente
    sceglie direttamente anno/mese.
    """

    MESI_CHOICES = (
        (1, "Gennaio"), (2, "Febbraio"), (3, "Marzo"), (4, "Aprile"),
        (5, "Maggio"), (6, "Giugno"), (7, "Luglio"), (8, "Agosto"),
        (9, "Settembre"), (10, "Ottobre"), (11, "Novembre"), (12, "Dicembre"),
    )

    anno = forms.IntegerField(min_value=2020, max_value=2099, label="Anno")
    mese = forms.TypedChoiceField(choices=MESI_CHOICES, coerce=int, label="Mese")
    tenant = forms.ModelChoiceField(
        queryset=TenantProfile.objects.all(),
        required=False,
        label="Solo inquilino",
        help_text="Se valorizzato, genera solo per questo inquilino (debug).",
    )
    force = forms.BooleanField(
        required=False,
        label="Sovrascrivi esistenti",
        help_text="Aggiorna i Receivable già presenti (la guardia allocations "
        "protegge comunque quelli riconciliati).",
    )
    dry_run = forms.BooleanField(
        required=False,
        label="Solo simulazione (dry-run)",
        help_text="Mostra cosa verrebbe scritto, senza toccare il DB.",
    )


@staff_member_required
def genera_receivables_affitto_view(request):
    """Pagina admin standalone equivalente all'action ``rigenera_receivables_affitto``
    ma indipendente da ``UtilityChargePeriod``.

    Usa la stessa funzione di calcolo (``billing.calc.rent.genera_pagamenti_mese``).
    """
    risultato = None
    if request.method == "POST":
        form = GeneraReceivableAffittoForm(request.POST)
        if form.is_valid():
            anno = form.cleaned_data["anno"]
            mese = form.cleaned_data["mese"]
            tenant = form.cleaned_data.get("tenant")
            force = form.cleaned_data.get("force", False)
            dry_run = form.cleaned_data.get("dry_run", False)

            try:
                ris = genera_pagamenti_mese(
                    anno, mese,
                    force=force,
                    persist=not dry_run,
                    tenant_id=tenant.pk if tenant else None,
                )
            except Exception as exc:  # noqa: BLE001
                form.add_error(None, f"Errore nella generazione: {exc}")
            else:
                tag = "[DRY-RUN] " if dry_run else ""
                etichetta = f"{anno}/{mese:02d}" + (
                    f" — solo {tenant.nominativo}" if tenant else ""
                ) + (" [FORCE]" if force else "")
                if dry_run:
                    for s in ris.get("simulazione", []):
                        flag = " [aggiust.]" if s["is_aggiustamento"] else ""
                        messages.info(
                            request,
                            f"{tag}{s['tenant_nominativo']}: "
                            f"{s['azione_prevista']} → {s['importo_dovuto']}€ "
                            f"(scad. {s['scadenza']}, comp. "
                            f"{s['competenza_da']}→{s['competenza_a']}){flag}",
                        )
                    if not ris.get("simulazione"):
                        messages.info(
                            request,
                            f"{tag}{etichetta}: nessun assignment attivo.",
                        )
                    risultato = {"sim": ris.get("simulazione", []), "etichetta": etichetta}
                else:
                    messages.success(
                        request,
                        f"{etichetta}: {ris['creati']} creati, "
                        f"{ris['aggiornati']} aggiornati, {ris['skippati']} skippati.",
                    )
                    for s in ris.get("skippati_per_allocation", []):
                        messages.warning(
                            request,
                            f"{s['tenant_nominativo']}: NON aggiornato — "
                            f"esistente {s['importo_esistente']}€, "
                            f"calcolato {s['importo_calcolato']}€ "
                            f"(receivable già allocato a una BT).",
                        )
                    risultato = {"esito": ris, "etichetta": etichetta}
    else:
        form = GeneraReceivableAffittoForm()

    return render(
        request,
        "admin/billing/genera_receivables_affitto.html",
        {
            **admin.site.each_context(request),
            "form": form,
            "risultato": risultato,
            "title": "Genera Receivable affitto",
            "opts": Receivable._meta,
            "has_view_permission": True,
        },
    )
