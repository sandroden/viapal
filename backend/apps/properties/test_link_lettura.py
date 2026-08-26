"""
Link di lettura: pacchetto di documenti aperto da un token, senza account.

Le due invarianti che i test devono tenere ferme:

* **solo l'esponibile esce**, e il controllo si ripete al momento di servire
  il file — togliere la spunta revoca il documento anche nei link già
  mandati, non solo nel compositore;
* **la copia oscurata non è un documento ufficiale**: sta fuori da
  tutti gli elenchi, compreso quello dell'inquilino, che l'originale ce
  l'ha già.

Il resto sono le trappole del token: un link revocato è 404, la voce di un
altro share è 404, e il file non deve finire indicizzato.
"""
import datetime
import re
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from rest_framework.test import APIClient

from properties.models import (
    Contract,
    DocumentShare,
    PropertyDocument,
    PropertyMembership,
    Room,
    RoomAssignment,
    ShareItem,
    TESTO_PREDEFINITO,
    TenantProfile,
    rendi_markdown,
)

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4 contenuto di test"
DOCS = "/api/v1/property-documents/"
SHARES = "/api/v1/document-shares/"
VOCI = "/api/v1/share-items/"


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
    proprietario = User.objects.create_user("prop-link")
    PropertyMembership.objects.create(
        property=immobile,
        user=proprietario,
        ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
    )
    c = APIClient(enforce_csrf_checks=False)
    c.force_login(proprietario)
    c.defaults["HTTP_X_PROPERTY_ID"] = str(immobile.pk)
    return c


def _doc(immobile, contratto=None, **kwargs):
    campi = {
        "tipo": PropertyDocument.Tipo.CONTRATTO if contratto else PropertyDocument.Tipo.REGOLE_CONVIVENZA,
        "visibile_inquilini": True,
        "descrizione": "Contratto 2025 firmato",
    }
    campi.update(kwargs)
    return PropertyDocument.objects.create(
        property=immobile,
        contract=contratto,
        file=SimpleUploadedFile(campi.pop("nome", "doc.pdf"), PDF),
        **campi,
    )


def _copia(originale, **kwargs):
    return PropertyDocument.objects.create(
        property=originale.property,
        contract=originale.contract,
        tipo=originale.tipo,
        descrizione=kwargs.pop("descrizione", "Contratto — copia oscurata"),
        file=SimpleUploadedFile(kwargs.pop("nome", "copia.pdf"), PDF),
        copia_di=originale,
        esponibile=kwargs.pop("esponibile", True),
        visibile_inquilini=kwargs.pop("visibile_inquilini", False),
        **kwargs,
    )


def _share(immobile, destinatario="Simona Bagnato", **kwargs):
    return DocumentShare.objects.create(
        property=immobile, destinatario=destinatario, **kwargs
    )


# ── Il token ──────────────────────────────────────────────────────────────


def test_ogni_link_ha_il_suo_token(immobile):
    """``default=genera_token`` è una funzione, non una chiamata valutata
    alla definizione della classe: due share, due token."""
    a, b = _share(immobile, "A"), _share(immobile, "B")
    assert a.token and b.token and a.token != b.token


def test_token_sconosciuto_404(client):
    assert client.get("/api/v1/public/documenti/inventato/").status_code == 404


def test_link_revocato_404(client, immobile):
    share = _share(immobile, attivo=False)
    assert client.get(f"/api/v1/public/documenti/{share.token}/").status_code == 404


def test_anonimo_legge_il_pacchetto_e_conta_le_aperture(client, immobile):
    share = _share(immobile, introduzione="Ciao, **ecco le carte**.")
    doc = _doc(immobile, esponibile=True, descrizione="Regole di convivenza")
    ShareItem.objects.create(share=share, documento=doc, ordine=0)
    ShareItem.objects.create(
        share=share, titolo="Cosa pagherai", corpo_md="**150 €** al mese", ordine=1
    )

    r = client.get(f"/api/v1/public/documenti/{share.token}/")

    assert r.status_code == 200
    assert r.data["destinatario"] == "Simona Bagnato"
    assert "<strong>ecco le carte</strong>" in r.data["introduzione_html"]
    assert r.data["casa"]["nome"] == immobile.nome
    assert [v["titolo"] for v in r.data["voci"]] == [
        "Regole di convivenza",
        "Cosa pagherai",
    ]
    assert [v["tipo"] for v in r.data["voci"]] == ["documento", "testo"]
    share.refresh_from_db()
    assert share.visite == 1 and share.ultima_visita is not None


