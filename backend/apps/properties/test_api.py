"""
Test API per l'app properties.

Coprono:
- Smoke test viewset (proprietario ottiene 200 con risultati)
- Filtering object-level per inquilino
- Accesso negato a risorse altrui
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from properties.models import (
    Contract,
    OwnerBankAccount,
    OwnerProfile,
    PropertyDocument,
    PropertyMembership,
    Room,
    RoomAssignment,
    TenantDocument,
    TenantProfile,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    return APIClient(enforce_csrf_checks=False)


@pytest.fixture
def gruppo_proprietari(db):
    grp, _ = Group.objects.get_or_create(name="proprietari")
    return grp


@pytest.fixture
def gruppo_inquilini(db):
    grp, _ = Group.objects.get_or_create(name="inquilini")
    return grp


@pytest.fixture
def user_prop(db, gruppo_proprietari, immobile):
    u = User.objects.create_user("prop_test", email="p@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
    )
    return u


@pytest.fixture
def user_inq_1(db, gruppo_inquilini):
    u = User.objects.create_user("inq_test_1", email="i1@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    return u


@pytest.fixture
def user_inq_2(db, gruppo_inquilini):
    u = User.objects.create_user("inq_test_2", email="i2@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    return u


@pytest.fixture
def owner_profile(db, user_prop):
    return OwnerProfile.objects.create(user=user_prop, nominativo="Proprietario Test")


@pytest.fixture
def tenant_1(db, user_inq_1, immobile):
    return TenantProfile.objects.create(
        user=user_inq_1,
        property=immobile,
        nominativo="Inquilino Uno",
        giorno_pagamento_affitto=1,
    )


@pytest.fixture
def tenant_2(db, user_inq_2, immobile):
    return TenantProfile.objects.create(
        user=user_inq_2,
        property=immobile,
        nominativo="Inquilino Due",
        giorno_pagamento_affitto=5,
    )


@pytest.fixture
def room_1(db, immobile):
    return Room.objects.create(property=immobile, nome="Camera Test A", ordinamento=10)


@pytest.fixture
def room_2(db, immobile):
    return Room.objects.create(property=immobile, nome="Camera Test B", ordinamento=11)


@pytest.fixture
def assignment_1(db, room_1, tenant_1):
    return RoomAssignment.objects.create(
        room=room_1,
        tenant=tenant_1,
        valid_from=datetime.date(2024, 9, 1),
        canone_mensile=Decimal("400"),
    )


@pytest.fixture
def assignment_2(db, room_2, tenant_2):
    return RoomAssignment.objects.create(
        room=room_2,
        tenant=tenant_2,
        valid_from=datetime.date(2024, 9, 1),
        canone_mensile=Decimal("380"),
    )


@pytest.fixture
def contract(db, immobile):
    return Contract.objects.create(
        property=immobile,
        data_stipula=datetime.date(2024, 9, 15),
        data_decorrenza=datetime.date(2024, 9, 20),
        durata_anni=4,
    )


@pytest.fixture
def bank_account(db, owner_profile):
    return OwnerBankAccount.objects.create(
        owner=owner_profile,
        banca="Banca Test",
        intestatario="Proprietario Test",
        iban="IT60X0542811101000000000001",
    )


@pytest.fixture
def client_prop(api_client, user_prop):
    api_client.force_login(user_prop)
    return api_client


@pytest.fixture
def client_inq_1(api_client, user_inq_1):
    api_client.force_login(user_inq_1)
    return api_client


@pytest.fixture
def client_inq_2(api_client, user_inq_2):
    api_client.force_login(user_inq_2)
    return api_client


# ---------------------------------------------------------------------------
# Test OwnerProfileViewSet
# ---------------------------------------------------------------------------


class TestOwnerProfileViewSet:
    def test_proprietario_vede_lista(self, client_prop, owner_profile):
        resp = client_prop.get("/api/v1/owners/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_inquilino_non_autorizzato(self, client_inq_1):
        resp = client_inq_1.get("/api/v1/owners/")
        assert resp.status_code == 403

    def test_anonimo_non_autorizzato(self):
        client = APIClient()
        resp = client.get("/api/v1/owners/")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test TenantProfileViewSet
# ---------------------------------------------------------------------------


class TestTenantProfileViewSet:
    def test_proprietario_vede_attivi_default(
        self, client_prop, tenant_1, tenant_2, assignment_1, assignment_2
    ):
        resp = client_prop.get("/api/v1/tenants/")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.json()]
        assert tenant_1.id in ids
        assert tenant_2.id in ids

    def test_proprietario_default_esclude_storici(
        self, client_prop, tenant_1, tenant_2, assignment_1
    ):
        # tenant_2 senza assignment attivo → non deve comparire di default
        resp = client_prop.get("/api/v1/tenants/")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.json()]
        assert tenant_1.id in ids
        assert tenant_2.id not in ids

    def test_proprietario_solo_attivi_zero_include_tutti(
        self, client_prop, tenant_1, tenant_2, assignment_1
    ):
        resp = client_prop.get("/api/v1/tenants/?solo_attivi=0")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.json()]
        assert tenant_1.id in ids
        assert tenant_2.id in ids

    def test_proprietario_assignment_chiuso_non_attivo(
        self, client_prop, tenant_1, tenant_2, assignment_1, assignment_2
    ):
        # Chiudo assignment_2 nel passato → tenant_2 non più attivo
        assignment_2.valid_to = datetime.date(2024, 12, 31)
        assignment_2.save()
        resp = client_prop.get("/api/v1/tenants/")
        ids = [t["id"] for t in resp.json()]
        assert tenant_1.id in ids
        assert tenant_2.id not in ids

    def test_proprietario_filtra_per_anno(
        self, client_prop, tenant_1, tenant_2, room_1, room_2
    ):
        # tenant_1: assignment chiuso nel 2024 → presente solo nel 2024
        RoomAssignment.objects.create(
            room=room_1,
            tenant=tenant_1,
            valid_from=datetime.date(2024, 3, 1),
            valid_to=datetime.date(2024, 12, 31),
            canone_mensile=Decimal("400"),
        )
        # tenant_2: assignment aperto dal 2025 → presente solo dal 2025
        RoomAssignment.objects.create(
            room=room_2,
            tenant=tenant_2,
            valid_from=datetime.date(2025, 6, 1),
            canone_mensile=Decimal("380"),
        )

        resp_2024 = client_prop.get("/api/v1/tenants/?anno=2024")
        ids_2024 = [t["id"] for t in resp_2024.json()]
        assert tenant_1.id in ids_2024
        assert tenant_2.id not in ids_2024

        resp_2025 = client_prop.get("/api/v1/tenants/?anno=2025")
        ids_2025 = [t["id"] for t in resp_2025.json()]
        assert tenant_1.id not in ids_2025
        assert tenant_2.id in ids_2025

    def test_anno_include_senza_assignment(
        self, client_prop, tenant_1, tenant_2, room_1
    ):
        # tenant_1: assignment che copre il 2025; tenant_2: profilo creato e
        # mai assegnato (es. prima-assegnazione fallita) → deve comparire
        # comunque nella lista per anno, col flag ha_assignment=False.
        RoomAssignment.objects.create(
            room=room_1,
            tenant=tenant_1,
            valid_from=datetime.date(2025, 2, 1),
            canone_mensile=Decimal("400"),
        )
        resp = client_prop.get("/api/v1/tenants/?anno=2025")
        assert resp.status_code == 200, resp.content
        per_id = {t["id"]: t for t in resp.json()}
        assert tenant_1.id in per_id
        assert per_id[tenant_1.id]["ha_assignment"] is True
        assert tenant_2.id in per_id
        assert per_id[tenant_2.id]["ha_assignment"] is False

        # Il mai-assegnato compare in qualunque anno; tenant_1 solo dove
        # l'assignment si sovrappone.
        resp_2020 = client_prop.get("/api/v1/tenants/?anno=2020")
        ids_2020 = [t["id"] for t in resp_2020.json()]
        assert tenant_2.id in ids_2020
        assert tenant_1.id not in ids_2020

    def test_proprietario_anno_invalido_fallback_a_solo_attivi(
        self, client_prop, tenant_1, assignment_1
    ):
        # Anno non parsabile → comportamento default (solo attivi oggi)
        resp = client_prop.get("/api/v1/tenants/?anno=pippo")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.json()]
        assert tenant_1.id in ids

    def test_con_assignment_include_futuri_esclude_mai_assegnati(
        self, client_prop, tenant_1, tenant_2, room_1
    ):
        # tenant_1: assegnazione a decorrenza futura → incluso;
        # tenant_2: profilo creato e mai assegnato → escluso.
        RoomAssignment.objects.create(
            room=room_1,
            tenant=tenant_1,
            valid_from=datetime.date.today() + datetime.timedelta(days=30),
            canone_mensile=Decimal("400"),
        )
        resp = client_prop.get("/api/v1/tenants/?solo_attivi=0&con_assignment=1")
        assert resp.status_code == 200, resp.content
        ids = [t["id"] for t in resp.json()]
        assert tenant_1.id in ids
        assert tenant_2.id not in ids

    def test_con_assignment_storico_incluso_senza_duplicati(
        self, client_prop, tenant_1, room_1, room_2
    ):
        # Due assegnazioni (una chiusa nel passato, una in corso): l'inquilino
        # compare, e una volta sola (distinct).
        RoomAssignment.objects.create(
            room=room_1,
            tenant=tenant_1,
            valid_from=datetime.date(2023, 1, 1),
            valid_to=datetime.date(2023, 12, 31),
            canone_mensile=Decimal("350"),
        )
        RoomAssignment.objects.create(
            room=room_2,
            tenant=tenant_1,
            valid_from=datetime.date(2024, 9, 1),
            canone_mensile=Decimal("400"),
        )
        resp = client_prop.get("/api/v1/tenants/?solo_attivi=0&con_assignment=1")
        assert resp.status_code == 200, resp.content
        ids = [t["id"] for t in resp.json()]
        assert ids.count(tenant_1.id) == 1

    def test_inquilino_vede_solo_se_stesso(self, client_inq_1, tenant_1, tenant_2):
        resp = client_inq_1.get("/api/v1/tenants/")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.json()]
        assert tenant_1.id in ids
        assert tenant_2.id not in ids

    def test_inquilino_detail_se_stesso(self, client_inq_1, tenant_1):
        resp = client_inq_1.get(f"/api/v1/tenants/{tenant_1.id}/")
        assert resp.status_code == 200

    def test_inquilino_non_vede_altro(self, client_inq_1, tenant_2):
        resp = client_inq_1.get(f"/api/v1/tenants/{tenant_2.id}/")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test RoomViewSet
# ---------------------------------------------------------------------------


class TestRoomViewSet:
    def test_proprietario_vede_tutte(self, client_prop, room_1, room_2):
        resp = client_prop.get("/api/v1/rooms/")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert room_1.id in ids
        assert room_2.id in ids

    def test_inquilino_vede_solo_propria(self, client_inq_1, assignment_1, room_1, room_2):
        resp = client_inq_1.get("/api/v1/rooms/")
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()]
        assert room_1.id in ids
        assert room_2.id not in ids


# ---------------------------------------------------------------------------
# Test RoomAssignmentViewSet
# ---------------------------------------------------------------------------


class TestRoomAssignmentViewSet:
    def test_proprietario_vede_tutti(self, client_prop, assignment_1, assignment_2):
        resp = client_prop.get("/api/v1/room-assignments/")
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()]
        assert assignment_1.id in ids
        assert assignment_2.id in ids

    def test_inquilino_vede_solo_propri(self, client_inq_1, assignment_1, assignment_2):
        resp = client_inq_1.get("/api/v1/room-assignments/")
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()]
        assert assignment_1.id in ids
        assert assignment_2.id not in ids


# ---------------------------------------------------------------------------
# Test ContractViewSet
# ---------------------------------------------------------------------------


class TestContractViewSet:
    def test_proprietario_vede_contratto(self, client_prop, contract):
        resp = client_prop.get("/api/v1/contracts/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_inquilino_non_autorizzato(self, client_inq_1):
        resp = client_inq_1.get("/api/v1/contracts/")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test OwnerBankAccountViewSet
# ---------------------------------------------------------------------------


class TestOwnerBankAccountViewSet:
    def test_proprietario_vede_conti(self, client_prop, bank_account):
        resp = client_prop.get("/api/v1/bank-accounts/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_inquilino_non_autorizzato(self, client_inq_1):
        resp = client_inq_1.get("/api/v1/bank-accounts/")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test TenantProfileViewSet.me (auto-modifica dati inquilino)
# ---------------------------------------------------------------------------


def _pdf_finto(nome="doc.pdf"):
    return SimpleUploadedFile(nome, b"%PDF-1.4 contenuto finto", content_type="application/pdf")


class TestTenantMe:
    def test_get_me_ritorna_proprio_profilo(self, client_inq_1, tenant_1):
        resp = client_inq_1.get("/api/v1/tenants/me/")
        assert resp.status_code == 200
        assert resp.json()["id"] == tenant_1.id
        assert resp.json()["nominativo"] == "Inquilino Uno"

    def test_patch_me_aggiorna_campi_consentiti(self, client_inq_1, tenant_1):
        resp = client_inq_1.patch(
            "/api/v1/tenants/me/",
            {"nominativo": "Nuovo Nome", "telefono": "333111", "codice_fiscale": "RSSMRA80A01H501U"},
            format="json",
        )
        assert resp.status_code == 200
        tenant_1.refresh_from_db()
        assert tenant_1.nominativo == "Nuovo Nome"
        assert tenant_1.telefono == "333111"
        assert tenant_1.codice_fiscale == "RSSMRA80A01H501U"

    def test_patch_me_ignora_campi_non_consentiti(self, client_inq_1, tenant_1):
        # giorno_pagamento_affitto NON è nel serializer ristretto: deve restare 1.
        resp = client_inq_1.patch(
            "/api/v1/tenants/me/",
            {"nominativo": "Tizio", "giorno_pagamento_affitto": 20, "deposito_versato": "999"},
            format="json",
        )
        assert resp.status_code == 200
        tenant_1.refresh_from_db()
        assert tenant_1.nominativo == "Tizio"
        assert tenant_1.giorno_pagamento_affitto == 1
        assert tenant_1.deposito_versato == Decimal("0")

    def test_me_senza_profilo_404(self, api_client, user_prop):
        # Un proprietario non ha tenant_profile.
        api_client.force_login(user_prop)
        resp = api_client.get("/api/v1/tenants/me/")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test TenantDocumentViewSet
# ---------------------------------------------------------------------------


class TestTenantDocumentViewSet:
    @pytest.fixture(autouse=True)
    def _media_tmp(self, settings, tmp_path):
        # I file caricati nei test finiscono in una dir temporanea, non in media/.
        settings.MEDIA_ROOT = str(tmp_path)

    def test_inquilino_carica_proprio_documento(self, client_inq_1, tenant_1):
        resp = client_inq_1.post(
            "/api/v1/tenant-documents/",
            {"tipo": "passaporto", "file": _pdf_finto(), "descrizione": "fronte"},
            format="multipart",
        )
        assert resp.status_code == 201, resp.content
        doc = TenantDocument.objects.get(id=resp.json()["id"])
        # tenant forzato al proprio profilo, caricato_da tracciato
        assert doc.tenant_id == tenant_1.id
        assert doc.caricato_da_id == tenant_1.user_id

    def test_inquilino_non_puo_caricare_per_altri(self, client_inq_1, tenant_1, tenant_2):
        # Anche passando tenant=tenant_2, il documento finisce su tenant_1.
        resp = client_inq_1.post(
            "/api/v1/tenant-documents/",
            {"tipo": "carta_identita", "file": _pdf_finto(), "tenant": tenant_2.id},
            format="multipart",
        )
        assert resp.status_code == 201
        assert TenantDocument.objects.get(id=resp.json()["id"]).tenant_id == tenant_1.id

    def test_inquilino_vede_solo_propri(self, client_inq_1, tenant_1, tenant_2):
        TenantDocument.objects.create(tenant=tenant_1, tipo="passaporto", file=_pdf_finto())
        TenantDocument.objects.create(tenant=tenant_2, tipo="passaporto", file=_pdf_finto())
        resp = client_inq_1.get("/api/v1/tenant-documents/")
        assert resp.status_code == 200
        tenant_ids = {d["tenant"] for d in resp.json()}
        assert tenant_ids == {tenant_1.id}

    def test_inquilino_non_accede_a_documento_altrui(self, client_inq_1, tenant_2):
        doc = TenantDocument.objects.create(tenant=tenant_2, tipo="passaporto", file=_pdf_finto())
        resp = client_inq_1.get(f"/api/v1/tenant-documents/{doc.id}/")
        assert resp.status_code == 404

    def test_inquilino_elimina_proprio(self, client_inq_1, tenant_1):
        doc = TenantDocument.objects.create(tenant=tenant_1, tipo="passaporto", file=_pdf_finto())
        resp = client_inq_1.delete(f"/api/v1/tenant-documents/{doc.id}/")
        assert resp.status_code == 204
        assert not TenantDocument.objects.filter(id=doc.id).exists()

    def test_proprietario_vede_tutti_e_filtra(self, client_prop, tenant_1, tenant_2):
        TenantDocument.objects.create(tenant=tenant_1, tipo="passaporto", file=_pdf_finto())
        TenantDocument.objects.create(tenant=tenant_2, tipo="passaporto", file=_pdf_finto())
        resp = client_prop.get("/api/v1/tenant-documents/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        resp_filtro = client_prop.get(f"/api/v1/tenant-documents/?tenant={tenant_1.id}")
        tenant_ids = {d["tenant"] for d in resp_filtro.json()}
        assert tenant_ids == {tenant_1.id}

    def test_proprietario_deve_indicare_tenant(self, client_prop, tenant_1):
        resp = client_prop.post(
            "/api/v1/tenant-documents/",
            {"tipo": "passaporto", "file": _pdf_finto()},
            format="multipart",
        )
        assert resp.status_code == 400

    def test_estensione_non_consentita_rifiutata(self, client_inq_1, tenant_1):
        cattivo = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")
        resp = client_inq_1.post(
            "/api/v1/tenant-documents/",
            {"tipo": "altro", "file": cattivo},
            format="multipart",
        )
        assert resp.status_code == 400

    def test_anonimo_non_autorizzato(self, tenant_1):
        client = APIClient()
        resp = client.get("/api/v1/tenant-documents/")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Test fascicolo documenti (checklist con stati)
# ---------------------------------------------------------------------------


class TestFascicolo:
    URL = "/api/v1/tenant-documents/fascicolo/"

    @pytest.fixture(autouse=True)
    def _media_tmp(self, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        settings.MEDIA_PRIVATE_ROOT = str(tmp_path / "media-private")

    def _voci(self, resp):
        return {v["tipo"]: v for v in resp.json()["voci"]}

    def test_fascicolo_vuoto_non_elenca_nulla(self, client_inq_1, tenant_1):
        payload = client_inq_1.get(self.URL).json()
        # Nessun documento è dovuto: senza file non c'è nulla da elencare —
        # nemmeno i due che generiamo noi, che si producono da un'azione
        # apposita e non da una riga vuota nel fascicolo.
        assert payload["voci"] == []
        assert payload["altri"] == []

    def test_voce_compare_solo_se_caricata(self, client_inq_1, tenant_1):
        TenantDocument.objects.create(
            tenant=tenant_1, tipo="passaporto", file=_pdf_finto()
        )
        voci = self._voci(client_inq_1.get(self.URL))
        assert voci["passaporto"]["stato"] == "ok"
        assert "carta_identita" not in voci

    def test_ricevuta_registrazione_agenzia(self, client_inq_1, tenant_1):
        TenantDocument.objects.create(
            tenant=tenant_1, tipo="ricevuta_registrazione", file=_pdf_finto()
        )
        voce = self._voci(client_inq_1.get(self.URL))["ricevuta_registrazione"]
        assert voce["tipo_display"] == "Registrazione contratto subentro"
        assert voce["stato"] == "ok"

    def test_fronte_retro_una_voce_due_pagine(self, client_inq_1, tenant_1):
        for descrizione in ("fronte", "retro"):
            TenantDocument.objects.create(
                tenant=tenant_1,
                tipo="carta_identita",
                descrizione=descrizione,
                file=_pdf_finto(),
            )
        voce = self._voci(client_inq_1.get(self.URL))["carta_identita"]
        assert voce["stato"] == "ok"
        assert [p["etichetta"] for p in voce["pagine"]] == ["fronte", "retro"]
        assert all(p["file"].startswith("/media-private/") for p in voce["pagine"])

    def test_stati_di_scadenza(self, client_inq_1, tenant_1):
        oggi = datetime.date.today()
        TenantDocument.objects.create(
            tenant=tenant_1,
            tipo="carta_identita",
            file=_pdf_finto(),
            data_scadenza=oggi + datetime.timedelta(days=30),
        )
        TenantDocument.objects.create(
            tenant=tenant_1,
            tipo="permesso_soggiorno",
            file=_pdf_finto(),
            data_scadenza=oggi - datetime.timedelta(days=1),
        )
        TenantDocument.objects.create(
            tenant=tenant_1,
            tipo="codice_fiscale",
            file=_pdf_finto(),
            data_scadenza=oggi + datetime.timedelta(days=365),
        )
        voci = self._voci(client_inq_1.get(self.URL))
        assert voci["carta_identita"]["stato"] == "scadenza"
        assert voci["carta_identita"]["giorni_alla_scadenza"] == 30
        assert voci["permesso_soggiorno"]["stato"] == "scaduto"
        assert voci["codice_fiscale"]["stato"] == "ok"

    def test_voce_prende_lo_stato_peggiore_delle_pagine(self, client_inq_1, tenant_1):
        oggi = datetime.date.today()
        TenantDocument.objects.create(
            tenant=tenant_1, tipo="carta_identita", descrizione="fronte", file=_pdf_finto()
        )
        TenantDocument.objects.create(
            tenant=tenant_1,
            tipo="carta_identita",
            descrizione="retro",
            file=_pdf_finto(),
            data_scadenza=oggi - datetime.timedelta(days=2),
        )
        assert self._voci(client_inq_1.get(self.URL))["carta_identita"]["stato"] == "scaduto"

    def test_altro_resta_fuori_dalla_checklist(self, client_inq_1, tenant_1):
        for descrizione in ("bolletta vecchia", "lettera"):
            TenantDocument.objects.create(
                tenant=tenant_1, tipo="altro", descrizione=descrizione, file=_pdf_finto()
            )
        payload = client_inq_1.get(self.URL).json()
        assert "altro" not in {v["tipo"] for v in payload["voci"]}
        # Due file "altro" restano due voci distinte, non una con due pagine.
        assert [a["titolo"] for a in payload["altri"]] == ["bolletta vecchia", "lettera"]

    def test_riepilogo(self, client_inq_1, tenant_1):
        oggi = datetime.date.today()
        TenantDocument.objects.create(
            tenant=tenant_1, tipo="carta_identita", file=_pdf_finto()
        )
        TenantDocument.objects.create(
            tenant=tenant_1,
            tipo="passaporto",
            file=_pdf_finto(),
            data_scadenza=oggi - datetime.timedelta(days=3),
        )
        riepilogo = client_inq_1.get(self.URL).json()["riepilogo"]
        # Carta d'identità valida, passaporto scaduto: due voci, entrambe
        # con un file dietro.
        assert riepilogo["ok"] == 1
        assert riepilogo["scaduto"] == 1
        assert riepilogo["voci"] == 2
        assert riepilogo["da_sistemare"] == 1
        # Nessun conteggio di "mancanti" né di documenti attesi: non c'è un
        # minimo da caricare.
        assert "mancante" not in riepilogo
        assert "completezza" not in riepilogo
        assert "attesa" not in riepilogo

    def test_inquilino_non_vede_documenti_altrui(self, client_inq_1, tenant_1, tenant_2):
        TenantDocument.objects.create(
            tenant=tenant_2, tipo="passaporto", file=_pdf_finto()
        )
        payload = client_inq_1.get(self.URL).json()
        assert payload["tenant"] == tenant_1.id
        assert "passaporto" not in {v["tipo"] for v in payload["voci"]}

    def test_proprietario_deve_indicare_inquilino(self, client_prop, tenant_1):
        assert client_prop.get(self.URL).status_code == 400

    def test_proprietario_vede_il_fascicolo_indicato(self, client_prop, tenant_1):
        TenantDocument.objects.create(
            tenant=tenant_1, tipo="carta_identita", file=_pdf_finto()
        )
        resp = client_prop.get(f"{self.URL}?tenant={tenant_1.id}")
        assert resp.status_code == 200
        assert resp.json()["tenant_nominativo"] == tenant_1.nominativo
        assert self._voci(resp)["carta_identita"]["stato"] == "ok"

    def test_proprietario_non_accede_ad_altro_immobile(
        self, client_prop, immobile2, user_inq_2
    ):
        estraneo = TenantProfile.objects.create(
            user=user_inq_2,
            property=immobile2,
            nominativo="Estraneo",
            giorno_pagamento_affitto=1,
        )
        assert client_prop.get(f"{self.URL}?tenant={estraneo.id}").status_code == 404

    def test_anonimo_non_autorizzato(self, tenant_1):
        assert APIClient().get(self.URL).status_code in (401, 403)


# ---------------------------------------------------------------------------
# Test PropertyDocumentViewSet
# ---------------------------------------------------------------------------


class TestPropertyDocumentViewSet:
    @pytest.fixture(autouse=True)
    def _media_tmp(self, settings, tmp_path):
        # I file caricati nei test finiscono in una dir temporanea, non in media/.
        settings.MEDIA_ROOT = str(tmp_path)

    def test_proprietario_carica_documento(self, client_prop, user_prop, immobile):
        resp = client_prop.post(
            "/api/v1/property-documents/",
            {"tipo": "contratto", "file": _pdf_finto(), "descrizione": "2024"},
            format="multipart",
        )
        assert resp.status_code == 201, resp.content
        doc = PropertyDocument.objects.get(id=resp.json()["id"])
        # property forzata all'immobile attivo, caricato_da tracciato
        assert doc.property_id == immobile.id
        assert doc.caricato_da_id == user_prop.id

    def test_lista_filtrata_su_immobile_attivo(
        self, client_prop, immobile, immobile2
    ):
        PropertyDocument.objects.create(
            property=immobile, tipo="contratto", file=_pdf_finto()
        )
        PropertyDocument.objects.create(
            property=immobile2, tipo="contratto", file=_pdf_finto()
        )
        resp = client_prop.get("/api/v1/property-documents/")
        assert resp.status_code == 200
        assert {d["property"] for d in resp.json()} == {immobile.id}

    def test_proprietario_elimina(self, client_prop, immobile):
        doc = PropertyDocument.objects.create(
            property=immobile, tipo="regolamento_condominiale", file=_pdf_finto()
        )
        resp = client_prop.delete(f"/api/v1/property-documents/{doc.id}/")
        assert resp.status_code == 204
        assert not PropertyDocument.objects.filter(id=doc.id).exists()

    def test_inquilino_vede_solo_documenti_condivisi(
        self, client_inq_1, tenant_1, immobile, immobile2
    ):
        condiviso = PropertyDocument.objects.create(
            property=immobile,
            tipo="regolamento_condominiale",
            file=_pdf_finto(),
            visibile_inquilini=True,
        )
        # Non condiviso: resta riservato al lato gestione.
        PropertyDocument.objects.create(
            property=immobile, tipo="side_letter", file=_pdf_finto()
        )
        # Condiviso ma di un altro immobile: invisibile.
        PropertyDocument.objects.create(
            property=immobile2,
            tipo="contratto",
            file=_pdf_finto(),
            visibile_inquilini=True,
        )
        resp = client_inq_1.get("/api/v1/property-documents/")
        assert resp.status_code == 200
        assert [d["id"] for d in resp.json()] == [condiviso.id]

    def test_inquilino_non_scrive(self, client_inq_1, tenant_1, immobile):
        doc = PropertyDocument.objects.create(
            property=immobile,
            tipo="contratto",
            file=_pdf_finto(),
            visibile_inquilini=True,
        )
        resp = client_inq_1.post(
            "/api/v1/property-documents/",
            {"tipo": "contratto", "file": _pdf_finto()},
            format="multipart",
        )
        assert resp.status_code in (403, 404)
        resp = client_inq_1.delete(f"/api/v1/property-documents/{doc.id}/")
        assert resp.status_code in (403, 404)
        assert PropertyDocument.objects.filter(id=doc.id).exists()

    def test_sola_lettura_legge_ma_non_scrive(self, api_client, immobile, gruppo_proprietari):
        u = User.objects.create_user("solalettura", password="pwd123!")
        u.groups.add(gruppo_proprietari)
        PropertyMembership.objects.create(
            property=immobile, user=u, ruolo=PropertyMembership.Ruolo.SOLA_LETTURA,
        )
        api_client.force_login(u)
        assert api_client.get("/api/v1/property-documents/").status_code == 200
        resp = api_client.post(
            "/api/v1/property-documents/",
            {"tipo": "contratto", "file": _pdf_finto()},
            format="multipart",
        )
        assert resp.status_code == 403

    def test_anonimo_non_autorizzato(self, immobile):
        client = APIClient()
        resp = client.get("/api/v1/property-documents/")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Test action RoomAssignmentViewSet.prima_assegnazione
# ---------------------------------------------------------------------------


class TestPrimaAssegnazioneAPI:
    URL = "/api/v1/room-assignments/prima-assegnazione/"

    def _payload(self, tenant_id, room_id, **overrides):
        payload = {
            "tenant": tenant_id,
            "room": room_id,
            "valid_from": "2026-08-01",
            "canone_mensile": "450.00",
            "ciclo_fatturazione": "solare",
        }
        payload.update(overrides)
        return payload

    def test_happy_path_3_rate(self, client_prop, tenant_2, room_2):
        from billing.models import Receivable

        payload = self._payload(
            tenant_2.id,
            room_2.id,
            deposito_totale="900.00",
            rate_deposito=[
                {"importo": "300.00", "scadenza": "2026-08-01"},
                {"importo": "300.00", "scadenza": "2026-09-01"},
                {"importo": "300.00", "scadenza": "2026-10-01"},
            ],
        )
        resp = client_prop.post(self.URL, payload, format="json")
        assert resp.status_code == 201, resp.content
        data = resp.json()
        assert len(data["rate_deposito_ids"]) == 3

        recs = Receivable.objects.filter(
            assignment__tenant=tenant_2,
            causale=Receivable.Causale.DEPOSITO,
            importo_dovuto__gt=0,
        )
        # Esattamente 3 rate: il signal non ne aggiunge una quarta.
        assert recs.count() == 3
        assert sum((r.importo_dovuto for r in recs), Decimal("0")) == Decimal("900.00")

        tenant_2.refresh_from_db()
        assert tenant_2.ciclo_fatturazione == "solare"
        assert tenant_2.deposito_versato == Decimal("900.00")

        # Primo addebito affitto: mese di ingresso (agosto, intero) generato
        # contestualmente. valid_from 2026-08-01 → canone pieno, no pro-rata.
        affitti = Receivable.objects.filter(
            assignment__tenant=tenant_2, causale=Receivable.Causale.AFFITTO
        )
        assert affitti.count() == 1
        assert affitti[0].importo_dovuto == Decimal("450.00")
        assert affitti[0].id in data["rent_receivable_ids"]

    def test_primo_affitto_pro_rata_meta_mese(self, client_prop, tenant_2, room_2):
        """Ingresso a metà mese, ciclo solare: il primo addebito copre la
        parte finale del mese in pro-rata giorni."""
        import calendar

        from billing.models import Receivable

        oggi = datetime.date.today()
        n_giorni = calendar.monthrange(oggi.year, oggi.month)[1]
        payload = self._payload(
            tenant_2.id, room_2.id, valid_from=oggi.isoformat()
        )
        resp = client_prop.post(self.URL, payload, format="json")
        assert resp.status_code == 201, resp.content

        affitti = Receivable.objects.filter(
            assignment__tenant=tenant_2, causale=Receivable.Causale.AFFITTO
        )
        assert affitti.count() == 1
        rec = affitti[0]
        giorni = n_giorni - oggi.day + 1
        atteso = (Decimal("450.00") * giorni / n_giorni).quantize(Decimal("0.01"))
        if giorni == n_giorni:
            assert rec.importo_dovuto == Decimal("450.00")
        else:
            assert rec.is_aggiustamento is True
            assert rec.importo_dovuto == atteso
        assert rec.competenza_da == oggi
        # La scadenza non precede mai l'ingresso (clamp per metà mese).
        assert rec.scadenza >= oggi

    def test_primo_affitto_include_quota_specifica(
        self, client_prop, tenant_2, room_2, contract
    ):
        """La quota condominio specifica creata dall'azione entra già nel
        primo canone generato (70, non la generica 90)."""
        from billing.models import Receivable, TenantCondominioRate

        TenantCondominioRate.objects.create(
            contract=contract,
            valid_from=datetime.date(2024, 1, 1),
            importo_mensile=Decimal("90.00"),
        )
        payload = self._payload(
            tenant_2.id, room_2.id, quota_condominio_mensile="70.00"
        )
        resp = client_prop.post(self.URL, payload, format="json")
        assert resp.status_code == 201, resp.content

        rec = Receivable.objects.get(
            assignment__tenant=tenant_2, causale=Receivable.Causale.AFFITTO
        )
        # Mese intero (2026-08-01): 450 canone + 70 quota specifica.
        assert rec.importo_dovuto == Decimal("520.00")

    def test_rate_non_sommano_400_e_niente_creato(self, client_prop, tenant_2, room_2):
        from billing.models import Receivable

        payload = self._payload(
            tenant_2.id,
            room_2.id,
            deposito_totale="900.00",
            rate_deposito=[
                {"importo": "300.00", "scadenza": "2026-08-01"},
                {"importo": "300.00", "scadenza": "2026-09-01"},
            ],
        )
        resp = client_prop.post(self.URL, payload, format="json")
        assert resp.status_code == 400
        assert not RoomAssignment.objects.filter(tenant=tenant_2).exists()
        assert not Receivable.objects.filter(assignment__tenant=tenant_2).exists()
        tenant_2.refresh_from_db()
        assert tenant_2.deposito_versato == Decimal("0")

    def test_tenant_con_assignment_in_corso_400(
        self, client_prop, tenant_2, room_2, assignment_2
    ):
        payload = self._payload(tenant_2.id, room_2.id)
        resp = client_prop.post(self.URL, payload, format="json")
        assert resp.status_code == 400
        assert "tenant" in resp.json()

    def test_room_di_altra_property_400(self, client_prop, tenant_2, immobile2):
        altra_room = Room.objects.create(
            property=immobile2, nome="Camera altra property", ordinamento=1
        )
        payload = self._payload(tenant_2.id, altra_room.id)
        resp = client_prop.post(self.URL, payload, format="json")
        assert resp.status_code == 400
        assert "room" in resp.json()

    def test_overlap_stanza_occupata_400_rollback(
        self, client_prop, tenant_2, room_1, assignment_1
    ):
        # room_1 è già occupata (assignment_1, aperta dal 2024-09-01).
        payload = self._payload(tenant_2.id, room_1.id, ciclo_fatturazione="ingresso")
        resp = client_prop.post(self.URL, payload, format="json")
        assert resp.status_code == 400
        assert not RoomAssignment.objects.filter(tenant=tenant_2).exists()
        # Rollback: anche il ciclo_fatturazione salvato prima dell'errore
        # deve tornare indietro (transazione atomica).
        tenant_2.refresh_from_db()
        assert tenant_2.ciclo_fatturazione == "solare"

    def test_quota_diversa_dalla_generica_crea_specifica(
        self, client_prop, tenant_2, room_2, contract
    ):
        from billing.models import TenantCondominioRate

        TenantCondominioRate.objects.create(
            contract=contract,
            valid_from=datetime.date(2024, 1, 1),
            importo_mensile=Decimal("90.00"),
        )
        payload = self._payload(
            tenant_2.id, room_2.id, quota_condominio_mensile="70.00"
        )
        resp = client_prop.post(self.URL, payload, format="json")
        assert resp.status_code == 201, resp.content
        assert resp.json()["quota_condominio_creata"] is True
        rata = TenantCondominioRate.objects.get(tenant=tenant_2)
        assert rata.importo_mensile == Decimal("70.00")
        assert rata.valid_from == datetime.date(2026, 8, 1)
        assert rata.contract_id == contract.id

    def test_quota_uguale_alla_generica_non_crea_riga(
        self, client_prop, tenant_2, room_2, contract
    ):
        from billing.models import TenantCondominioRate

        TenantCondominioRate.objects.create(
            contract=contract,
            valid_from=datetime.date(2024, 1, 1),
            importo_mensile=Decimal("90.00"),
        )
        payload = self._payload(
            tenant_2.id, room_2.id, quota_condominio_mensile="90.00"
        )
        resp = client_prop.post(self.URL, payload, format="json")
        assert resp.status_code == 201, resp.content
        assert resp.json()["quota_condominio_creata"] is False
        assert not TenantCondominioRate.objects.filter(tenant=tenant_2).exists()

    def test_quota_senza_contratto_attivo_ok(self, client_prop, tenant_2, room_2):
        """Immobile appena creato, nessun contratto ancora registrato: la
        quota condominio si registra lo stesso, sull'immobile."""
        from billing.models import Receivable, TenantCondominioRate

        payload = self._payload(
            tenant_2.id,
            room_2.id,
            canone_mensile="600.00",
            quota_condominio_mensile="100.00",
        )
        resp = client_prop.post(self.URL, payload, format="json")
        assert resp.status_code == 201, resp.content
        assert resp.json()["quota_condominio_creata"] is True

        rata = TenantCondominioRate.objects.get(tenant=tenant_2)
        assert rata.property_id == room_2.property_id
        assert rata.contract_id is None
        assert rata.importo_mensile == Decimal("100.00")

        # E finisce nel canone: 600 di affitto + 100 di quota.
        affitto = Receivable.objects.filter(
            assignment__tenant=tenant_2, causale=Receivable.Causale.AFFITTO
        ).first()
        assert affitto is not None
        assert affitto.importo_dovuto == Decimal("700.00")

    def test_deposito_gia_esistente_con_payload_deposito_400(
        self, client_prop, tenant_2, room_2
    ):
        tenant_2.deposito_versato = Decimal("500.00")
        tenant_2.save()
        payload = self._payload(tenant_2.id, room_2.id, deposito_totale="900.00")
        resp = client_prop.post(self.URL, payload, format="json")
        assert resp.status_code == 400
        assert "deposito_totale" in resp.json()

    def test_deposito_gia_esistente_senza_payload_deposito_201(
        self, client_prop, tenant_2, room_2
    ):
        tenant_2.deposito_versato = Decimal("500.00")
        tenant_2.save()
        payload = self._payload(tenant_2.id, room_2.id)
        resp = client_prop.post(self.URL, payload, format="json")
        assert resp.status_code == 201, resp.content

    def test_utente_inquilino_403(self, client_inq_1, tenant_2, room_2):
        payload = self._payload(tenant_2.id, room_2.id)
        resp = client_inq_1.post(self.URL, payload, format="json")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Test action RoomAssignmentViewSet.rigenera_receivable
