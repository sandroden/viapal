"""Test della vista /media-private/ (serving autenticato dei file riservati).

Matrice minima: anonimo, inquilino titolare, altro inquilino (stessa e
altra property), membro della property, membro di altra property,
superuser; più i casi 404 (file ignoto, prefisso ignoto).
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from billing.models import Supplier, UtilityBill
from properties.models import (
    PropertyDocument,
    PropertyMembership,
    TenantDocument,
    TenantProfile,
)

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4 contenuto di test"


@pytest.fixture(autouse=True)
def media_private_tmp(settings, tmp_path):
    settings.MEDIA_PRIVATE_ROOT = str(tmp_path / "media-private")
    settings.MEDIA_ROOT = str(tmp_path / "media")


@pytest.fixture
def owner_a(immobile):
    user = User.objects.create_user("owner-a", password="x")
    PropertyMembership.objects.create(
        property=immobile, user=user, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    return user


@pytest.fixture
def owner_b(immobile2):
    user = User.objects.create_user("owner-b", password="x")
    PropertyMembership.objects.create(
        property=immobile2, user=user, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    return user


@pytest.fixture
def tenant_a(immobile):
    user = User.objects.create_user("tenant-a", password="x")
    return TenantProfile.objects.create(
        user=user, property=immobile, nominativo="Mario Rossi", giorno_pagamento_affitto=1
    )


@pytest.fixture
def tenant_a2(immobile):
    user = User.objects.create_user("tenant-a2", password="x")
    return TenantProfile.objects.create(
        user=user, property=immobile, nominativo="Luigi Verdi", giorno_pagamento_affitto=1
    )


@pytest.fixture
def tenant_b(immobile2):
    user = User.objects.create_user("tenant-b", password="x")
    return TenantProfile.objects.create(
        user=user, property=immobile2, nominativo="Anna Bianchi", giorno_pagamento_affitto=1
    )


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser("admin-test", password="x")


@pytest.fixture
def doc_tenant_a(tenant_a):
    doc = TenantDocument.objects.create(
        tenant=tenant_a,
        tipo=TenantDocument.Tipo.CARTA_IDENTITA,
        file=SimpleUploadedFile("ci.pdf", PDF, content_type="application/pdf"),
    )
    return doc


def _get(user, url):
    client = Client()
    if user is not None:
        client.force_login(user)
    return client.get(url)


# ── documenti/ (TenantDocument) ─────────────────────────────────────────────


def test_anonimo_negato(doc_tenant_a):
    assert _get(None, doc_tenant_a.file.url).status_code == 403


def test_url_e_su_media_private(doc_tenant_a):
    assert doc_tenant_a.file.url.startswith("/media-private/documenti/")


def test_inquilino_scarica_il_proprio(doc_tenant_a, tenant_a):
    resp = _get(tenant_a.user, doc_tenant_a.file.url)
    assert resp.status_code == 200
    assert b"".join(resp.streaming_content) == PDF


def test_altro_inquilino_stessa_property_negato(doc_tenant_a, tenant_a2):
    assert _get(tenant_a2.user, doc_tenant_a.file.url).status_code == 403


def test_inquilino_altra_property_negato(doc_tenant_a, tenant_b):
    assert _get(tenant_b.user, doc_tenant_a.file.url).status_code == 403


def test_membro_property_scarica(doc_tenant_a, owner_a):
    assert _get(owner_a, doc_tenant_a.file.url).status_code == 200


def test_membro_altra_property_negato(doc_tenant_a, owner_b):
    assert _get(owner_b, doc_tenant_a.file.url).status_code == 403


def test_superuser_scarica(doc_tenant_a, superuser):
    assert _get(superuser, doc_tenant_a.file.url).status_code == 200


def test_file_non_referenziato_404(owner_a):
    assert _get(owner_a, "/media-private/documenti/1-x/inesistente.pdf").status_code == 404


def test_prefisso_sconosciuto_404(owner_a):
    assert _get(owner_a, "/media-private/galleria/foto.jpg").status_code == 404


# ── documenti-proprieta/ (PropertyDocument) ─────────────────────────────────


@pytest.fixture
def doc_casa_riservato(immobile):
    return PropertyDocument.objects.create(
        property=immobile,
        tipo=PropertyDocument.Tipo.CONTRATTO,
        visibile_inquilini=False,
        file=SimpleUploadedFile("contratto.pdf", PDF),
    )


def test_doc_casa_membro_ok_inquilino_negato(doc_casa_riservato, owner_a, tenant_a):
    assert _get(owner_a, doc_casa_riservato.file.url).status_code == 200
    assert _get(tenant_a.user, doc_casa_riservato.file.url).status_code == 403


def test_doc_casa_visibile_inquilini(immobile, tenant_a, tenant_b):
    doc = PropertyDocument.objects.create(
        property=immobile,
        tipo=PropertyDocument.Tipo.REGOLAMENTO_CONDOMINIALE,
        visibile_inquilini=True,
        file=SimpleUploadedFile("regolamento.pdf", PDF),
    )
    assert _get(tenant_a.user, doc.file.url).status_code == 200
    assert _get(tenant_b.user, doc.file.url).status_code == 403


# ── bollette/ (UtilityBill) ─────────────────────────────────────────────────


@pytest.fixture
def bolletta_a(immobile):
    supplier = Supplier.objects.create(nome="Edison Test", property=immobile)
    return UtilityBill.objects.create(
        immobile=immobile,
        supplier=supplier,
        numero_fattura="TEST-1",
        data_emissione=datetime.date(2026, 5, 15),
        periodo_da=datetime.date(2026, 5, 1),
        periodo_a=datetime.date(2026, 5, 31),
        importo_totale=Decimal("100.00"),
        file_pdf=SimpleUploadedFile("bolletta.pdf", PDF),
    )


def test_bolletta_membro_e_inquilino_ok(bolletta_a, owner_a, tenant_a):
    assert bolletta_a.file_pdf.url.startswith("/media-private/bollette/")
    assert _get(owner_a, bolletta_a.file_pdf.url).status_code == 200
    assert _get(tenant_a.user, bolletta_a.file_pdf.url).status_code == 200


def test_bolletta_estranei_negati(bolletta_a, owner_b, tenant_b):
    assert _get(owner_b, bolletta_a.file_pdf.url).status_code == 403
    assert _get(tenant_b.user, bolletta_a.file_pdf.url).status_code == 403


# ── spese/ (Expense.allegato) ───────────────────────────────────────────────


@pytest.fixture
def spesa_a(immobile, owner_a):
    from billing.models import Expense, ExpenseCategory
    from properties.models import OwnerProfile

    owner = OwnerProfile.objects.create(user=owner_a, nominativo="Owner A")
    cat = ExpenseCategory.objects.create(
        property=immobile, nome="Manutenzione", codice="MAN"
    )
    return Expense.objects.create(
        property=immobile,
        data=datetime.date(2026, 8, 20),
        category=cat,
        importo=Decimal("80.00"),
        descrizione="Idraulico",
        anticipata_da_owner=owner,
        allegato=SimpleUploadedFile("fattura.pdf", PDF),
    )


def test_spesa_url_su_media_private(spesa_a):
    assert spesa_a.allegato.url.startswith("/media-private/spese/")


def test_spesa_membro_scarica(spesa_a, owner_a):
    resp = _get(owner_a, spesa_a.allegato.url)
    assert resp.status_code == 200
    assert b"".join(resp.streaming_content) == PDF


def test_spesa_inquilino_negato(spesa_a, tenant_a):
    # Le fatture della casa non sono carte dell'inquilino.
    assert _get(tenant_a.user, spesa_a.allegato.url).status_code == 403


def test_spesa_membro_altra_property_negato(spesa_a, owner_b):
    assert _get(owner_b, spesa_a.allegato.url).status_code == 403


def test_spesa_superuser_scarica(spesa_a, superuser):
    assert _get(superuser, spesa_a.allegato.url).status_code == 200
