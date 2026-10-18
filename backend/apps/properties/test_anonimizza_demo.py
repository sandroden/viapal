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


# --- ritocchi per le riprese -------------------------------------------------


def test_iban_finti_hanno_abi_non_assegnato_e_restano_validi():
    for i in range(100):
        iban = an.genera_iban(random.Random(i))
        assert iban[5:10] == "99999" and an.iban_valido(iban)


def test_telefono_fittizio_chiaramente_finto_e_riconosciuto_dalla_regex():
    s = an.Scrubber(seed="t")
    tel = s.telefono_finto("376 333 2514")
    assert tel.startswith("333 000 ") and len(an.normalizza_telefono(tel)) == 10
    assert s.telefono_finto("376 333 2514") == tel          # deterministico
    # i formati con spazi (e +39) sono presi dalla regex e riscritti
    for reale in ("376 333 2514", "+39 376 333 2514", "376-333-2514", "3763332514"):
        out = s.scrub(f"Tel: {reale}.")
        assert "376" not in out and "333 000" in out, (reale, out)
    # un finto non viene riscritto (idempotenza)
    assert s.scrub(f"Tel: {tel}.") == f"Tel: {tel}."


@pytest.mark.parametrize("src,atteso", [
    ("letto stanza mamma", "letto camera 2"),
    ("Cessione Camera Papà — Luca", "Cessione Camera 3 — Luca"),
    ("Sanzione ritardo successione suppletiva mamma", "Sanzione ritardo pagamento imposta"),
    ("Contratto nuovo: tommaso -> mamma", "Contratto nuovo: tommaso -> camera 2"),
    ("eredità di famiglia", "pratica di famiglia"),
    ("Affitto Ilaria — da libro mano «conti 2023» (riga 186)", "Affitto Ilaria"),
    ("TARI 2023 — da libro mano «conti 2023» riga 121", "TARI 2023"),
    ("Affitto Ilaria (righe 164+165)", "Affitto Ilaria"),
    ("mammone e papaveri", "mammone e papaveri"),   # niente falsi positivi
])
def test_frasi_neutre(src, atteso):
    assert an.applica_frasi(src) == atteso


def test_frasi_neutre_nei_percorsi():
    s = an.Scrubber(seed="t")
    assert s.scrub_percorso("spese/sanzione-successione-mamma.pdf") == \
        "spese/sanzione-ritardo-pagamento-imposta.pdf"


def test_nota_neutra():
    assert an.nota_neutra("Pagato in contanti") == "Pagato in contanti"
    assert an.nota_neutra("x" * 200) == an.NOTA_NEUTRA
    assert an.nota_neutra("Importo dal libro mano riga 88") == an.NOTA_NEUTRA
    assert an.nota_neutra("x" * 80, massimo=60) == an.NOTA_NEUTRA
    assert an.nota_neutra("") == ""


def test_descrizione_fra_proprietari_neutra():
    d = date(2024, 7, 3)
    assert an.descrizione_fra_proprietari(D("10"), d) == "Quota anticipata (luglio 2024)"
    assert an.descrizione_fra_proprietari(D("-10"), d) == "Rimborso quota (luglio 2024)"
    assert an.descrizione_fra_proprietari(D("5"), None, spesa=True) == "Spesa anticipata"
    assert an.descrizione_fra_proprietari(D("5"), d, bonifico=True).startswith("Bonifico")


def test_numero_bolletta_finto():
    n = an.numero_bolletta_finto("s", 144, date(2026, 7, 1))
    assert n.isdigit() and len(n) == 11 and n.startswith("26")
    assert n == an.numero_bolletta_finto("s", 144, date(2026, 7, 1))
    assert n != an.numero_bolletta_finto("s", 145, date(2026, 7, 1))
    assert "mz" not in n


def test_nomi_gruppo_finti_distinti_e_deterministici():
    nomi = [an.nome_gruppo_finto(i) for i in range(len(an.NOMI_GRUPPI_FINTI) + 3)]
    assert len(set(nomi)) == len(nomi)
    assert nomi[0] == an.nome_gruppo_finto(0)
    assert not any(c.isdigit() for c in nomi[0])


def test_nome_lead_coerente_per_provenienza():
    pool = {"italia": (set(an.NOMI_M + an.NOMI_F), set(an.COGNOMI_IT))}
    for k, v in an.CATEGORIE_ESTERE.items():
        pool[k] = (set(v[3] + v[4]), set(v[5]))
    viste = set()
    for i in range(300):
        nome, cognome, origine = an.genera_nome_lead(random.Random(i))
        assert nome in pool[origine][0] and cognome in pool[origine][1], (nome, cognome)
        viste.add(origine)
    assert len(viste) > 3
    assert an.genera_nome_lead(random.Random(5)) == an.genera_nome_lead(random.Random(5))


def test_nome_lead_rispetta_i_nomi_reali():
    escludi = {n.lower() for n in an.NOMI_M[:-1] + an.NOMI_F[:-1]}
    for i in range(100):
        nome, _c, origine = an.genera_nome_lead(random.Random(i), escludi)
        if origine == "italia":
            assert nome in (an.NOMI_M[-1], an.NOMI_F[-1])


def test_ascii_sicuro_toglie_i_glifi_mancanti():
    assert an.ascii_sicuro("Documento di esempio — dati fittizi") == \
        "Documento di esempio - dati fittizi"
    assert an.ascii_sicuro("2026-01-01 → 2026-01-31") == "2026-01-01 -> 2026-01-31"
    assert an.ascii_sicuro("è così") == "è così"


