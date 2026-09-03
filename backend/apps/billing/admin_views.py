"""
View admin custom dell'app billing.
"""
import calendar
from datetime import date

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from billing.calc.rent import genera_pagamenti_mese
from billing.models import Receivable
from properties.models import Property, TenantProfile


def _tenants_attivi_nel_mese(anno: int, mese: int, prop=None):
    """Tenant con almeno una ``RoomAssignment`` che interseca il mese
    (anno, mese): stessa condizione di overlap di
    ``genera_pagamenti_mese``. Se ``prop`` è dato, limita ai suoi tenant."""
    primo = date(anno, mese, 1)
    ultimo = date(anno, mese, calendar.monthrange(anno, mese)[1])
    qs = TenantProfile.objects.filter(
        Q(assignments__valid_from__lte=ultimo)
        & Q(assignments__rinunciata=False)
        & (
            Q(assignments__valid_to__isnull=True)
            | Q(assignments__valid_to__gte=primo)
        )
    )
    if prop is not None:
        qs = qs.filter(assignments__room__property=prop)
    return qs.distinct().order_by("nominativo")


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
    property = forms.ModelChoiceField(
        queryset=Property.objects.all().order_by("nome"),
        label="Immobile",
        help_text="La generazione è vincolata a questo immobile.",
    )
    tenant = forms.ModelChoiceField(
        queryset=TenantProfile.objects.all(),
        required=False,
        label="Solo inquilino",
        help_text="Se valorizzato, genera solo per questo inquilino. "
        "La lista mostra solo chi ha una stanza assegnata nel mese scelto.",
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

    def clean(self):
        cleaned = super().clean()
        tenant = cleaned.get("tenant")
        anno = cleaned.get("anno")
        mese = cleaned.get("mese")
        prop = cleaned.get("property")
        if tenant and anno and mese:
            attivi = _tenants_attivi_nel_mese(anno, mese, prop=prop)
            if not attivi.filter(pk=tenant.pk).exists():
                self.add_error(
                    "tenant",
                    f"{tenant.nominativo} non ha una stanza assegnata "
                    f"nel {mese:02d}/{anno}: nessun Receivable verrebbe generato.",
                )
        return cleaned


@staff_member_required
def genera_affitto_tenants_json(request):
    """Endpoint JSON per la tendina dipendente della pagina
    "Genera Receivable affitto": dato ``?anno=&mese=&property=`` ritorna i
    tenant con una stanza assegnata in quel mese in quell'immobile."""
    try:
        anno = int(request.GET.get("anno", ""))
        mese = int(request.GET.get("mese", ""))
        date(anno, mese, 1)
    except ValueError:
        return JsonResponse({"error": "Parametri anno/mese non validi."}, status=400)
    prop = None
    property_id = request.GET.get("property")
    if property_id:
        prop = Property.objects.filter(pk=property_id).first()
        if prop is None:
            return JsonResponse({"error": "Immobile non valido."}, status=400)
    tenants = [
        {"id": t.pk, "nominativo": t.nominativo}
        for t in _tenants_attivi_nel_mese(anno, mese, prop=prop)
    ]
    return JsonResponse({"tenants": tenants})


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
            prop = form.cleaned_data["property"]
            tenant = form.cleaned_data.get("tenant")
            force = form.cleaned_data.get("force", False)
            dry_run = form.cleaned_data.get("dry_run", False)

            try:
                ris = genera_pagamenti_mese(
                    anno, mese,
                    force=force,
                    persist=not dry_run,
                    tenant_id=tenant.pk if tenant else None,
                    property=prop,
                )
            except Exception as exc:  # noqa: BLE001
                form.add_error(None, f"Errore nella generazione: {exc}")
            else:
                tag = "[DRY-RUN] " if dry_run else ""
                etichetta = f"{anno}/{mese:02d} [{prop.nome}]" + (
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
        oggi = timezone.localdate()
        form = GeneraReceivableAffittoForm(
            initial={"anno": oggi.year, "mese": oggi.month}
        )

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
