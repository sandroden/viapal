"""Test delle parti pure dell'anonimizzazione demo (nessun DB)."""
import random
from datetime import date
from decimal import Decimal as D

import pytest

from properties import anonimizza_demo as an

# --- importi -----------------------------------------------------------------


@pytest.mark.parametrize("src,atteso", [
    (D("100.00"), D("70.00")), (D("0.05"), D("0.04")), (D("0.01"), D("0.01")),
    (D("-100.00"), D("-70.00")), (D("33.50"), D("23.45")), (D("10.01"), D("7.01")),
    (D("0"), D("0.00")), (D("-0.05"), D("-0.04")),
])
def test_scala_half_up_simmetrico(src, atteso):
    assert an.scala(src) == atteso


def test_scala_none():
    assert an.scala(None) is None


def _somma(allocs, chiave, idx):
    tot = {}
    for aid, v in allocs.items():
        k = v[idx]
        tot[k] = tot.get(k, D(0)) + chiave[aid]
    return tot


def test_ripara_bt_e_addebiti_saldati_restano_pari():
    # un bonifico spezzato su tre addebiti con centesimi "scomodi"
    allocs = {1: (10, 100, D("33.33")), 2: (10, 101, D("33.33")), 3: (10, 102, D("33.34"))}
    bts = {10: D("100.00")}
    recs = {100: (D("33.33"), D("33.33")), 101: (D("33.33"), D("33.33")),
            102: (D("33.34"), D("33.34"))}
    r = an.ripara_importi(allocs, bts, recs)
    tot = sum(r.allocazioni.values())
    assert r.movimenti[10] == tot            # BT pari alla somma delle allocazioni
    for rc, aid in ((100, 1), (101, 2), (102, 3)):
        assert r.addebiti_dovuto[rc] == r.allocazioni[aid] == r.addebiti_pagato[rc]
    assert abs(tot - an.scala(D("100.00"))) <= D("0.02")


def test_ripara_addebito_pagato_da_piu_bonifici():
    allocs = {1: (10, 100, D("0.05")), 2: (11, 100, D("0.05"))}
    bts = {10: D("0.05"), 11: D("0.05")}
    recs = {100: (D("0.10"), D("0.10"))}
    r = an.ripara_importi(allocs, bts, recs)
    assert r.addebiti_dovuto[100] == r.allocazioni[1] + r.allocazioni[2]
    assert r.movimenti[10] == r.allocazioni[1] and r.movimenti[11] == r.allocazioni[2]


def test_ripara_addebito_aperto_senza_allocazioni_e_scalato_semplice():
    r = an.ripara_importi({}, {5: D("12.34")}, {7: (D("700.00"), None)})
    assert r.movimenti[5] == D("8.64")
    assert r.addebiti_dovuto[7] == D("490.00") and r.addebiti_pagato[7] is None


def test_ripara_parziale_resta_parziale_oltre_la_soglia():
    # dovuto 10.00, versati 8.70: scarto 1.30 > 1 euro -> aperto; scalando
    # scarterebbe 0.91 (<1) e diventerebbe "pagato": va corretto
    allocs = {1: (10, 100, D("8.70"))}
    r = an.ripara_importi(allocs, {10: D("8.70")}, {100: (D("10.00"), D("8.70"))})
    scarto = abs(r.addebiti_dovuto[100]) - abs(r.allocazioni[1])
    assert scarto > an.SOGLIA_RECEIVABLE
    assert r.addebiti_pagato[100] == r.allocazioni[1]


def test_ripara_addebito_pagato_per_tolleranza_resta_pagato():
    allocs = {1: (10, 100, D("78.30"))}
    r = an.ripara_importi(allocs, {10: D("78.30")}, {100: (D("79.30"), D("78.30"))})
    assert abs(r.addebiti_dovuto[100]) - abs(r.allocazioni[1]) <= an.SOGLIA_RECEIVABLE


def test_ripara_restituzione_deposito_segno_discorde():
    # addebito -980 coperto da +980 (restituzione con trattenuta): resta -980*0.7
    allocs = {1: (10, 100, D("980.00"))}
    r = an.ripara_importi(allocs, {10: D("980.00")}, {100: (D("-980.00"), D("980.00"))})
    assert r.addebiti_dovuto[100] == -r.allocazioni[1]
    assert r.addebiti_dovuto[100] < 0 < r.allocazioni[1]