def test_ascii_puro_per_il_font_senza_accenti():
    assert an.ascii_puro("Carta d'identità — è") == "Carta d'identita - e"
    assert an.ascii_puro("1 → 2") == "1 -> 2"


# --- inquilini italiani tranne uno ------------------------------------------------


def _tutti_nomi_inquilini():
    return [n for g in an.NOMI_INQUILINI.values() for s in ("M", "F") for n in g[s]]


def test_pool_inquilini_disgiunti_da_proprietari_lead_e_terzi():
    nomi = {n.lower() for n in _tutti_nomi_inquilini()}
    cognomi = {c.lower() for c in an.COGNOMI_INQUILINI}
    altri_nomi = {n.lower() for n in an.NOMI_M + an.NOMI_F}
    altri_cognomi = {c.lower() for c in an.COGNOMI_IT + an.POOL_TERZI}
    for v in an.CATEGORIE_ESTERE.values():
        altri_nomi |= {n.lower() for n in v[3] + v[4]}
        altri_cognomi |= {c.lower() for c in v[5]}
    assert not nomi & altri_nomi
    assert not cognomi & altri_cognomi
    assert not nomi & cognomi
    # un token solo, nessun doppione
    assert all(" " not in x for x in nomi | cognomi)
    assert len(nomi) == len(_tutti_nomi_inquilini())
    assert len(cognomi) == len(an.COGNOMI_INQUILINI)


def test_comuni_nascita_inquilini_da_tutta_italia_e_cf_valido():
    sigle = {s for _c, s, _b in an.COMUNI_NASCITA_INQUILINI}
    assert {"NA", "PA", "BA", "CA", "RM", "NO"} <= sigle
    for comune, sigla, belf in an.COMUNI_NASCITA_INQUILINI:
        assert len(sigla) == 2 and sigla != "EE"
        assert len(belf) == 4 and belf[0].isalpha() and belf[0] != "Z" and belf[1:].isdigit()
        assert an.cf_valido(an.codice_fiscale("Esposito", "Ciro", date(1990, 3, 4), "M", belf))


@pytest.mark.parametrize("data,cf,atteso", [
    (date(1980, 6, 1), "", 1980),
    (date(2099, 1, 1), "RSSMRA62C10F839X", 1962),   # data refusa: vale il codice fiscale
    (None, "RSSMRA04C10F839X", 2004),
    (None, "RSSMRA62C10F839X", 1962),
    (None, "", None),
])
def test_anno_nascita(data, cf, atteso):
    assert an.anno_nascita(data, cf, oggi=date(2026, 10, 18)) == atteso


def test_pool_nomi_per_generazione():
    assert an.generazione(1961) == "adulta"
    assert an.generazione(1975) == "media"
    assert an.generazione(1994) == "media"
    assert an.generazione(1999) == "giovane"
    assert an.generazione(None) == "media"
    pool = an.pool_nomi_inquilino("M", 1961, random.Random(1))
    n = len(an.NOMI_INQUILINI["adulta"]["M"])
    assert set(pool[:n]) == set(an.NOMI_INQUILINI["adulta"]["M"])
    assert set(pool[n:]) == set(an.NOMI_INQUILINI["media"]["M"] + an.NOMI_INQUILINI["giovane"]["M"])
    assert pool == an.pool_nomi_inquilino("M", 1961, random.Random(1))
    assert set(an.pool_nomi_inquilino("F", 2001, random.Random(2))[:3]) <= set(
        an.NOMI_INQUILINI["giovane"]["F"])


def test_origine_estera_solo_lo_straniero_scelto_fra_gli_inquilini():
    kw = {"proprietario": False, "cittadinanza": "marocchina", "belfiore": "Z330"}
    assert an.origine_estera(**kw, straniero_scelto=False) is False
    assert an.origine_estera(**kw, straniero_scelto=True) is True
    assert an.origine_estera(proprietario=False, cittadinanza="", belfiore="F952",
                             straniero_scelto=True) is True
    # proprietari: decide la cittadinanza dichiarata, senza sono italiani
    assert an.origine_estera(proprietario=True, cittadinanza="Turca", belfiore="Z243",
                             straniero_scelto=False) is True
    assert an.origine_estera(proprietario=True, cittadinanza="", belfiore="Z243",
                             straniero_scelto=False) is False
    assert an.origine_estera(proprietario=True, cittadinanza="Italiana", belfiore="Z243",
                             straniero_scelto=True) is False


@pytest.mark.parametrize("tipo,autorita,estera,atteso", [
    ("permesso_soggiorno", "Questura di Novara", False, ("carta_identita", "Comune di Trecate")),
    ("passaporto", "Marocco", False, ("passaporto", "Questura di Novara")),
    ("passaporto", "Questura di Novara", False, ("passaporto", "Questura di Novara")),
    ("carta_identita", "Repubblica di Turchia", False, ("carta_identita", "Comune di Trecate")),
    ("carta_identita", "Comune di Cameri", False, ("carta_identita", "Comune di Cameri")),
    ("carta_identita", "", False, ("carta_identita", "")),
    ("", "", False, ("", "")),
    ("passaporto", "Marocco", True, ("passaporto", "Marocco")),
    ("permesso_soggiorno", "Questura di Novara", True, ("permesso_soggiorno", "Questura di Novara")),
])
def test_documento_coerente(tipo, autorita, estera, atteso):
    assert an.documento_coerente(tipo, autorita, estera=estera, comune="Trecate") == atteso
