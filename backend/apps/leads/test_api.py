"""Test delle API dei lead.

Il cuore è l'invariante di proprietà dei campi: il bot riscrive i suoi, e non
tocca mai la lavorazione umana. Se un giorno qualcuno unificasse i due
serializer, è qui che deve suonare l'allarme.
"""
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from leads.models import Lead
from properties.models import PropertyMembership

URL = "/api/v1/leads/"
URL_UPSERT = "/api/v1/leads/bulk-upsert/"


# --- fixture ---------------------------------------------------------------


@pytest.fixture
def api():
    return APIClient(enforce_csrf_checks=False)


def _membro(immobile, username, ruolo=PropertyMembership.Ruolo.PROPRIETARIO):
    user = User.objects.create_user(username, email=f"{username}@v.it", password="pwd123!")
    PropertyMembership.objects.create(property=immobile, user=user, ruolo=ruolo)
    return user


@pytest.fixture
def sandro(db, immobile):
    return _membro(immobile, "lead_sandro")


@pytest.fixture
def bruna(db, immobile):
    return _membro(immobile, "lead_bruna")


@pytest.fixture
def bot_user(db, immobile):
    return _membro(immobile, "lead_bot", PropertyMembership.Ruolo.GESTORE)


def _payload(post_id="fb-1", **extra):
    dati = {
        "post_id": post_id,
        "group_id": "999",
        "group_label": "Affitti Monza",
        "author_name": "Giulia F.",
        "author_url": "https://www.facebook.com/groups/999",
        "permalink": f"https://www.facebook.com/groups/999/posts/{post_id}/",
        "link_messenger": "https://m.me/",
        "testo": "Cerco singola a Monza, max 480 tutto incluso.",
        "analisi": {"zona": "Monza", "budget_max": 480, "stanze_compatibili": ["S2"]},
        "commento_proposto": "Ciao, ti ho scritto in privato",
        "privato_proposto": "Ciao Giulia, abbiamo una singola libera…",
        "seen_at": timezone.now().isoformat(),
    }
    dati.update(extra)
    return dati


def _lead(immobile, **extra):
    dati = _payload(**{k: v for k, v in extra.items() if k != "post_id"})
    dati["post_id"] = extra.get("post_id", "fb-1")
    dati["seen_at"] = timezone.now()
    return Lead.objects.create(property=immobile, **dati)


# --- upsert dal bot --------------------------------------------------------


def test_upsert_crea_il_lead(api, immobile, bot_user):
    api.force_authenticate(bot_user)
    r = api.post(URL_UPSERT, {"leads": [_payload()]}, format="json")
    assert r.status_code == 200, r.data
    assert r.data == {"creati": 1, "aggiornati": 0, "scartati": []}
    lead = Lead.objects.get(post_id="fb-1")
    assert lead.property == immobile
    assert lead.stato == Lead.Stato.NUOVO
    assert lead.analisi["budget_max"] == 480


def test_upsert_e_idempotente(api, immobile, bot_user):
    api.force_authenticate(bot_user)
    api.post(URL_UPSERT, {"leads": [_payload()]}, format="json")
    r = api.post(URL_UPSERT, {"leads": [_payload()]}, format="json")
    assert r.data == {"creati": 0, "aggiornati": 1, "scartati": []}
    assert Lead.objects.count() == 1