def test_il_pacchetto_non_espone_dati_interni(client, immobile):
    """Chi apre il link non ha un account: nessun id di documento, nessun
    path di file, nessun contatore."""
    share = _share(immobile)
    doc = _doc(immobile, esponibile=True)
    ShareItem.objects.create(share=share, documento=doc, ordine=0)

    r = client.get(f"/api/v1/public/documenti/{share.token}/")

    assert set(r.data) == {"casa", "destinatario", "introduzione_html", "voci"}
    assert set(r.data["voci"][0]) == {"id", "tipo", "titolo", "corpo_html"}


# ── Solo l'esponibile esce ────────────────────────────────────────────────


def test_documento_non_piu_esponibile_sparisce_e_il_file_da_404(client, immobile):
    share = _share(immobile)
    doc = _doc(immobile, esponibile=True)
    voce = ShareItem.objects.create(share=share, documento=doc, ordine=0)
    url_file = f"/api/v1/public/documenti/{share.token}/file/{voce.pk}/"
    assert client.get(url_file).status_code == 200

    doc.esponibile = False
    doc.save(update_fields=["esponibile"])

    r = client.get(f"/api/v1/public/documenti/{share.token}/")
    assert r.data["voci"] == []
    assert client.get(url_file).status_code == 404


def test_voce_di_un_altro_share_404(client, immobile):
    mio, altrui = _share(immobile, "Mio"), _share(immobile, "Altrui")
    doc = _doc(immobile, esponibile=True)
    voce_altrui = ShareItem.objects.create(share=altrui, documento=doc, ordine=0)

    r = client.get(f"/api/v1/public/documenti/{mio.token}/file/{voce_altrui.pk}/")

    assert r.status_code == 404


def test_voce_di_testo_non_ha_file(client, immobile):
    share = _share(immobile)
    voce = ShareItem.objects.create(share=share, corpo_md="niente allegato", ordine=0)

    r = client.get(f"/api/v1/public/documenti/{share.token}/file/{voce.pk}/")

    assert r.status_code == 404


def test_il_file_e_inline_e_non_indicizzabile(client, immobile):
    share = _share(immobile)
    doc = _doc(immobile, esponibile=True)
    voce = ShareItem.objects.create(share=share, documento=doc, ordine=0)

    r = client.get(f"/api/v1/public/documenti/{share.token}/file/{voce.pk}/")

    assert r.status_code == 200
    assert r["X-Robots-Tag"] == "noindex, nofollow"
    assert r["Content-Disposition"].startswith("inline")


def test_voce_con_documento_non_esponibile_rifiutata(api, immobile):
    share = _share(immobile)
    doc = _doc(immobile, esponibile=False)

    r = api.post(
        VOCI, {"share": share.pk, "documento": doc.pk}, format="json"
    )

    assert r.status_code == 400
    assert "esponibile" in str(r.data).lower()


# ── La copia per la lettura ───────────────────────────────────────────────


def test_copia_lettura_nasce_esponibile_e_legata(api, immobile, contratto):
    originale = _doc(immobile, contratto)

    r = api.post(
        f"{DOCS}{originale.pk}/copia-lettura/",
        {"file": SimpleUploadedFile("oscurato.pdf", PDF)},
        format="multipart",
    )

    assert r.status_code == 201, r.data
    copia = PropertyDocument.objects.get(pk=r.data["id"])
    assert copia.copia_di_id == originale.pk
    assert copia.esponibile is True
    assert copia.visibile_inquilini is False
    assert copia.contract_id == contratto.pk
    assert r.data["copia_di_titolo"] == originale.titolo


