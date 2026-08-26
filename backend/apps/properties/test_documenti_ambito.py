"""Ambito dei documenti immobile: carta di un contratto o carta della casa.

``PropertyDocument.contract`` è nullable, ma non per tutti i tipi allo stesso
modo: contratto, side letter e ricevuta di registrazione *sono* la carta di
un contratto e senza quel collegamento finiscono fra i documenti generali,
visibili agli inquilini di ogni contratto. Regolamento e regole di convivenza
valgono invece per la casa e il contratto resta facoltativo.

La regola sta in ``PropertyDocument.valida_ambito`` ed è applicata due volte —
``clean()`` per l'admin, ``validate()`` del serializer per l'API — perché i
due percorsi di scrittura non passano l'uno per l'altro.
"""
import datetime

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from rest_framework.test import APIClient

from properties.models import Contract, PropertyDocument, PropertyMembership

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4 contenuto di test"
URL = "/api/v1/property-documents/"


@pytest.fixture(autouse=True)
def media_private_tmp(settings, tmp_path):
    settings.MEDIA_PRIVATE_ROOT = str(tmp_path / "media-private")
    settings.MEDIA_ROOT = str(tmp_path / "media")


@pytest.fixture
def contratto(immobile):
    return Contract.objects.create(
        property=immobile,
        nome="Collettivo 2025",
        data_stipula=datetime.date(2025, 2, 15),
        data_decorrenza=datetime.date(2025, 2, 15),
        durata_anni=4,
    )


@pytest.fixture
def api(immobile):
    proprietario = User.objects.create_user("prop-ambito")
    PropertyMembership.objects.create(
        property=immobile,
        user=proprietario,
        ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
    )
    c = APIClient(enforce_csrf_checks=False)
    c.force_login(proprietario)
    c.defaults["HTTP_X_PROPERTY_ID"] = str(immobile.pk)
    return c


def _crea(immobile, tipo, contract=None, nome="doc.pdf", descrizione=""):
    """Crea saltando la validazione: serve a fabbricare anche il malformato."""
    return PropertyDocument.objects.create(
        property=immobile,
        contract=contract,
        tipo=tipo,
        descrizione=descrizione,
        file=SimpleUploadedFile(nome, PDF),
    )


class TestValidazioneModello:
    def test_side_letter_senza_contratto_non_passa(self, immobile):
        doc = PropertyDocument(
            property=immobile,
            tipo=PropertyDocument.Tipo.SIDE_LETTER,
            file=SimpleUploadedFile("side.pdf", PDF),
        )
        with pytest.raises(ValidationError) as exc:
            doc.full_clean()
        assert "contract" in exc.value.message_dict

    def test_regolamento_senza_contratto_va_bene(self, immobile):
        doc = PropertyDocument(
            property=immobile,
            tipo=PropertyDocument.Tipo.REGOLAMENTO_CONDOMINIALE,
            file=SimpleUploadedFile("reg.pdf", PDF),
        )
        doc.full_clean()  # non solleva

    def test_regole_convivenza_sono_carta_della_casa(self, immobile):
        doc = PropertyDocument(
            property=immobile,
            tipo=PropertyDocument.Tipo.REGOLE_CONVIVENZA,
            file=SimpleUploadedFile("convivenza.pdf", PDF),
        )
        doc.full_clean()  # non solleva


