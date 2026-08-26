"""
Test del generatore di documenti (``properties.documenti``).

Due assi: la lista dei dati mancanti — che è il cuore della funzionalità,
perché dice all'utente *dove* andare a compilare — e il PDF prodotto, di
cui si verifica il contenuto reale con ``pdftotext`` (già usato dal parsing
delle bollette, nessuno strumento nuovo).
"""
import datetime
import subprocess
import tempfile
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from billing.models import Receivable, TenantCondominioRate
from properties.documenti import (
    DatiInsufficienti,
    anteprima,
    anteprima_facsimile,
    esempio,
    genera_facsimile,
    genera_pdf,
    segnaposto,
)
from properties.documenti.base import eur, raccogli_fonti
from properties.models import (
    Contract,
    DocumentTemplate,
    OwnerProfile,
    OwnershipShare,
    Room,
    RoomAssignment,
    TenantProfile,
)

pytestmark = pytest.mark.django_db

ATTO = DocumentTemplate.Codice.ATTO_SUBENTRO_LOCAZIONE
CESSIONE = DocumentTemplate.Codice.CESSIONE_FABBRICATO

OGGI = datetime.date(2026, 8, 2)
INGRESSO = datetime.date(2026, 7, 22)


# ---------------------------------------------------------------------------
# Costruzione dello scenario
# ---------------------------------------------------------------------------


ANAGRAFICA = {
    "cognome": "Rossi",
    "nome": "Mario",
    "data_nascita": datetime.date(1990, 3, 12),
    "comune_nascita": "Monza",
    "provincia_nascita": "MB",
    "cittadinanza": "italiana",
    "residenza_via": "Via Palestrina 20",
    "residenza_comune": "Monza",
    "residenza_provincia": "MB",
    "residenza_cap": "20900",
}

DOCUMENTO = {
    "documento_tipo": TenantProfile.TipoDocumento.CARTA_IDENTITA,
    "documento_numero": "CA72894HS",
    "documento_autorita": "Ministero dell'Interno",
    "documento_data_rilascio": datetime.date(2024, 3, 22),
}


def _nome_e_cognome(nominativo):
    cognome, _, nome = nominativo.partition(" ")
    return {"cognome": cognome, "nome": nome}


def _owner(nominativo, completo=True):
    user = User.objects.create_user(username=nominativo.lower().replace(" ", "-"))
    dati = {
        "nominativo": nominativo,
        "codice_fiscale": "DNTLSN63D07Z404Z",
        "telefono": "3358389194",
    }
    if completo:
        dati |= {**ANAGRAFICA, **_nome_e_cognome(nominativo)}
    return OwnerProfile.objects.create(user=user, **dati)


def _tenant(immobile, nominativo, completo=True):
    user = User.objects.create_user(
        username=nominativo.lower().replace(" ", "-"), email=f"{nominativo}@example.com"
    )
    dati = {
        "nominativo": nominativo,
        "codice_fiscale": "RSSMRA90C12F704X",
        "telefono": "3331234567",
        "giorno_pagamento_affitto": 5,
    }
    if completo:
        dati |= {**ANAGRAFICA, **DOCUMENTO, **_nome_e_cognome(nominativo)}
    return TenantProfile.objects.create(user=user, property=immobile, **dati)