def test_la_copia_di_una_copia_e_rifiutata(api, immobile):
    originale = _doc(immobile)
    copia = _copia(originale)

    r = api.post(
        f"{DOCS}{copia.pk}/copia-lettura/",
        {"file": SimpleUploadedFile("altra.pdf", PDF)},
        format="multipart",
    )

    assert r.status_code == 400


def test_copia_di_un_originale_malformato_da_400(api, immobile):
    """Un contratto senza contratto è un dato legacy malformato: la copia lo
    eredita e il difetto emerge qui — con un messaggio, non con un 500."""
    malformato = _doc(immobile, tipo=PropertyDocument.Tipo.CONTRATTO)

    r = api.post(
        f"{DOCS}{malformato.pk}/copia-lettura/",
        {"file": SimpleUploadedFile("copia.pdf", PDF)},
        format="multipart",
    )

    assert r.status_code == 400


def test_copia_non_compare_fra_i_documenti_dell_inquilino(immobile, contratto):
    """La lista dell'inquilino è quella da non dimenticare: l'originale ce
    l'ha già, la versione oscurata non gli va offerta."""
    originale = _doc(immobile, contratto, visibile_inquilini=True)
    copia = _copia(originale, visibile_inquilini=True)

    stanza = Room.objects.create(property=immobile, nome="C1")
    tenant = TenantProfile.objects.create(
        user=User.objects.create_user("inq-copia"),
        property=immobile,
        nominativo="Inquilino",
        giorno_pagamento_affitto=5,
    )
    RoomAssignment.objects.create(
        room=stanza,
        tenant=tenant,
        contract=contratto,
        valid_from=datetime.date(2025, 3, 1),
        canone_mensile=Decimal("400"),
    )
    c = APIClient(enforce_csrf_checks=False)
    c.force_login(tenant.user)

    ids = [d["id"] for d in c.get(DOCS).data]

    assert originale.pk in ids
    assert copia.pk not in ids


def test_inquilino_non_scarica_il_file_della_copia(immobile, contratto):
    """Secondo controllo: la lista non basta, con l'URL in mano si
    scaricherebbe comunque."""
    originale = _doc(immobile, contratto, visibile_inquilini=True)
    copia = _copia(originale, visibile_inquilini=True)
    stanza = Room.objects.create(property=immobile, nome="C1")
    tenant = TenantProfile.objects.create(
        user=User.objects.create_user("inq-file"),
        property=immobile,
        nominativo="Inquilino",
        giorno_pagamento_affitto=5,
    )
    RoomAssignment.objects.create(
        room=stanza,
        tenant=tenant,
        contract=contratto,
        valid_from=datetime.date(2025, 3, 1),
        canone_mensile=Decimal("400"),
    )
    c = Client()
    c.force_login(tenant.user)

    assert c.get(f"/media-private/{originale.file.name}").status_code == 200
    assert c.get(f"/media-private/{copia.file.name}").status_code == 403


def test_la_copia_resta_nella_lista_di_gestione(api, immobile):
    """Il proprietario le vede tutte: il FE separa le sezioni guardando
    ``copia_di``, non un filtro server."""
    originale = _doc(immobile)
    copia = _copia(originale)

    ids = [d["id"] for d in api.get(DOCS).data]

    assert {originale.pk, copia.pk} <= set(ids)


def test_copia_di_non_si_imposta_dal_post_generico(api, immobile):
    originale = _doc(immobile)

    r = api.post(
        DOCS,
        {
            "tipo": PropertyDocument.Tipo.ALTRO,
            "file": SimpleUploadedFile("furbata.pdf", PDF),
            "copia_di": originale.pk,
        },
        format="multipart",
    )

    assert r.status_code == 201
    assert PropertyDocument.objects.get(pk=r.data["id"]).copia_di_id is None


def test_eliminare_l_originale_con_una_copia_e_bloccato(api, immobile):
    """PROTECT e non SET_NULL: azzerando ``copia_di`` la copia oscurata
    diventerebbe un documento ufficiale a tutti gli effetti."""
    originale = _doc(immobile)
    _copia(originale)

    r = api.delete(f"{DOCS}{originale.pk}/")

    assert r.status_code == 409
    assert PropertyDocument.objects.filter(pk=originale.pk).exists()


