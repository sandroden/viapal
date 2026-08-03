"""
Test dell'API di generazione documenti
(``POST /api/v1/tenant-documents/genera/``) e delle sue ricadute sul
fascicolo.

La regressione da non perdere mai: rigenerare non deve cancellare la copia
firmata che qualcuno ha caricato a mano sotto lo stesso tipo.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from rest_framework.test import APIClient

from billing.models import Receivable, TenantCondominioRate
from properties.documenti import esempio
from properties.models import (
    Contract,
    DocumentTemplate,
    OwnerProfile,
    OwnershipShare,
    PropertyMembership,
    Room,
    RoomAssignment,
    TenantDocument,
    TenantProfile,
)

pytestmark = pytest.mark.django_db

URL = "/api/v1/tenant-documents/genera/"
FASCICOLO = "/api/v1/tenant-documents/fascicolo/"
ATTO = "atto_subentro_locazione"
CESSIONE = "cessione_fabbricato"
INGRESSO = datetime.date(2026, 7, 22)

ANAGRAFICA = {
    "data_nascita": datetime.date(1990, 3, 12),
    "comune_nascita": "Monza",
    "provincia_nascita": "MB",
    "cittadinanza": "italiana",
    "residenza_via": "Via Palestrina 20",
    "residenza_comune": "Monza",
    "residenza_provincia": "MB",
    "residenza_cap": "20900",
    "telefono": "3331234567",
    "codice_fiscale": "RSSMRA90C12F704X",
}

DOCUMENTO = {
    "documento_tipo": TenantProfile.TipoDocumento.CARTA_IDENTITA,
    "documento_numero": "CA72894HS",
    "documento_autorita": "Ministero dell'Interno",
    "documento_data_rilascio": datetime.date(2024, 3, 22),
}


@pytest.fixture(autouse=True)
def _media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.MEDIA_PRIVATE_ROOT = str(tmp_path / "media-private")


def _client(user):
    c = APIClient(enforce_csrf_checks=False)
    c.force_login(user)
    return c


def _persona(modello, nominativo, **extra):
    cognome, _, nome = nominativo.partition(" ")
    return modello.objects.create(
        user=User.objects.create_user(
            username=nominativo.lower().replace(" ", "-"),
            email=f"{nominativo.replace(' ', '.')}@example.com",
        ),
        nominativo=nominativo,
        cognome=cognome,
        nome=nome,
        **ANAGRAFICA,
        **extra,
    )


@pytest.fixture
def mondo(immobile):
    """Immobile completo: due comproprietari, contratto registrato,
    un uscente e un subentrante con anagrafica piena."""
    for campo, valore in {
        "via": "Palestrina", "civico": "20", "cap": "20900", "comune": "Monza",
        "provincia": "MB", "piano": "2", "vani": "5",
    }.items():
        setattr(immobile, campo, valore)
    proprietario = _persona(OwnerProfile, "Dentella Alessandro")
    immobile.owner_firmatario = proprietario
    immobile.save()
    OwnershipShare.objects.create(
        property=immobile, owner=proprietario,
        valid_from=datetime.date(2020, 1, 1), quota=Decimal("1"),
    )
    contratto = Contract.objects.create(
        property=immobile,
        data_stipula=datetime.date(2025, 2, 20),
        data_decorrenza=datetime.date(2025, 2, 20),
        durata_anni=4,
        ufficio_registrazione="Desio",
        data_registrazione=datetime.date(2025, 3, 20),
        numero_registrazione="002272",
        serie_registrazione="3T",
        codice_identificativo="TM325T002272000SJ",
    )
    TenantCondominioRate.objects.create(
        contract=contratto, valid_from=datetime.date(2025, 1, 1),
        importo_mensile=Decimal("70"),
    )
    stanza = Room.objects.create(property=immobile, nome="Camera 2", ordinamento=1)
    uscente = _persona(
        TenantProfile, "Di Maio Davide", property=immobile,
        giorno_pagamento_affitto=5,
    )
    vecchia = RoomAssignment.objects.create(
        room=stanza, tenant=uscente,
        valid_from=datetime.date(2025, 2, 20),
        valid_to=datetime.date(2026, 6, 30),
        canone_mensile=Decimal("400"),
    )
    tenant = _persona(
        TenantProfile, "Bouchane Oussama", property=immobile,
        giorno_pagamento_affitto=5, **DOCUMENTO,
    )
    assegnazione = RoomAssignment.objects.create(
        room=stanza, tenant=tenant, valid_from=INGRESSO,
        canone_mensile=Decimal("400"), subentra_a=vecchia,
    )
    Receivable.objects.create(
        assignment=assegnazione,
        causale=Receivable.Causale.DEPOSITO,
        competenza_da=INGRESSO, competenza_a=INGRESSO,
        importo_dovuto=Decimal("800"), scadenza=INGRESSO,
    )
    for codice in (ATTO, CESSIONE):
        DocumentTemplate.objects.create(
            property=immobile, codice=codice, corpo_html=esempio(codice)
        )
    return {
        "immobile": immobile, "tenant": tenant, "uscente": uscente,
        "assegnazione": assegnazione, "stanza": stanza,
    }


def _membro(immobile, username, ruolo=PropertyMembership.Ruolo.PROPRIETARIO):
    user = User.objects.create_user(username=username)
    PropertyMembership.objects.create(property=immobile, user=user, ruolo=ruolo)
    return user


@pytest.fixture
def client_prop(mondo):
    return _client(_membro(mondo["immobile"], "prop"))


@pytest.fixture
def client_sola_lettura(mondo):
    return _client(
        _membro(mondo["immobile"], "lettore", PropertyMembership.Ruolo.SOLA_LETTURA)
    )


@pytest.fixture
def client_inq(mondo):
    user = mondo["tenant"].user
    gruppo, _ = Group.objects.get_or_create(name="inquilini")
    user.groups.add(gruppo)
    return _client(user)


def _payload(mondo, documento=ATTO, **extra):
    return {"tenant": mondo["tenant"].pk, "documento": documento, **extra}


# ---------------------------------------------------------------------------
# Anteprima
# ---------------------------------------------------------------------------


class TestAnteprima:
    def test_dry_run_non_crea_nulla(self, client_prop, mondo):
        resp = client_prop.post(URL, _payload(mondo), format="json")
        assert resp.status_code == 200, resp.content
        assert resp.json()["completo"] is True
        assert TenantDocument.objects.count() == 0

    def test_dry_run_e_il_default(self, client_prop, mondo):
        client_prop.post(URL, _payload(mondo), format="json")
        assert TenantDocument.objects.count() == 0

    def test_elenca_i_mancanti(self, client_prop, mondo):
        tenant = mondo["tenant"]
        tenant.data_nascita = None
        tenant.save()
        dati = client_prop.post(URL, _payload(mondo), format="json").json()
        assert dati["completo"] is False
        assert "subentrante_data_nascita" in {m["campo"] for m in dati["mancanti"]}

    def test_documento_sconosciuto_400(self, client_prop, mondo):
        resp = client_prop.post(
            URL, _payload(mondo, documento="pergamena"), format="json"
        )
        assert resp.status_code == 400
        assert "documento" in resp.json()

    def test_tenant_mancante_400(self, client_prop):
        resp = client_prop.post(URL, {"documento": ATTO}, format="json")
        assert resp.status_code == 400

    def test_inquilino_senza_assegnazioni_400(self, client_prop, mondo):
        orfano = _persona(
            TenantProfile, "Senza Stanza", property=mondo["immobile"],
            giorno_pagamento_affitto=5,
        )
        resp = client_prop.post(
            URL, {"tenant": orfano.pk, "documento": ATTO}, format="json"
        )
        assert resp.status_code == 400
        assert "assegnazioni" in str(resp.json()["detail"])


# ---------------------------------------------------------------------------
# Generazione
# ---------------------------------------------------------------------------


class TestGenerazione:
    def _genera(self, client, mondo, documento=ATTO):
        return client.post(
            URL, _payload(mondo, documento, dry_run=False), format="json"
        )

    def test_crea_un_tenant_document(self, client_prop, mondo):
        resp = self._genera(client_prop, mondo)
        assert resp.status_code == 201, resp.content
        documento = TenantDocument.objects.get()
        assert documento.tipo == ATTO
        assert documento.generato is True
        assert documento.tenant == mondo["tenant"]
        assert documento.caricato_da.username == "prop"
        assert documento.file.name.endswith(".pdf")
        assert documento.descrizione.startswith("generato il ")
        assert resp.json()["sostituito"] is None

    def test_dati_incompleti_400_con_elenco(self, client_prop, mondo):
        tenant = mondo["tenant"]
        tenant.cognome = ""
        tenant.save()
        resp = self._genera(client_prop, mondo)
        assert resp.status_code == 400
        assert resp.json()["mancanti"]
        assert TenantDocument.objects.count() == 0

    def test_modello_non_caricato_400(self, client_prop, mondo):
        DocumentTemplate.objects.filter(codice=ATTO).delete()
        resp = self._genera(client_prop, mondo)
        assert resp.status_code == 400
        assert "modello" in {m["campo"] for m in resp.json()["mancanti"]}

    def test_rigenerazione_sostituisce(self, client_prop, mondo):
        primo = self._genera(client_prop, mondo).json()
        secondo = self._genera(client_prop, mondo)
        assert secondo.status_code == 201
        assert secondo.json()["sostituito"] == primo["id"]
        assert TenantDocument.objects.filter(tipo=ATTO).count() == 1

    def test_rigenerazione_non_tocca_la_scansione_firmata(self, client_prop, mondo):
        """Genera → stampa → firma → scansiona → ricarica: un 'Rigenera'
        non deve distruggere l'unico originale firmato."""
        self._genera(client_prop, mondo)
        firmato = TenantDocument.objects.create(
            tenant=mondo["tenant"],
            tipo=ATTO,
            descrizione="firmato",
            file=ContentFile(b"%PDF-1.4 scansione", name="firmato.pdf"),
        )
        self._genera(client_prop, mondo)
        firmato.refresh_from_db()
        assert firmato.generato is False
        assert TenantDocument.objects.filter(tipo=ATTO).count() == 2

    def test_anteprima_segnala_il_documento_gia_generato(self, client_prop, mondo):
        creato = self._genera(client_prop, mondo).json()
        dati = client_prop.post(URL, _payload(mondo), format="json").json()
        assert dati["esistente"]["id"] == creato["id"]

    def test_cessione_fabbricato(self, client_prop, mondo):
        resp = self._genera(client_prop, mondo, CESSIONE)
        assert resp.status_code == 201, resp.content
        assert TenantDocument.objects.get().tipo == CESSIONE