def test_ripara_bt_eccedente_resta_eccedente():
    allocs = {1: (10, 100, D("50.00")), 2: (10, 101, D("50.00"))}
    bts = {10: D("99.00")}  # allocato 100 su 99: sovra
    recs = {100: (D("50.00"), D("50.00")), 101: (D("50.00"), D("50.00"))}
    r = an.ripara_importi(allocs, bts, recs)
    assert sum(r.allocazioni.values()) - r.movimenti[10] > an.TOLLERANZA_BT


def test_ripara_bt_parziale_resta_parziale():
    allocs = {1: (10, 100, D("30.00"))}
    r = an.ripara_importi(allocs, {10: D("30.04")}, {100: (D("30.00"), D("30.00"))})
    # 30.04 -> 21.03 vs 30.00 -> 21.00: il parziale resta parziale
    assert r.movimenti[10] > r.allocazioni[1]


# --- importi nel testo -------------------------------------------------------


@pytest.mark.parametrize("src,atteso", [
    ("Affitto 500€ al mese", "Affitto 350€ al mese"),
    ("totale 33,50 €", "totale 23,45 €"),
    ("(36.67€) [dichiarato]: 36.67 €", "(25.67€) [dichiarato]: 25.67 €"),
    ("costo € 67", "costo € 46.90"),
    ("1.000,00 euro", "700,00 euro"),
    ("il 12/03/2026 alle 10", "il 12/03/2026 alle 10"),      # niente simbolo: non e' un importo
    ("anno 2026 rata 5", "anno 2026 rata 5"),
    ("Costo mese400€ + spese", "Costo mese280€ + spese"),
])
def test_scala_importi_nel_testo(src, atteso):
    assert an.scala_importi_nel_testo(src) == atteso


# --- IBAN e codice fiscale ---------------------------------------------------


def test_iban_esempio_noto_valido():
    assert an.iban_valido("IT60X0542811101000000123456")
    assert not an.iban_valido("IT61X0542811101000000123456")


def test_iban_generati_validi_e_deterministici():
    for i in range(200):
        iban = an.genera_iban(random.Random(i))
        assert iban.startswith("IT") and len(iban) == 27 and an.iban_valido(iban), iban
    assert an.genera_iban(random.Random(7)) == an.genera_iban(random.Random(7))


def test_codice_fiscale_noto():
    assert an.codice_fiscale("Rossi", "Mario", date(1980, 1, 1), "M", "H501") == "RSSMRA80A01H501U"
    assert an.cf_valido("RSSMRA80A01H501U")
    assert not an.cf_valido("RSSMRA80A01H501X")


def test_codice_fiscale_donna_e_cognome_corto():
    cf = an.codice_fiscale("Fo", "Anna", date(1999, 12, 31), "F", "F952")
    assert cf[:6] == "FOXNNA" and cf[9:11] == "71" and an.cf_valido(cf)


def test_codice_fiscale_nome_con_quattro_consonanti():
    # nome con >= 4 consonanti: prima, terza, quarta
    cf = an.codice_fiscale("Bianchi", "Gianfranco", date(1970, 5, 5), "M", "L219")
    assert cf[3:6] == "GFR" and an.cf_valido(cf)


# --- scrubber ----------------------------------------------------------------


@pytest.fixture
def scr():
    s = an.Scrubber(seed="test")
    s.aggiungi_nome("Anna", "Giulia")
    s.aggiungi_nome("Bianchetti", "Ferrari")
    s.aggiungi_nome("De Rossi", "Colombo")
    s.aggiungi_nome("Monza", "Novara")
    s.aggiungi_nome("Palestrina", "dei Tigli")
    s.emails["anna@gmail.com"] = "giulia.ferrari@example.com"
    return s


def test_scrub_word_boundary(scr):
    assert scr.scrub("Anna e Annalisa, Sala Anna.") == "Giulia e Annalisa, Sala Giulia."
    assert scr.scrub("Banna Bianchettini") == "Banna Bianchettini"


def test_scrub_maiuscole_adattate(scr):
    assert scr.scrub("BON.DA BIANCHETTI ANNA") == "BON.DA FERRARI GIULIA"
    assert scr.scrub("anna bianchetti") == "giulia ferrari"