def test_eliminare_un_documento_in_un_link_e_bloccato(api, immobile):
    share = _share(immobile)
    doc = _doc(immobile, esponibile=True)
    ShareItem.objects.create(share=share, documento=doc, ordine=0)

    r = api.delete(f"{DOCS}{doc.pk}/")

    assert r.status_code == 409
    assert "link di lettura" in r.data["detail"]


# ── Il testo di chiarimento ───────────────────────────────────────────────


def test_premessa_resa_e_sanitizzata(immobile):
    """La premessa apre la pagina e spiega tutto quello che segue: è
    markdown come i chiarimenti, e passa dallo stesso sanitizzatore."""
    share = _share(immobile, introduzione="## Ciao\n\n<script>x</script>**bene**")

    assert "<h2>Ciao</h2>" in share.introduzione_html
    assert "<script" not in share.introduzione_html
    assert "<strong>bene</strong>" in share.introduzione_html


def test_premessa_si_rigenera_anche_con_update_fields(immobile):
    """``save(update_fields=["introduzione"])`` non deve lasciare indietro
    l'HTML: la pagina pubblica mostra quello, non il markdown."""
    share = _share(immobile, introduzione="prima")
    share.introduzione = "**dopo**"
    share.save(update_fields=["introduzione", "updated_at"])

    share.refresh_from_db()
    assert "<strong>dopo</strong>" in share.introduzione_html


def test_premessa_si_scrive_dall_api(api, immobile):
    share = _share(immobile)

    r = api.patch(
        f"{SHARES}{share.pk}/", {"introduzione": "**ciao**"}, format="json"
    )

    assert r.status_code == 200
    assert "<strong>ciao</strong>" in r.data["introduzione_html"]


def test_markdown_sanitizzato(immobile):
    share = _share(immobile)
    voce = ShareItem.objects.create(
        share=share,
        corpo_md="**grassetto** <script>alert(1)</script>\n\n- uno\n- due",
        ordine=0,
    )

    assert "<strong>grassetto</strong>" in voce.corpo_html
    assert "<script" not in voce.corpo_html
    assert "alert(1)" not in voce.corpo_html
    assert "<li>uno</li>" in voce.corpo_html


def test_markdown_niente_immagini_ne_onclick():
    html = rendi_markdown('![x](http://evil/x.png)\n\n<p onclick="x()">ciao</p>')
    assert "<img" not in html
    assert "onclick" not in html


def test_testo_predefinito_e_una_proposta(api):
    """L'editor di un chiarimento nuovo parte da qui. Due paletti: che ci
    sia, e che non contenga importi — un link vale per più stanze, e una
    cifra scritta dentro resterebbe quella del giorno dell'invio."""
    r = api.get(f"{SHARES}testo-predefinito/")

    assert r.status_code == 200
    assert r.data["titolo"]
    assert r.data["corpo_md"] == TESTO_PREDEFINITO["corpo_md"]
    assert "€" not in r.data["corpo_md"]
    assert not re.search(r"\d+\s*(€|euro)", r.data["corpo_md"], re.I)


def test_testo_predefinito_e_markdown_valido(api):
    """Il testo si vede reso, non com'è scritto: se il segno di spunta o
    l'elenco non passano il sanitizzatore, il difetto è qui."""
    html = rendi_markdown(TESTO_PREDEFINITO["corpo_md"])

    assert "<li>" in html and "<strong>" in html
    assert "<script" not in html
    # ``nl2br`` è attivo: un paragrafo mandato a capo nel sorgente uscirebbe
    # spezzato a metà frase. Nessun <br> dentro un paragrafo o una voce.
    assert "<br" not in html


def test_anteprima_markdown_usa_lo_stesso_renderer(api):
    r = api.post(
        f"{SHARES}anteprima-markdown/",
        {"corpo_md": "**ciao** <script>x</script>"},
        format="json",
    )
    assert r.status_code == 200
    assert r.data["html"] == rendi_markdown("**ciao** <script>x</script>")