def test_upsert_non_azzera_la_lavorazione(api, immobile, bot_user, bruna):
    """L'invariante che regge tutto: il secondo passaggio dello scraper non
    deve far sparire il fatto che Bruna ha già scritto a questa persona."""
    api.force_authenticate(bot_user)
    api.post(URL_UPSERT, {"leads": [_payload()]}, format="json")
    lead = Lead.objects.get(post_id="fb-1")
    lead.stato = Lead.Stato.CONTATTATO
    lead.preso_da = bruna
    lead.preso_at = timezone.now()
    lead.note = "le ho scritto ieri sera"
    lead.save()

    # il post ripassa nel feed con il testo modificato dall'autrice
    api.post(URL_UPSERT, {"leads": [_payload(testo="Cerco singola, ANCHE doppia")]}, format="json")

    lead.refresh_from_db()
    assert lead.testo == "Cerco singola, ANCHE doppia"   # il bot aggiorna i suoi
    assert lead.stato == Lead.Stato.CONTATTATO           # e non tocca gli altri
    assert lead.preso_da == bruna
    assert lead.note == "le ho scritto ieri sera"


def test_upsert_ignora_i_campi_umani_nel_payload(api, immobile, bot_user, bruna):
    """Anche se il bot li mandasse (bug, o payload confezionato a mano), i campi
    di lavorazione non sono nemmeno nominabili nel serializer."""
    api.force_authenticate(bot_user)
    r = api.post(
        URL_UPSERT,
        {"leads": [_payload(stato="risposto", note="iniettata", preso_da=bruna.pk)]},
        format="json",
    )
    assert r.status_code == 200
    lead = Lead.objects.get(post_id="fb-1")
    assert lead.stato == Lead.Stato.NUOVO
    assert lead.note == ""
    assert lead.preso_da is None


def test_una_riga_storta_non_blocca_le_altre(api, immobile, bot_user):
    """Il bot ritenta sempre lo stesso blocco: se una riga malformata lo
    facesse rifiutare tutto, la coda resterebbe ferma su quella riga per
    sempre e i lead buoni non arriverebbero mai."""
    api.force_authenticate(bot_user)
    r = api.post(
        URL_UPSERT,
        {"leads": [
            _payload("buono-1"),
            _payload("rotto", permalink="non-e-un-url"),
            _payload("buono-2"),
        ]},
        format="json",
    )
    assert r.status_code == 200
    assert r.data["creati"] == 2
    assert [s["post_id"] for s in r.data["scartati"]] == ["rotto"]
    assert set(Lead.objects.values_list("post_id", flat=True)) == {"buono-1", "buono-2"}


def test_upsert_rifiuta_estranei(api, immobile, db):
    estraneo = User.objects.create_user("estraneo", password="pwd123!")
    api.force_authenticate(estraneo)
    r = api.post(URL_UPSERT, {"leads": [_payload()]}, format="json")
    assert r.status_code in (403, 404)
    assert Lead.objects.count() == 0


def test_upsert_stesso_post_su_due_immobili(api, immobile, immobile2, bot_user):
    """Due immobili che pescano dallo stesso gruppo: lo stesso post è un lead
    per entrambi, ognuno con la propria presa in carico."""
    altro = _membro(immobile2, "bot_due")
    api.force_authenticate(bot_user)
    api.post(URL_UPSERT, {"leads": [_payload()]}, format="json", HTTP_X_PROPERTY_ID=immobile.pk)
    api.force_authenticate(altro)
    r = api.post(URL_UPSERT, {"leads": [_payload()]}, format="json", HTTP_X_PROPERTY_ID=immobile2.pk)
    assert r.status_code == 200
    assert Lead.objects.filter(post_id="fb-1").count() == 2


# --- lista e lavorazione ---------------------------------------------------


def test_lista_solo_del_proprio_immobile(api, immobile, immobile2, sandro):
    _lead(immobile, post_id="mio")
    _lead(immobile2, post_id="altrui")
    api.force_authenticate(sandro)
    r = api.get(URL, HTTP_X_PROPERTY_ID=immobile.pk)
    assert r.status_code == 200
    assert [x["post_id"] for x in r.data["results"]] == ["mio"]


def test_filtro_per_stato(api, immobile, sandro):
    _lead(immobile, post_id="a")
    contattato = _lead(immobile, post_id="b")
    contattato.stato = Lead.Stato.CONTATTATO
    contattato.save()
    api.force_authenticate(sandro)
    r = api.get(URL, {"stato": "nuovo"}, HTTP_X_PROPERTY_ID=immobile.pk)
    assert [x["post_id"] for x in r.data["results"]] == ["a"]


