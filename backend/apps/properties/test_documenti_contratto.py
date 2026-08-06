"""
Documenti dell'immobile agganciati a un contratto
(``PropertyDocument.contract``).

Un documento collegato a un contratto è una carta di quel contratto: se è
visibile agli inquilini, la vedono solo quelli la cui occupazione sta sotto
quel contratto (``RoomAssignment.contract``). Senza contratto sul documento
vale la regola di prima: tutti gli inquilini dell'immobile.

I due controlli — lista API e serving del file — vanno verificati entrambi:
filtrare solo la lista lascerebbe il file scaricabile a chi ha l'URL.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from rest_framework.test import APIClient

from properties.models import (
    Contract,
    PropertyDocument,
    PropertyMembership,
    Room,
    RoomAssignment,
    TenantProfile,
)

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4 contenuto di test"
URL = "/api/v1/property-documents/"


@pytest.fixture(autouse=True)
def media_private_tmp(settings, tmp_path):
    settings.MEDIA_PRIVATE_ROOT = str(tmp_path / "media-private")
    settings.MEDIA_ROOT = str(tmp_path / "media")


def _inquilino(immobile, username, stanza, contratto, dal=datetime.date(2025, 3, 1)):
    """Inquilino con un'occupazione, eventualmente sotto un contratto."""
    tenant = TenantProfile.objects.create(
        user=User.objects.create_user(username),
        property=immobile,
        nominativo=username,
        giorno_pagamento_affitto=5,
    )
    RoomAssignment.objects.create(
        room=stanza,
        tenant=tenant,
        contract=contratto,
        valid_from=dal,
        canone_mensile=Decimal("400"),
    )
    return tenant


@pytest.fixture
def scena(immobile):
    contratto_a = Contract.objects.create(
        property=immobile,
        nome="Collettivo 2025",
        data_stipula=datetime.date(2025, 2, 15),
        data_decorrenza=datetime.date(2025, 2, 15),
        durata_anni=4,
    )
    contratto_b = Contract.objects.create(
        property=immobile,
        nome="Arun 2024",
        data_stipula=datetime.date(2024, 7, 11),
        data_decorrenza=datetime.date(2024, 7, 11),
        durata_anni=4,
    )
    proprietario = User.objects.create_user("prop-doc")
    PropertyMembership.objects.create(
        property=immobile,
        user=proprietario,
        ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
    )
    return {
        "immobile": immobile,
        "contratto_a": contratto_a,
        "contratto_b": contratto_b,
        "dentro": _inquilino(
            immobile, "dentro", Room.objects.create(property=immobile, nome="C1"), contratto_a
        ),
        "altro_contratto": _inquilino(
            immobile, "altro", Room.objects.create(property=immobile, nome="C2"), contratto_b
        ),
        "senza_contratto": _inquilino(
            immobile, "senza", Room.objects.create(property=immobile, nome="C3"), None
        ),
        "proprietario": proprietario,
    }


def _doc(immobile, contratto, visibile=True, nome="side letter.pdf"):
    return PropertyDocument.objects.create(
        property=immobile,
        contract=contratto,
        tipo=PropertyDocument.Tipo.SIDE_LETTER,
        visibile_inquilini=visibile,
        file=SimpleUploadedFile(nome, PDF),
    )


def _api(user, immobile=None):
    c = APIClient(enforce_csrf_checks=False)
    c.force_login(user)
    if immobile is not None:
        c.defaults["HTTP_X_PROPERTY_ID"] = str(immobile.pk)
    return c


def _ids(resp):
    dati = resp.json()
    righe = dati if isinstance(dati, list) else dati.get("results", [])
    return {r["id"] for r in righe}