class TestApi:
    def test_upload_contrattuale_senza_contratto_400(self, api):
        resp = api.post(
            URL,
            {
                "tipo": PropertyDocument.Tipo.SIDE_LETTER,
                "file": SimpleUploadedFile("side.pdf", PDF),
            },
            format="multipart",
        )
        assert resp.status_code == 400, resp.content
        assert "contract" in resp.json()

    def test_upload_carta_della_casa_senza_contratto_201(self, api):
        resp = api.post(
            URL,
            {
                "tipo": PropertyDocument.Tipo.REGOLE_CONVIVENZA,
                "file": SimpleUploadedFile("convivenza.pdf", PDF),
            },
            format="multipart",
        )
        assert resp.status_code == 201, resp.content

    def test_aggancia_il_contratto_dopo_il_caricamento(self, api, immobile, contratto):
        """Il buco che ha generato i doppioni: prima si poteva solo ricaricare."""
        doc = _crea(immobile, PropertyDocument.Tipo.REGOLE_CONVIVENZA)
        resp = api.patch(
            f"{URL}{doc.pk}/",
            {"tipo": PropertyDocument.Tipo.SIDE_LETTER, "contract": contratto.pk},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        doc.refresh_from_db()
        assert doc.contract_id == contratto.pk

    def test_stacca_il_contratto_da_una_carta_della_casa(self, api, immobile, contratto):
        doc = _crea(immobile, PropertyDocument.Tipo.REGOLE_CONVIVENZA, contract=contratto)
        resp = api.patch(f"{URL}{doc.pk}/", {"contract": None}, format="json")
        assert resp.status_code == 200, resp.content
        doc.refresh_from_db()
        assert doc.contract_id is None

    def test_staccare_il_contratto_da_una_side_letter_400(self, api, immobile, contratto):
        doc = _crea(immobile, PropertyDocument.Tipo.SIDE_LETTER, contract=contratto)
        resp = api.patch(f"{URL}{doc.pk}/", {"contract": None}, format="json")
        assert resp.status_code == 400, resp.content
        doc.refresh_from_db()
        assert doc.contract_id == contratto.pk

    def test_visibilita_su_documento_legacy_malformato_passa(self, api, immobile):
        """Un PATCH che non tocca l'ambito non deve fallire per un difetto
        che non ha introdotto: altrimenti i documenti già in archivio
        diventerebbero impossibili anche solo da nascondere."""
        doc = _crea(immobile, PropertyDocument.Tipo.SIDE_LETTER)  # senza contratto
        resp = api.patch(
            f"{URL}{doc.pk}/", {"visibile_inquilini": False}, format="json"
        )
        assert resp.status_code == 200, resp.content


class TestComandoSistemazione:
    def test_corregge_tipo_e_rimuove_il_doppione(self, immobile, contratto, capsys):
        buono = _crea(
            immobile,
            PropertyDocument.Tipo.ALTRO,
            contract=contratto,
            nome="lettera-accompagnamento.pdf",  # il secondo prende il suffisso
        )
        doppione = _crea(
            immobile,
            PropertyDocument.Tipo.SIDE_LETTER,
            nome="lettera-accompagnamento.pdf",
            descrizione="lettera accompagnamento",
        )
        # Django numera il secondo file caricato: il "buono" è quello col
        # suffisso solo se creato per secondo. Qui li rileggo per sapere chi
        # è chi, come fa il command.
        buono.refresh_from_db()
        doppione.refresh_from_db()
        if buono.file.name.endswith("lettera-accompagnamento.pdf"):
            buono, doppione = doppione, buono
            buono.contract = contratto
            buono.tipo = PropertyDocument.Tipo.ALTRO
            buono.save()
            doppione.contract = None
            doppione.tipo = PropertyDocument.Tipo.SIDE_LETTER
            doppione.descrizione = "lettera accompagnamento"
            doppione.save()

        call_command("sistema_documenti_immobile", "--apply")

        buono.refresh_from_db()
        assert buono.tipo == PropertyDocument.Tipo.SIDE_LETTER
        assert buono.descrizione == "lettera accompagnamento"  # travasata
        assert not PropertyDocument.objects.filter(pk=doppione.pk).exists()

    def test_idempotente(self, immobile, contratto):
        _crea(
            immobile,
            PropertyDocument.Tipo.ALTRO,
            nome="Regolamento_di_Convivenza_per_lAppartamento.pdf",
        )
        call_command("sistema_documenti_immobile", "--apply")
        call_command("sistema_documenti_immobile", "--apply")
        doc = PropertyDocument.objects.get(file__contains="Regolamento_di_Convivenza")
        assert doc.tipo == PropertyDocument.Tipo.REGOLE_CONVIVENZA

    def test_dry_run_non_scrive(self, immobile):
        doc = _crea(
            immobile,
            PropertyDocument.Tipo.ALTRO,
            nome="Regolamento_di_Convivenza_per_lAppartamento.pdf",
        )
        call_command("sistema_documenti_immobile")
        doc.refresh_from_db()
        assert doc.tipo == PropertyDocument.Tipo.ALTRO

    def test_segnala_i_visibili_che_nessuno_vede(self, immobile, contratto, capsys):
        """La spunta «visibile agli inquilini» su una carta di contratto non
        basta: se nessuna assegnazione è collegata a quel contratto, il
        documento resta invisibile e nulla lo direbbe."""
        doc = _crea(immobile, PropertyDocument.Tipo.CONTRATTO, contract=contratto)
        doc.visibile_inquilini = True
        doc.save()

        call_command("sistema_documenti_immobile")

        uscita = capsys.readouterr().out
        assert "invisibili" in uscita
        assert str(doc.pk) in uscita

    def test_non_tocca_un_documento_che_non_e_il_doppione(self, immobile, contratto):
        """Fail-safe: se il record col nome atteso è agganciato a un
        contratto non è il doppione, e il command lo salta."""
        doc = _crea(
            immobile,
            PropertyDocument.Tipo.CONTRATTO,
            contract=contratto,
            nome="contratto-2025-firmato.pdf",
        )
        call_command("sistema_documenti_immobile", "--apply")
        assert PropertyDocument.objects.filter(pk=doc.pk).exists()