# ---------------------------------------------------------------------------


def _primo_mese_fa(delta_mesi: int) -> datetime.date:
    """Primo giorno del mese, ``delta_mesi`` mesi prima di oggi."""
    oggi = datetime.date.today()
    anno, mese = oggi.year, oggi.month - delta_mesi
    while mese <= 0:
        mese += 12
        anno -= 1
    return datetime.date(anno, mese, 1)


class TestRigeneraReceivableAPI:
    """Correzione assignment (canone/valid_from sbagliati) + rigenerazione
    degli addebiti AFFITTO non incassati."""

    def _url(self, assignment_id):
        return f"/api/v1/room-assignments/{assignment_id}/rigenera-receivable/"

    @pytest.fixture
    def assignment_corr(self, db, room_1, tenant_1):
        """Assegnazione dal 1° del mese, due mesi fa: la finestra di
        rigenerazione resta piccola e deterministica (3 mesi)."""
        return RoomAssignment.objects.create(
            room=room_1,
            tenant=tenant_1,
            valid_from=_primo_mese_fa(2),
            canone_mensile=Decimal("600.00"),
        )

    def _genera_mesi(self, assignment) -> list[int]:
        """Genera gli addebiti AFFITTO da valid_from al mese corrente
        (come farebbe la prima assegnazione)."""
        from billing.calc.rent import genera_pagamenti_mese

        ids: list[int] = []
        cursore = assignment.valid_from.replace(day=1)
        fine = datetime.date.today().replace(day=1)
        while cursore <= fine:
            esito = genera_pagamenti_mese(
                cursore.year,
                cursore.month,
                tenant_id=assignment.tenant_id,
                property=assignment.room.property,
            )
            ids.extend(esito["payments"])
            cursore = (
                cursore.replace(year=cursore.year + 1, month=1)
                if cursore.month == 12
                else cursore.replace(month=cursore.month + 1)
            )
        return ids

    def _affitti(self, assignment):
        from billing.models import Receivable

        return Receivable.objects.filter(
            assignment=assignment, causale=Receivable.Causale.AFFITTO
        ).order_by("competenza_da")

    def test_cambio_canone_aggiorna_receivable_esistenti(
        self, client_prop, assignment_corr
    ):
        """Il caso reale: canone inserito a 600 invece di 700. PATCH del
        canone + rigenera → tutti gli addebiti liberi passano a 700."""
        assert len(self._genera_mesi(assignment_corr)) == 3

        resp = client_prop.patch(
            f"/api/v1/room-assignments/{assignment_corr.id}/",
            {"canone_mensile": "700.00"},
            format="json",
        )
        assert resp.status_code == 200, resp.content

        resp = client_prop.post(self._url(assignment_corr.id))
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data["aggiornati"] == 3
        assert data["creati"] == 0
        assert data["eliminati"] == 0
        assert data["skippati_per_allocation"] == 0

        importi = [r.importo_dovuto for r in self._affitti(assignment_corr)]
        assert len(importi) == 3
        assert all(i == Decimal("700.00") for i in importi)

    def test_receivable_con_allocation_non_toccato(
        self, client_prop, assignment_corr, bank_account
    ):
        """Guardia allocations: l'addebito già incassato resta al vecchio
        importo e viene contato in skippati_per_allocation."""
        from billing.models import BankTransaction, BankTransactionAllocation

        self._genera_mesi(assignment_corr)
        primo = self._affitti(assignment_corr).first()
        bt = BankTransaction.objects.create(
            data=primo.competenza_da,
            descrizione="Bonifico affitto",
            importo=Decimal("600.00"),
            owner_account=bank_account,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=primo, importo=Decimal("600.00")
        )

        resp = client_prop.patch(
            f"/api/v1/room-assignments/{assignment_corr.id}/",
            {"canone_mensile": "700.00"},
            format="json",
        )
        assert resp.status_code == 200, resp.content

        resp = client_prop.post(self._url(assignment_corr.id))
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data["skippati_per_allocation"] == 1
        assert data["aggiornati"] == 2
        assert data["eliminati"] == 0

        primo.refresh_from_db()
        assert primo.importo_dovuto == Decimal("600.00")
        altri = self._affitti(assignment_corr).exclude(pk=primo.pk)
        assert all(r.importo_dovuto == Decimal("700.00") for r in altri)

    def test_valid_from_spostato_avanti_pro_rata_senza_orfani(
        self, client_prop, assignment_corr
    ):
        """Spostando l'inizio dal 1 al 15, il mese d'ingresso diventa un
        pro-rata e il vecchio addebito a mese pieno viene eliminato."""
        import calendar
        from decimal import ROUND_HALF_UP

        self._genera_mesi(assignment_corr)
        nuovo_inizio = assignment_corr.valid_from.replace(day=15)

        resp = client_prop.patch(
            f"/api/v1/room-assignments/{assignment_corr.id}/",
            {"valid_from": nuovo_inizio.isoformat()},
            format="json",
        )
        assert resp.status_code == 200, resp.content

        resp = client_prop.post(self._url(assignment_corr.id))
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data["creati"] == 1  # il nuovo pro-rata del mese d'ingresso
        assert data["aggiornati"] == 2  # i mesi pieni successivi
        assert data["eliminati"] == 1  # il vecchio mese d'ingresso intero
        assert data["skippati_per_allocation"] == 0

        qs = self._affitti(assignment_corr)
        assert qs.count() == 3
        # Nessun orfano prima del nuovo inizio.
        assert not qs.filter(competenza_da__lt=nuovo_inizio).exists()

        rec = qs.first()
        assert rec.competenza_da == nuovo_inizio
        assert rec.is_aggiustamento is True
        n_giorni = calendar.monthrange(nuovo_inizio.year, nuovo_inizio.month)[1]
        giorni = n_giorni - nuovo_inizio.day + 1
        atteso = (Decimal("600.00") * giorni / n_giorni).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert rec.importo_dovuto == atteso

    def test_quota_condominio_inclusa(
        self, client_prop, assignment_corr, immobile
    ):
        """Con una TenantCondominioRate valida sull'immobile, l'importo
        rigenerato è canone + quota (il caso reale 600 → 700)."""
        from billing.models import TenantCondominioRate

        self._genera_mesi(assignment_corr)
        importi = [r.importo_dovuto for r in self._affitti(assignment_corr)]
        assert all(i == Decimal("600.00") for i in importi)

        TenantCondominioRate.objects.create(
            property=immobile,
            valid_from=datetime.date(2024, 1, 1),
            importo_mensile=Decimal("100.00"),
        )

        resp = client_prop.post(self._url(assignment_corr.id))
        assert resp.status_code == 200, resp.content
        assert resp.json()["aggiornati"] == 3

        importi = [r.importo_dovuto for r in self._affitti(assignment_corr)]
        assert all(i == Decimal("700.00") for i in importi)

    def test_inquilino_non_autorizzato(self, client_inq_1, assignment_corr):
        resp = client_inq_1.post(self._url(assignment_corr.id))
        assert resp.status_code in (403, 404)
        importi = [r.importo_dovuto for r in self._affitti(assignment_corr)]
        assert importi == []  # nessuna generazione avvenuta