def test_patch_solo_stato_e_note(api, immobile, sandro):
    lead = _lead(immobile)
    api.force_authenticate(sandro)
    r = api.patch(
        f"{URL}{lead.pk}/",
        {"stato": "contattato", "note": "scritto su Messenger", "testo": "manomesso"},
        format="json",
        HTTP_X_PROPERTY_ID=immobile.pk,
    )
    assert r.status_code == 200
    lead.refresh_from_db()
    assert lead.stato == Lead.Stato.CONTATTATO
    assert lead.note == "scritto su Messenger"
    assert lead.testo != "manomesso"
    assert lead.contattato_at is not None


def test_contattato_at_non_si_sposta(api, immobile, sandro):
    lead = _lead(immobile)
    api.force_authenticate(sandro)
    kw = {"format": "json", "HTTP_X_PROPERTY_ID": immobile.pk}
    api.patch(f"{URL}{lead.pk}/", {"stato": "contattato"}, **kw)
    lead.refresh_from_db()
    primo = lead.contattato_at
    api.patch(f"{URL}{lead.pk}/", {"stato": "nuovo"}, **kw)
    api.patch(f"{URL}{lead.pk}/", {"stato": "contattato"}, **kw)
    lead.refresh_from_db()
    assert lead.contattato_at == primo


# --- fotina ----------------------------------------------------------------

FOTINA = "data:image/webp;base64,UklGRhoAAABXRUJQVlA4TA0AAAAvAAAAEAcQERGIiP4H"


def test_fotina_si_incolla_e_il_bot_non_la_cancella(api, immobile, sandro, bot_user):
    """La foto è un campo umano: il giro successivo dello scraper la trova
    ancora lì, come le note e la presa in carico."""
    lead = _lead(immobile)
    api.force_authenticate(sandro)
    r = api.patch(
        f"{URL}{lead.pk}/", {"foto": FOTINA}, format="json", HTTP_X_PROPERTY_ID=immobile.pk
    )
    assert r.status_code == 200, r.data
    assert r.data["foto"] == FOTINA

    api.force_authenticate(bot_user)
    api.post(URL_UPSERT, {"leads": [_payload()]}, format="json")
    lead.refresh_from_db()
    assert lead.foto == FOTINA


def test_fotina_rifiuta_quello_che_non_e_unimmagine(api, immobile, sandro):
    """Il ridimensionamento sta nel browser, la garanzia no: un PATCH arriva
    anche da curl, e il campo non deve diventare un deposito."""
    lead = _lead(immobile)
    api.force_authenticate(sandro)
    kw = {"format": "json", "HTTP_X_PROPERTY_ID": immobile.pk}
    r = api.patch(f"{URL}{lead.pk}/", {"foto": "https://esempio.it/faccia.jpg"}, **kw)
    assert r.status_code == 400
    r = api.patch(f"{URL}{lead.pk}/", {"foto": "data:image/webp;base64," + "A" * 100_000}, **kw)
    assert r.status_code == 400
    lead.refresh_from_db()
    assert lead.foto == ""


def test_fotina_si_toglie_con_la_stringa_vuota(api, immobile, sandro):
    lead = _lead(immobile)
    lead.foto = FOTINA
    lead.save()
    api.force_authenticate(sandro)
    r = api.patch(f"{URL}{lead.pk}/", {"foto": ""}, format="json", HTTP_X_PROPERTY_ID=immobile.pk)
    assert r.status_code == 200, r.data
    lead.refresh_from_db()
    assert lead.foto == ""


# --- presa in carico -------------------------------------------------------


