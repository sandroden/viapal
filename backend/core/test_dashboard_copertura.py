"""Ogni modello registrato in admin deve comparire nella dashboard.

I moduli di admin-tools filtrano per pattern (`modulo.Classe`): un modello di
un'app che nessun pattern nomina non sparisce con un errore, sparisce in
silenzio — è successo a `leads.Lead`, invisibile finché non lo si è cercato.
Il test guarda l'HTML renderizzato, non la struttura dei moduli: è indifferente
a come i tab sono organizzati, purché il link alla changelist ci sia.
"""
import pytest
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

# Modelli tecnici tenuti fuori dalla dashboard per scelta: si raggiungono
# dall'URL diretto quando servono (praticamente mai).
FUORI_DASHBOARD = {
    "sites.site",
    "authtoken.tokenproxy",
    "account.emailaddress",
}


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser("su_dash", "su@v.it", "pwd123!")


def test_nessun_modello_resta_fuori_dalla_dashboard(superuser):
    client = Client()
    client.force_login(superuser)
    html = client.get("/admin/").content.decode()

    mancanti = []
    for model in admin.site._registry:
        meta = model._meta
        etichetta = f"{meta.app_label}.{meta.model_name}"
        if etichetta in FUORI_DASHBOARD:
            continue
        url = reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist")
        if f'href="{url}"' not in html:
            mancanti.append(etichetta)

    assert not mancanti, (
        "modelli registrati in admin ma assenti dalla dashboard: "
        f"{sorted(mancanti)} — aggiungili a un modulo di core/dashboard.py "
        "oppure, se è voluto, a FUORI_DASHBOARD"
    )