@pytest.fixture
def scenario(immobile):
    """Immobile, contratto, comproprietari, uscente e subentrante completi."""
    for campo, valore in {
        # ``via`` è la via *per esteso*, come in produzione e come la usa la
        # comunicazione di cessione: il campo si chiama «via/piazza» perché
        # ci sta dentro anche "Piazza Trento".
        "via": "Via Palestrina", "civico": "20", "cap": "20900", "comune": "Monza",
        "provincia": "MB", "piano": "2", "vani": "5",
    }.items():
        setattr(immobile, campo, valore)

    alessandro = _owner("Dentella Alessandro")
    fabio = _owner("Dentella Fabio")
    immobile.owner_firmatario = alessandro
    immobile.save()

    for owner in (alessandro, fabio):
        OwnershipShare.objects.create(
            property=immobile, owner=owner,
            valid_from=datetime.date(2020, 1, 1), quota=Decimal("0.5"),
        )

    contratto = Contract.objects.create(
        property=immobile,
        nome="Contratto 2025",
        data_stipula=datetime.date(2025, 2, 20),
        data_decorrenza=datetime.date(2025, 2, 20),
        durata_anni=4,
        durata_rinnovo_anni=2,
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
    uscente = _tenant(immobile, "Di Maio Davide")
    assegnazione_uscente = RoomAssignment.objects.create(
        room=stanza, tenant=uscente,
        valid_from=datetime.date(2025, 2, 20),
        valid_to=datetime.date(2026, 6, 30),
        canone_mensile=Decimal("400"),
    )
    subentrante = _tenant(immobile, "Bouchane Oussama")
    assegnazione = RoomAssignment.objects.create(
        room=stanza, tenant=subentrante,
        valid_from=INGRESSO,
        canone_mensile=Decimal("400"),
        subentra_a=assegnazione_uscente,
    )
    for i in range(3):
        Receivable.objects.create(
            assignment=assegnazione,
            causale=Receivable.Causale.DEPOSITO,
            competenza_da=INGRESSO,
            competenza_a=INGRESSO,
            importo_dovuto=Decimal("266.67"),
            scadenza=INGRESSO + datetime.timedelta(days=30 * i),
        )
    for codice in (ATTO, CESSIONE):
        DocumentTemplate.objects.create(
            property=immobile, codice=codice, corpo_html=esempio(codice)
        )

    return {
        "immobile": immobile,
        "contratto": contratto,
        "stanza": stanza,
        "tenant": subentrante,
        "uscente": uscente,
        "assegnazione": assegnazione,
        "assegnazione_uscente": assegnazione_uscente,
        "owner": alessandro,
        "owner2": fabio,
    }


def _testo_pdf(pdf: bytes) -> str:
    """Testo estratto dal PDF (``pdftotext``, come il parsing bollette)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as fh:
        fh.write(pdf)
        fh.flush()
        esito = subprocess.run(
            ["pdftotext", "-layout", fh.name, "-"],
            capture_output=True, text=True, check=True,
        )
    return esito.stdout


def _chiavi(mancanti):
    return {m["campo"] for m in mancanti}


# ---------------------------------------------------------------------------
# Scenario completo
# ---------------------------------------------------------------------------


class TestScenarioCompleto:
    def test_atto_non_ha_mancanti(self, scenario):
        esito = anteprima(scenario["tenant"], ATTO, oggi=OGGI)
        assert esito["mancanti"] == []
        assert esito["completo"] is True

    def test_cessione_non_ha_mancanti(self, scenario):
        esito = anteprima(scenario["tenant"], CESSIONE, oggi=OGGI)
        assert esito["mancanti"] == []

    def test_riepilogo(self, scenario):
        riepilogo = anteprima(scenario["tenant"], ATTO, oggi=OGGI)["riepilogo"]
        assert riepilogo["stanza"] == "Camera 2"
        assert riepilogo["decorrenza"] == INGRESSO
        assert riepilogo["canone"] == "400,00"
        assert riepilogo["oneri_accessori"] == "70,00"
        assert riepilogo["rate_deposito"] == 3
        assert riepilogo["deposito"] == "800,01"
        assert riepilogo["uscente"] == "Di Maio Davide"
        assert riepilogo["comproprietari"] == ["Dentella Alessandro", "Dentella Fabio"]

    def test_riepilogo_cessione_non_parla_di_soldi(self, scenario):
        """La comunicazione all'autorità non dice a che prezzo si è ceduto.

        Canone, oneri, deposito e comproprietari non compaiono nel modulo:
        rileggerli prima di generarlo confondeva e basta.
        """
        riepilogo = anteprima(scenario["tenant"], CESSIONE, oggi=OGGI)["riepilogo"]
        assert riepilogo == {
            "data_cessione": INGRESSO,
            "firmatario": "Dentella Alessandro",
            "fabbricato": "Via Palestrina 20, 20900 Monza (MB)",
        }

    def test_documento_sconosciuto(self, scenario):
        with pytest.raises(KeyError):
            anteprima(scenario["tenant"], "inesistente", oggi=OGGI)


# ---------------------------------------------------------------------------
# Dati mancanti
# ---------------------------------------------------------------------------


class TestMancanti:
    def test_inquilino_senza_assegnazioni(self, immobile):
        orfano = _tenant(immobile, "Senza Stanza")
        with pytest.raises(DatiInsufficienti):
            anteprima(orfano, ATTO, oggi=OGGI)

    def test_modello_non_caricato_e_il_primo_mancante(self, scenario):
        DocumentTemplate.objects.filter(codice=ATTO).delete()
        esito = anteprima(scenario["tenant"], ATTO, oggi=OGGI)
        assert esito["mancanti"][0]["campo"] == "modello"
        assert esito["mancanti"][0]["link"].startswith("/p/impostazioni?tab=modelli")
        assert esito["completo"] is False

    def test_anagrafica_inquilino_vuota(self, scenario):
        tenant = scenario["tenant"]
        for campo in ("cognome", "comune_nascita", "residenza_via"):
            setattr(tenant, campo, "")
        tenant.data_nascita = None
        tenant.save()
        mancanti = anteprima(tenant, ATTO, oggi=OGGI)["mancanti"]
        assert "subentrante_nome" in _chiavi(mancanti)
        assert "subentrante_data_nascita" in _chiavi(mancanti)
        voce = next(m for m in mancanti if m["campo"] == "subentrante_data_nascita")
        assert voce["link"] == (
            f"/p/inquilini/{tenant.pk}?tab=profilo&modifica=anagrafica"
            "&campo=data_nascita"
        )
        assert voce["esterno"] is False

    def test_estremi_registrazione_mancanti(self, scenario):
        contratto = scenario["contratto"]
        contratto.numero_registrazione = ""
        contratto.data_registrazione = None
        contratto.save()
        mancanti = anteprima(scenario["tenant"], ATTO, oggi=OGGI)["mancanti"]
        assert {"registrazione_numero", "registrazione_data"} <= _chiavi(mancanti)
        voce = next(m for m in mancanti if m["campo"] == "registrazione_numero")
        assert f"contratto={contratto.pk}" in voce["link"]

    def test_subentro_non_impostato_e_un_solo_mancante(self, scenario):
        """Se non si sa a chi si subentra manca il collegamento, non i
        quattro dati dell'uscente che ne discendono."""
        assegnazione = scenario["assegnazione"]
        assegnazione.subentra_a = None
        assegnazione.save()
        mancanti = anteprima(scenario["tenant"], ATTO, oggi=OGGI)["mancanti"]
        da_assegnazione = [m for m in mancanti if m["fonte"] == "assignment"]
        assert len(da_assegnazione) == 1
        assert da_assegnazione[0]["esterno"] is True
        assert da_assegnazione[0]["link"].startswith("/admin/properties/roomassignment/")
        assert not [m for m in mancanti if m["fonte"] == "uscente"]

    def test_deposito_manda_alla_scheda_admin(self, scenario):
        """Il deposito non è nel form anagrafica: il link deve portare dove
        si può davvero sistemare, non su un dialog che non lo contiene."""
        Receivable.objects.filter(
            causale=Receivable.Causale.DEPOSITO
        ).delete()
        scenario["tenant"].deposito_versato = Decimal("0")
        scenario["tenant"].save()
        mancanti = anteprima(scenario["tenant"], ATTO, oggi=OGGI)["mancanti"]
        voce = next(m for m in mancanti if m["campo"] == "deposito")
        assert voce["link"] == (
            f"/admin/properties/tenantprofile/{scenario['tenant'].pk}/change/"
        )
        assert voce["esterno"] is True

    def test_comproprietario_incompleto_e_nominato(self, scenario):
        fabio = scenario["owner2"]
        fabio.data_nascita = None
        fabio.save()
        mancanti = anteprima(scenario["tenant"], ATTO, oggi=OGGI)["mancanti"]
        voce = next(m for m in mancanti if "Dentella Fabio" in m["etichetta"])
        assert voce["etichetta"] == "Data di nascita — Dentella Fabio"
        assert voce["link"] == (
            f"/p/impostazioni?tab=membri&modifica=anagrafica&owner={fabio.pk}"
            "&campo=data_nascita"
        )
        assert voce["esterno"] is False

    def test_firmatario_assente_e_un_solo_mancante(self, scenario):
        """Il modulo art. 12 vuole un dichiarante solo: finché non è scelto,
        i suoi otto dati anagrafici non sono ancora "mancanti"."""
        immobile = scenario["immobile"]
        immobile.owner_firmatario = None
        immobile.save()
        mancanti = anteprima(scenario["tenant"], CESSIONE, oggi=OGGI)["mancanti"]
        da_owner = [m for m in mancanti if m["fonte"] in ("owner", "property")]
        assert [m["campo"] for m in da_owner] == [""]
        assert da_owner[0]["link"].startswith("/p/impostazioni?tab=dati")

    def test_dati_documento_identita(self, scenario):
        tenant = scenario["tenant"]
        tenant.documento_numero = ""
        tenant.documento_tipo = ""
        tenant.save()
        mancanti = anteprima(tenant, CESSIONE, oggi=OGGI)["mancanti"]
        assert {
            "cessionario_documento_numero", "cessionario_documento_tipo",
        } <= _chiavi(mancanti)

    def test_caselle_facoltative_del_fabbricato(self, scenario):
        """Scala, interno, accessori e ingressi restano in bianco senza
        bloccare nulla: in un appartamento singolo spesso non esistono."""
        esito = anteprima(scenario["tenant"], CESSIONE, oggi=OGGI)
        assert esito["mancanti"] == []
        assert scenario["immobile"].scala == ""


# ---------------------------------------------------------------------------
# Fonti
# ---------------------------------------------------------------------------


class TestFonti:
    def test_quote_chiuse_prima_del_subentro_non_contano(self, scenario):
        uscito = scenario["owner2"]
        OwnershipShare.objects.filter(owner=uscito).update(
            valid_to=datetime.date(2026, 1, 1)
        )
        fonti = raccogli_fonti(scenario["tenant"], oggi=OGGI)
        assert [o.nominativo for o in fonti.comproprietari] == ["Dentella Alessandro"]

    def test_quota_condominio_non_dipende_dal_contratto_attivo(self, scenario):
        """La quota si cerca per immobile, come fa la generazione degli
        addebiti: se il documento leggesse solo il contratto attivo,
        dichiarerebbe una cifra diversa da quella che l'inquilino paga."""
        contratto = scenario["contratto"]
        # Decorrenza spostata dopo l'ingresso dell'inquilino: alla sua data
        # il contratto attivo diventa un altro (o nessuno).
        contratto.data_decorrenza = INGRESSO + datetime.timedelta(days=10)
        contratto.save()
        fonti = raccogli_fonti(scenario["tenant"], oggi=OGGI)
        assert fonti.contract is None
        assert fonti.oneri_accessori == Decimal("70")

    def test_quota_condominio_del_tenant_vince_sulla_generica(self, scenario):
        TenantCondominioRate.objects.create(
            contract=scenario["contratto"],
            tenant=scenario["tenant"],
            valid_from=datetime.date(2026, 1, 1),
            importo_mensile=Decimal("90"),
        )
        fonti = raccogli_fonti(scenario["tenant"], oggi=OGGI)
        assert fonti.oneri_accessori == Decimal("90")

    def test_quota_condominio_scaduta_ignorata(self, scenario):
        TenantCondominioRate.objects.filter(contract=scenario["contratto"]).update(
            valid_to=datetime.date(2026, 1, 1)
        )
        fonti = raccogli_fonti(scenario["tenant"], oggi=OGGI)
        assert fonti.oneri_accessori is None

    def test_restituzione_deposito_non_conta_come_rata(self, scenario):
        Receivable.objects.create(
            assignment=scenario["assegnazione"],
            causale=Receivable.Causale.DEPOSITO,
            competenza_da=INGRESSO,
            competenza_a=INGRESSO,
            importo_dovuto=Decimal("-800"),
            scadenza=INGRESSO,
        )
        fonti = raccogli_fonti(scenario["tenant"], oggi=OGGI)
        assert fonti.rate_deposito == 3

    def test_uscente_solo_da_subentra_a(self, scenario):
        """Le date non bastano: l'uscente chiude il 30/06 e il subentrante
        entra il 22/07, e comunque il legame non si deduce."""
        assegnazione = scenario["assegnazione"]
        assegnazione.subentra_a = None
        assegnazione.save()
        fonti = raccogli_fonti(scenario["tenant"], oggi=OGGI)
        assert fonti.uscente is None


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------


class TestPdf:
    def test_atto_contiene_i_dati(self, scenario):
        pdf, nome, tipo = genera_pdf(scenario["tenant"], ATTO, oggi=OGGI)
        assert pdf[:4] == b"%PDF"
        assert nome == "atto-subentro-bouchane-oussama-20260802.pdf"
        assert tipo == "atto_subentro_locazione"
        testo = _testo_pdf(pdf)
        assert "002272" in testo
        assert "TM325T002272000SJ" in testo
        assert "Camera 2" in testo
        assert "400,00" in testo
        assert "22/07/2026" in testo
        assert "30/06/2026" in testo  # recesso dell'uscente
        assert "Cedolare Secca" in testo
        assert "4+2" in testo
        # Nessun segnaposto rimasto scoperto.
        assert "{{" not in testo

    def test_atto_nomina_tutti_i_comproprietari(self, scenario):
        pdf, _, _ = genera_pdf(scenario["tenant"], ATTO, oggi=OGGI)
        testo = _testo_pdf(pdf)
        assert "Dentella Alessandro" in testo
        assert "Dentella Fabio" in testo

    def test_cessione_contiene_i_dati(self, scenario):
        pdf, nome, tipo = genera_pdf(scenario["tenant"], CESSIONE, oggi=OGGI)
        assert nome.startswith("cessione-fabbricato-")
        assert tipo == "cessione_fabbricato"
        testo = _testo_pdf(pdf)
        assert "CA72894HS" in testo
        assert "Ministero dell'Interno" in testo
        assert "20900" in testo
        assert "italiana" in testo
        assert "{{" not in testo

    def test_senza_modello_non_genera(self, scenario):
        DocumentTemplate.objects.filter(codice=ATTO).delete()
        with pytest.raises(DatiInsufficienti):
            genera_pdf(scenario["tenant"], ATTO, oggi=OGGI)

    def test_modello_non_puo_leggere_file_locali(self, scenario, tmp_path):
        """Il modello lo carica un utente: WeasyPrint non deve poter
        incorporare file del server nel PDF.

        WeasyPrint registra l'errore della risorsa e prosegue senza di
        essa: quel che conta è che il contenuto non finisca nel documento.
        """
        segreto = tmp_path / "segreto.txt"
        segreto.write_text("PAROLA-SEGRETA-NEL-FILE")
        modello = DocumentTemplate.objects.get(codice=ATTO)
        modello.corpo_html = (
            f'<p>ciao</p><img src="file://{segreto}">'
            f'<iframe src="file://{segreto}"></iframe>'
        )
        modello.save()
        pdf, _, _ = genera_pdf(scenario["tenant"], ATTO, oggi=OGGI)
        assert b"PAROLA-SEGRETA-NEL-FILE" not in pdf
        assert "PAROLA-SEGRETA-NEL-FILE" not in _testo_pdf(pdf)


# ---------------------------------------------------------------------------
# Segnaposto ed esempi
# ---------------------------------------------------------------------------


class TestSegnaposto:
    @pytest.mark.parametrize("codice", [ATTO, CESSIONE])
    def test_gli_esempi_usano_solo_segnaposto_esistenti(self, codice):
        disponibili = {s["chiave"] for s in segnaposto(codice)}
        import re

        usati = set(re.findall(r"\{\{(\w+)\}\}", esempio(codice)))
        assert usati <= disponibili, usati - disponibili

    def test_elenco_con_etichette(self):
        voci = segnaposto(CESSIONE)
        per_chiave = {v["chiave"]: v for v in voci}
        assert per_chiave["cessionario_cittadinanza"]["etichetta"] == (
            "Cittadinanza (cessionario)"
        )
        assert per_chiave["fabbricato_scala"]["obbligatorio"] is False
        assert per_chiave["uso"]["derivato"] is True


def test_formattazione_importi():
    assert eur(Decimal("1234.5")) == "1.234,50"
    assert eur(Decimal("70")) == "70,00"


# ---------------------------------------------------------------------------
# Fac-simile
# ---------------------------------------------------------------------------
#
# Lo stesso atto senza nessuna persona e senza nessuna stanza: si manda a
# leggere a chi deve ancora decidere. Le due cose da tenere ferme sono che
# non nomini nessuno e che si generi *anche quando* l'inquilino e
# l'assegnazione non ci sono — è tutto il punto: uno vale per tutti.


class TestFacSimile:
    def test_si_genera_senza_inquilino_e_senza_assegnazione(self, scenario):
        stato = anteprima_facsimile(scenario["immobile"], ATTO, oggi=OGGI)
        assert stato["completo"], stato["mancanti"]

        pdf, nome = genera_facsimile(scenario["immobile"], ATTO, oggi=OGGI)

        assert pdf.startswith(b"%PDF")
        assert nome.startswith("facsimile-atto-subentro-")

    def test_non_nomina_nessun_inquilino(self, scenario):
        pdf, _ = genera_facsimile(scenario["immobile"], ATTO, oggi=OGGI)
        testo = _testo_pdf(pdf)

        assert "Bouchane" not in testo
        assert "Di Maio" not in testo
        assert "RSSMRA90C12F704X" not in testo
        assert "Camera 2" not in testo
        assert "OMISSIS" in testo

    def test_indirizzo_non_raddoppia_il_via(self, scenario):
        """«Monza, Via Via Palestrina n. 20»: il campo contiene già "Via"."""
        testo = _testo_pdf(genera_facsimile(scenario["immobile"], ATTO, oggi=OGGI)[0])

        assert "Via Via" not in testo
        assert "Monza, Via Palestrina n. 20" in testo

    def test_i_locatori_e_il_contratto_restano(self, scenario):
        """Quello che si manda a leggere è proprio questo: chi sono i
        proprietari e a quale contratto registrato si subentra."""
        testo = _testo_pdf(genera_facsimile(scenario["immobile"], ATTO, oggi=OGGI)[0])

        assert "Dentella Alessandro" in testo
        assert "002272" in testo
        assert "Desio" in testo

    def test_senza_uscente_non_e_un_dato_mancante(self, immobile, scenario):
        """L'atto normale pretende di sapere a chi si subentra; il fac-simile
        non nomina nessuno, quindi non ha niente da chiedere."""
        scenario["assegnazione"].subentra_a = None
        scenario["assegnazione"].save()

        assert anteprima_facsimile(immobile, ATTO, oggi=OGGI)["completo"]

    def test_senza_contratto_dice_cosa_manca(self, immobile, scenario):
        scenario["contratto"].delete()

        stato = anteprima_facsimile(immobile, ATTO, oggi=OGGI)

        assert not stato["completo"]
        assert "contract" in _chiavi(stato["mancanti"])
        with pytest.raises(DatiInsufficienti):
            genera_facsimile(immobile, ATTO, oggi=OGGI)

    def test_senza_modello_dice_cosa_manca(self, immobile, scenario):
        DocumentTemplate.objects.filter(property=immobile, codice=ATTO).delete()

        stato = anteprima_facsimile(immobile, ATTO, oggi=OGGI)

        assert not stato["completo"]
        assert "modello" in _chiavi(stato["mancanti"])

    def test_documento_sconosciuto(self, immobile):
        with pytest.raises(KeyError):
            anteprima_facsimile(immobile, "inventato", oggi=OGGI)


class TestFacSimileAPI:
    """Dall'app: il fac-simile nasce già esponibile e già fuori dall'area
    dell'inquilino, che l'atto vero ce l'ha."""

    URL = "/api/v1/property-documents/facsimile/"

    @pytest.fixture(autouse=True)
    def media_private_tmp(self, settings, tmp_path):
        settings.MEDIA_PRIVATE_ROOT = str(tmp_path / "media-private")
        settings.MEDIA_ROOT = str(tmp_path / "media")

    @pytest.fixture
    def api(self, immobile):
        from rest_framework.test import APIClient

        from properties.models import PropertyMembership

        utente = User.objects.create_user("prop-facsimile")
        PropertyMembership.objects.create(
            property=immobile,
            user=utente,
            ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
        )
        client = APIClient(enforce_csrf_checks=False)
        client.force_login(utente)
        client.defaults["HTTP_X_PROPERTY_ID"] = str(immobile.pk)
        return client

    def test_genera_e_lo_rende_esponibile(self, api, scenario):
        from properties.models import PropertyDocument

        r = api.post(self.URL, {"codice": ATTO}, format="json")

        assert r.status_code == 201, r.data
        documento = PropertyDocument.objects.get(pk=r.data["id"])
        assert documento.tipo == PropertyDocument.Tipo.FAC_SIMILE
        assert documento.esponibile is True
        assert documento.visibile_inquilini is False
        assert documento.copia_di_id is None
        assert "OMISSIS" in _testo_pdf(documento.file.read())

    def test_dati_incompleti_400_con_l_elenco(self, api, immobile, scenario):
        scenario["contratto"].numero_registrazione = ""
        scenario["contratto"].save()

        r = api.post(self.URL, {"codice": ATTO}, format="json")

        assert r.status_code == 400
        assert "registrazione_numero" in str(r.data)

    def test_get_dice_cosa_manca_senza_generare(self, api, immobile, scenario):
        from properties.models import PropertyDocument

        r = api.get(self.URL, {"codice": ATTO})

        assert r.status_code == 200
        assert r.data["completo"] is True
        assert not PropertyDocument.objects.filter(
            tipo=PropertyDocument.Tipo.FAC_SIMILE
        ).exists()

    def test_codice_sconosciuto_400(self, api, scenario):
        assert api.post(self.URL, {"codice": "inventato"}, format="json").status_code == 400