class TestListaInquilino:
    def test_lo_vede_solo_chi_sta_sotto_quel_contratto(self, scena):
        doc = _doc(scena["immobile"], scena["contratto_a"])
        assert doc.id in _ids(_api(scena["dentro"].user).get(URL))
        assert doc.id not in _ids(_api(scena["altro_contratto"].user).get(URL))

    def test_senza_contratto_sull_assegnazione_non_vede_nulla_di_contratto(self, scena):
        doc = _doc(scena["immobile"], scena["contratto_a"])
        assert doc.id not in _ids(_api(scena["senza_contratto"].user).get(URL))

    def test_documento_della_casa_lo_vedono_tutti(self, scena):
        doc = _doc(scena["immobile"], None, nome="regolamento.pdf")
        for chi in ("dentro", "altro_contratto", "senza_contratto"):
            assert doc.id in _ids(_api(scena[chi].user).get(URL)), chi

    def test_non_visibile_resta_nascosto_anche_a_chi_e_nel_contratto(self, scena):
        doc = _doc(scena["immobile"], scena["contratto_a"], visibile=False)
        assert doc.id not in _ids(_api(scena["dentro"].user).get(URL))

    def test_la_proprieta_li_vede_tutti(self, scena):
        a = _doc(scena["immobile"], scena["contratto_a"])
        b = _doc(scena["immobile"], scena["contratto_b"])
        casa = _doc(scena["immobile"], None, visibile=False, nome="regolamento.pdf")
        visti = _ids(_api(scena["proprietario"], scena["immobile"]).get(URL))
        assert {a.id, b.id, casa.id} <= visti


class TestServingFile:
    """Il filtro della lista non basta: con l'URL in mano il file si
    scaricherebbe comunque."""

    def _get(self, user, url):
        c = Client()
        c.force_login(user)
        return c.get(url)

    def test_file_di_contratto_negato_a_chi_e_fuori(self, scena):
        doc = _doc(scena["immobile"], scena["contratto_a"])
        assert self._get(scena["dentro"].user, doc.file.url).status_code == 200
        assert self._get(scena["altro_contratto"].user, doc.file.url).status_code == 403
        assert self._get(scena["senza_contratto"].user, doc.file.url).status_code == 403

    def test_file_della_casa_aperto_a_tutti_gli_inquilini(self, scena):
        doc = _doc(scena["immobile"], None, nome="regolamento.pdf")
        assert self._get(scena["senza_contratto"].user, doc.file.url).status_code == 200

    def test_la_proprieta_scarica_comunque(self, scena):
        doc = _doc(scena["immobile"], scena["contratto_a"], visibile=False)
        assert self._get(scena["proprietario"], doc.file.url).status_code == 200


class TestScrittura:
    def test_upload_con_contratto(self, scena):
        resp = _api(scena["proprietario"], scena["immobile"]).post(
            URL,
            {
                "tipo": PropertyDocument.Tipo.CONTRATTO,
                "file": SimpleUploadedFile("firmato.pdf", PDF),
                "contract": scena["contratto_a"].id,
            },
            format="multipart",
        )
        assert resp.status_code == 201, resp.content
        assert resp.json()["contract"] == scena["contratto_a"].id
        assert resp.json()["contract_nome"] == "Collettivo 2025"

    def test_contratto_di_un_altro_immobile_400(self, scena, immobile2):
        estraneo = Contract.objects.create(
            property=immobile2,
            data_stipula=datetime.date(2025, 1, 1),
            data_decorrenza=datetime.date(2025, 1, 1),
            durata_anni=4,
        )
        resp = _api(scena["proprietario"], scena["immobile"]).post(
            URL,
            {
                "tipo": PropertyDocument.Tipo.CONTRATTO,
                "file": SimpleUploadedFile("firmato.pdf", PDF),
                "contract": estraneo.id,
            },
            format="multipart",
        )
        assert resp.status_code == 400, resp.content
        assert "contract" in resp.json()

    def test_eliminare_il_contratto_lascia_il_documento(self, scena):
        """SET_NULL: il file non si perde, torna a essere una carta della
        casa. Attenzione: se era visibile agli inquilini, da quel momento lo
        vedono tutti."""
        doc = _doc(scena["immobile"], scena["contratto_a"])
        scena["contratto_a"].delete()
        doc.refresh_from_db()
        assert doc.contract_id is None
