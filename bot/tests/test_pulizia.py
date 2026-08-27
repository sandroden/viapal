"""Test sulla pulizia del testo: è la parte che si può verificare senza browser."""
from bot.pulizia import e_troncato, pulisci


def test_toglie_il_rumore_delle_icone():
    assert pulisci("Facebook\nFacebook\nMario Rossi\nCerco stanza a Monza") == (
        "Mario Rossi\nCerco stanza a Monza"
    )


def test_taglia_i_commenti_col_nome_di_chi_commenta():
    raw = (
        "Laura Demi\nSegui\n·\nAffitto stanza a Monza\n"
        "3\n3\n"                       # contatori reazioni: il confine col post
        "Rubi Missevil\n11 h\nQual è il costo?\nRispondi\nCondividi"
    )
    assert pulisci(raw) == "Laura Demi\nAffitto stanza a Monza"


def test_un_post_senza_commenti_resta_intero():
    raw = "Federica\nCerco monolocale a Sesto\nDisponibilità da settembre\n2"
    assert pulisci(raw) == "Federica\nCerco monolocale a Sesto\nDisponibilità da settembre"


def test_non_scambia_un_prezzo_per_un_contatore():
    raw = "Anonimo\nAffitto stanza 500€ tutto incluso\n5\n4\nPeppe\n13 h\nTroppo\nRispondi"
    assert "500€" in pulisci(raw)


def test_riconosce_i_post_collassati():
    assert e_troncato("Affitti brevi… Altro...")
    assert not e_troncato("Cerco stanza a Monza")