def test_voce_con_documento_e_testo_rifiutata(immobile):
    share = _share(immobile)
    doc = _doc(immobile, esponibile=True)
    voce = ShareItem(share=share, documento=doc, corpo_md="e anche un testo")

    with pytest.raises(ValidationError):
        voce.full_clean()


def test_voce_vuota_rifiutata(immobile):
    with pytest.raises(ValidationError):
        ShareItem(share=_share(immobile)).full_clean()


# ── Composizione lato gestione ────────────────────────────────────────────


def test_crea_link_e_riordina_le_voci(api, immobile):
    r = api.post(SHARES, {"destinatario": "Oussama Bouchane"}, format="json")
    assert r.status_code == 201, r.data
    share_id = r.data["id"]
    assert r.data["url_pubblico"].endswith(f"/d/{r.data['token']}")

    doc = _doc(immobile, esponibile=True)
    prima = api.post(VOCI, {"share": share_id, "documento": doc.pk}, format="json").data
    dopo = api.post(
        VOCI, {"share": share_id, "corpo_md": "Cosa pagherai"}, format="json"
    ).data
    assert (prima["ordine"], dopo["ordine"]) == (0, 1)

    r = api.post(
        f"{SHARES}{share_id}/riordina/",
        {"voci": [dopo["id"], prima["id"]]},
        format="json",
    )

    assert r.status_code == 200
    assert [v["id"] for v in r.data["voci"]] == [dopo["id"], prima["id"]]


def test_riordina_esige_tutte_le_voci(api, immobile):
    share = _share(immobile)
    doc = _doc(immobile, esponibile=True)
    voce = ShareItem.objects.create(share=share, documento=doc, ordine=0)
    ShareItem.objects.create(share=share, corpo_md="testo", ordine=1)

    r = api.post(f"{SHARES}{share.pk}/riordina/", {"voci": [voce.pk]}, format="json")

    assert r.status_code == 400


def test_revoca_e_riattiva(api, client, immobile):
    share = _share(immobile)

    api.post(f"{SHARES}{share.pk}/revoca/")
    assert client.get(f"/api/v1/public/documenti/{share.token}/").status_code == 404

    api.post(f"{SHARES}{share.pk}/riattiva/")
    assert client.get(f"/api/v1/public/documenti/{share.token}/").status_code == 200


def test_link_di_un_altro_immobile_invisibile(api, immobile2):
    _share(immobile2, "Estraneo")

    assert api.get(SHARES).data == []


def test_voce_con_documento_di_un_altro_immobile_rifiutata(api, immobile, immobile2):
    share = _share(immobile)
    estraneo = _doc(immobile2, esponibile=True)

    r = api.post(VOCI, {"share": share.pk, "documento": estraneo.pk}, format="json")

    assert r.status_code == 400


def test_voce_non_si_sposta_su_un_link_di_un_altro_immobile(api, immobile, immobile2):
    """Il queryset garantisce che la voce sia nostra, non che lo sia lo share
    in cui la si vuole spostare."""
    mia = ShareItem.objects.create(share=_share(immobile), corpo_md="testo", ordine=0)
    estraneo = _share(immobile2, "Estraneo")

    r = api.patch(f"{VOCI}{mia.pk}/", {"share": estraneo.pk}, format="json")

    assert r.status_code == 400
    mia.refresh_from_db()
    assert mia.share.property_id == immobile.pk


def test_link_con_inquilino_di_un_altro_immobile_rifiutato(api, immobile2):
    estraneo = TenantProfile.objects.create(
        user=User.objects.create_user("inq-estraneo"),
        property=immobile2,
        nominativo="Estraneo",
        giorno_pagamento_affitto=5,
    )

    r = api.post(
        SHARES, {"destinatario": "Tizio", "tenant": estraneo.pk}, format="json"
    )

    assert r.status_code == 400


def test_anonimo_non_compone(client, immobile):
    share = _share(immobile)
    assert client.get(SHARES).status_code in (401, 403)
    assert client.post(f"{SHARES}{share.pk}/revoca/").status_code in (401, 403)