def test_scrub_frasi_con_particelle_prima_dei_token(scr):
    assert scr.scrub("Bonifico DE ROSSI DAVIDE") == "Bonifico COLOMBO DAVIDE"
    assert scr.scrub("De Rossi") == "Colombo"


def test_scrub_particella_minuscola_nei_finti(scr):
    assert scr.scrub("Via Palestrina 20, Monza") == "Via dei Tigli 20, Novara"


def test_scrub_minuscolo_vicino_a_maiuscolo_viene_capitalizzato(scr):
    assert scr.scrub("Bonifico anna Rossi") == "Bonifico Giulia Rossi"
    assert scr.scrub("caparra anna") == "caparra giulia"


def test_scrub_email_iban_cf_telefono(scr):
    t = scr.scrub("anna@gmail.com IT60X0542811101000000123456 RSSMRA80A01H501U 335/838.9194")
    assert t.startswith("giulia.ferrari@example.com ")
    assert "IT60X0542811101000000123456" not in t and "RSSMRA80A01H501U" not in t
    assert "335/838.9194" not in t
    assert an.iban_valido(t.split(" ")[1])
    assert an.cf_valido(t.split(" ")[2])


def test_scrub_idempotente_sui_finti(scr):
    una = scr.scrub("IT60X0542811101000000123456 RSSMRA80A01H501U 335 838 9194 x@y.it")
    due = scr.scrub(una)
    assert una == due


def test_scrub_codici_lunghi_e_importi(scr):
    t = scr.scrub("NR. BONIFICO SEPA: MB0B25236111 totale 100€")
    assert "MB0B25236111" not in t and t.endswith("70€")
    assert len(t.split()[3]) == 12


def test_scrub_senza_importi_non_scala(scr):
    assert scr.scrub("canone 100€", importi=False) == "canone 100€"


def test_scrub_token_reset_password(scr):
    t = scr.scrub("https://x.it/imposta-password/2x/dfh978-ad5fbc441423ea38b1d742ccfee1b7b1\nok")
    assert "dfh978" not in t and t.endswith("\nok") and "/imposta-password/" in t


def test_scrub_json(scr):
    out = scr.scrub_json({"a": ["Anna", {"b": "Monza 100€"}], "n": 3})
    assert out == {"a": ["Giulia", {"b": "Novara 70€"}], "n": 3}


def test_scrub_percorso_non_tocca_importi_e_codici(scr):
    assert scr.scrub_percorso("documenti/1-anna/fattura_100€_MB0B25236111.pdf") == \
        "documenti/1-giulia/fattura_100€_MB0B25236111.pdf"
    assert scr.scrub_percorso("doc/Palestrina_20.pdf") == "doc/dei-Tigli_20.pdf"


def test_scrub_ordinanti_sostituisce_i_terzi_e_lascia_i_noti():
    s = an.Scrubber(seed="test")
    s.token_noti = {"ferrari", "giulia"}
    s.vietati = {"mario", "verdi"}
    t = s.scrub_ordinanti("BON.DA FERRARI GIULIA E VERDI MARIO UTENZE LUGLIO NR. 123")
    assert t.startswith("BON.DA FERRARI GIULIA E ")
    assert "VERDI" not in t and "MARIO" not in t
    assert "UTENZE LUGLIO" in t


def test_scrub_ordinanti_non_tocca_le_aziende():
    s = an.Scrubber(seed="test")
    s.aziende = {"edison"}
    t = "BON.DA GENERALI ITALIA S.P.A. POL:1"
    assert s.scrub_ordinanti(t) == t


def test_scrub_percorso_slug_con_la_via(scr):
    scr.percorsi["viapessi"] = "casa-dei-gelsomini"
    assert scr.scrub_percorso("bollette/viapessi/2026/06/x.pdf") == \
        "bollette/casa-dei-gelsomini/2026/06/x.pdf"
    # il prodotto resta, e una parola che contiene lo slug non viene toccata
    assert scr.scrub_percorso("bollette/viapal/a.pdf") == "bollette/viapal/a.pdf"
    assert scr.scrub_percorso("x/viapessina/a.pdf") == "x/viapessina/a.pdf"


def test_scrub_percorso_partita_iva(scr):
    t = scr.scrub_percorso("spese/IT03336420967_ynipr.xml.p7m.pdf")
    assert "03336420967" not in t and t.startswith("spese/IT") and t.endswith("_ynipr.xml.p7m.pdf")