def test_prendi_assegna_a_chi_chiama(api, immobile, sandro):
    lead = _lead(immobile)
    api.force_authenticate(sandro)
    r = api.post(f"{URL}{lead.pk}/prendi/", HTTP_X_PROPERTY_ID=immobile.pk)
    assert r.status_code == 200
    lead.refresh_from_db()
    assert lead.preso_da == sandro
    assert lead.preso_at is not None


def test_prendi_due_volte_in_due_persone(api, immobile, sandro, bruna):
    """Il caso per cui la pagina esiste: due che lavorano la stessa lista."""
    lead = _lead(immobile)
    api.force_authenticate(bruna)
    api.post(f"{URL}{lead.pk}/prendi/", HTTP_X_PROPERTY_ID=immobile.pk)
    api.force_authenticate(sandro)
    r = api.post(f"{URL}{lead.pk}/prendi/", HTTP_X_PROPERTY_ID=immobile.pk)
    assert r.status_code == 409
    assert "lead_bruna" in r.data["detail"] or "Bruna" in r.data["detail"]
    lead.refresh_from_db()
    assert lead.preso_da == bruna


def test_rilascia_solo_il_proprio(api, immobile, sandro, bruna):
    lead = _lead(immobile)
    api.force_authenticate(bruna)
    api.post(f"{URL}{lead.pk}/prendi/", HTTP_X_PROPERTY_ID=immobile.pk)
    api.force_authenticate(sandro)
    assert api.post(f"{URL}{lead.pk}/rilascia/", HTTP_X_PROPERTY_ID=immobile.pk).status_code == 409
    api.force_authenticate(bruna)
    assert api.post(f"{URL}{lead.pk}/rilascia/", HTTP_X_PROPERTY_ID=immobile.pk).status_code == 200
    lead.refresh_from_db()
    assert lead.preso_da is None


# --- riepilogo e chiusura campagna ----------------------------------------


def test_riepilogo(api, immobile, sandro):
    _lead(immobile, post_id="a")
    b = _lead(immobile, post_id="b")
    b.stato = Lead.Stato.CONTATTATO
    b.save()
    api.force_authenticate(sandro)
    r = api.get(f"{URL}riepilogo/", HTTP_X_PROPERTY_ID=immobile.pk)
    assert r.data["totale"] == 2
    assert r.data["per_stato"]["nuovo"] == 1
    assert r.data["per_stato"]["contattato"] == 1
    assert r.data["gruppi"] == [{"id": "999", "nome": "Affitti Monza"}]


def test_chiudi_campagna_vuole_la_conferma(api, immobile, sandro):
    _lead(immobile)
    api.force_authenticate(sandro)
    r = api.post(f"{URL}chiudi-campagna/", {}, format="json", HTTP_X_PROPERTY_ID=immobile.pk)
    assert r.status_code == 400
    assert Lead.objects.count() == 1


def test_chiudi_campagna_solo_ai_proprietari(api, immobile, bot_user):
    """Il gestore (e l'utente del bot, che ha la password in chiaro nel TOML)
    non deve poter buttare via le note e la presa in carico degli altri."""
    _lead(immobile)
    api.force_authenticate(bot_user)   # ruolo gestore
    r = api.post(
        f"{URL}chiudi-campagna/", {"conferma": True}, format="json",
        HTTP_X_PROPERTY_ID=immobile.pk,
    )
    assert r.status_code == 403
    assert Lead.objects.count() == 1


def test_chiudi_campagna_cancella_solo_il_proprio_immobile(api, immobile, immobile2, sandro):
    _lead(immobile, post_id="mio")
    _lead(immobile2, post_id="altrui")
    api.force_authenticate(sandro)
    r = api.post(
        f"{URL}chiudi-campagna/", {"conferma": True}, format="json", HTTP_X_PROPERTY_ID=immobile.pk
    )
    assert r.status_code == 200
    assert r.data["cancellati"] == 1
    assert Lead.objects.filter(post_id="altrui").exists()