# ---------------------------------------------------------------------------
# Permessi e isolamento
# ---------------------------------------------------------------------------


class TestPermessi:
    def test_sola_lettura_403(self, client_sola_lettura, mondo):
        resp = client_sola_lettura.post(URL, _payload(mondo), format="json")
        assert resp.status_code == 403

    def test_inquilino_403(self, client_inq, mondo):
        resp = client_inq.post(URL, _payload(mondo), format="json")
        assert resp.status_code == 403

    def test_inquilino_di_altro_immobile_404(self, client_prop, immobile2):
        estraneo = _persona(
            TenantProfile, "Altro Inquilino", property=immobile2,
            giorno_pagamento_affitto=5,
        )
        resp = client_prop.post(
            URL, {"tenant": estraneo.pk, "documento": ATTO}, format="json"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Ricadute sul fascicolo
# ---------------------------------------------------------------------------


class TestFascicoloDopoGenerazione:
    def _voci(self, client, tenant):
        resp = client.get(FASCICOLO, {"tenant": tenant.pk})
        return {v["tipo"]: v for v in resp.json()["voci"]}

    def test_voce_da_attesa_a_ok(self, client_prop, mondo):
        voci = self._voci(client_prop, mondo["tenant"])
        assert voci[ATTO]["stato"] == "attesa"
        assert voci[ATTO]["generabile"] == ATTO
        client_prop.post(URL, _payload(mondo, dry_run=False), format="json")
        voci = self._voci(client_prop, mondo["tenant"])
        assert voci[ATTO]["stato"] == "ok"
        assert len(voci[ATTO]["pagine"]) == 1

    def test_atto_di_subentro_assente_senza_subentro(self, client_prop, mondo):
        """Chi non è subentrato a nessuno non deve vedere per sempre una
        voce in attesa di un atto che non esisterà mai."""
        assegnazione = mondo["assegnazione"]
        assegnazione.subentra_a = None
        assegnazione.save()
        voci = self._voci(client_prop, mondo["tenant"])
        assert ATTO not in voci
        assert CESSIONE in voci

    def test_atto_caricato_a_mano_compare_comunque(self, client_prop, mondo):
        """Se il file esiste va mostrato, anche se la voce non si
        applicherebbe: un documento caricato non si nasconde."""
        assegnazione = mondo["assegnazione"]
        assegnazione.subentra_a = None
        assegnazione.save()
        TenantDocument.objects.create(
            tenant=mondo["tenant"], tipo=ATTO,
            file=ContentFile(b"%PDF-1.4", name="atto.pdf"),
        )
        assert ATTO in self._voci(client_prop, mondo["tenant"])


# ---------------------------------------------------------------------------
# Fusione dei due tipi "ricevuta"
# ---------------------------------------------------------------------------


class TestFusioneRicevuteSubentro:
    """La 0032 fonde ``ricevuta_subentro`` in ``ricevuta_registrazione``.

    In locale non esistono righe del vecchio tipo: senza questo test la
    migrazione girerebbe per la prima volta in produzione senza essere mai
    stata eseguita su dati reali.
    """

    def _funzione_di_migrazione(self):
        import importlib

        modulo = importlib.import_module(
            "properties.migrations.0032_fonde_ricevuta_subentro"
        )
        return modulo.fonde_ricevuta_subentro

    def test_rimappa_il_vecchio_tipo(self, mondo):
        from django.apps import apps as django_apps

        doc = TenantDocument.objects.create(
            tenant=mondo["tenant"],
            tipo="altro",
            file=ContentFile(b"%PDF-1.4", name="ricevuta.pdf"),
        )
        # Il vecchio valore non è più fra le choices: si scrive aggirando il
        # modello, come farebbe una riga già presente nel database.
        TenantDocument.objects.filter(pk=doc.pk).update(tipo="ricevuta_subentro")

        self._funzione_di_migrazione()(django_apps, None)

        doc.refresh_from_db()
        assert doc.tipo == "ricevuta_registrazione"

    def test_non_tocca_gli_altri_tipi(self, mondo):
        from django.apps import apps as django_apps

        altro = TenantDocument.objects.create(
            tenant=mondo["tenant"],
            tipo=ATTO,
            file=ContentFile(b"%PDF-1.4", name="atto.pdf"),
        )
        self._funzione_di_migrazione()(django_apps, None)
        altro.refresh_from_db()
        assert altro.tipo == ATTO
