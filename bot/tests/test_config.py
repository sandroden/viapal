from pathlib import Path

from bot.config import carica

ESEMPIO = Path(__file__).parent.parent / "config.toml.example"


def test_il_file_di_esempio_si_carica():
    cfg = carica(ESEMPIO)
    assert cfg.group_id == "2262271623946575"
    assert len(cfg.stanze_libere) == 3


def test_il_totale_somma_canone_e_spese():
    """È l'unico numero confrontabile con un budget "tutto incluso"."""
    stanza = carica(ESEMPIO).stanze[0]
    assert stanza.totale == stanza.prezzo + stanza.spese_condominio == 550


def test_una_stanza_affittata_esce_dal_giro(tmp_path):
    testo = ESEMPIO.read_text().replace(
        'id = "camera-3"\nlibera = true', 'id = "camera-3"\nlibera = false'
    )
    f = tmp_path / "c.toml"
    f.write_text(testo)
    assert {s.id for s in carica(f).stanze_libere} == {"camera-4", "camera-5"}


def test_la_descrizione_espone_sempre_le_spese():
    """Il composer non deve poter citare il canone da solo."""
    d = carica(ESEMPIO).stanze[0].descrizione()
    assert "470" in d and "80" in d and "550" in d


def test_l_id_e_marcato_come_interno():
    """Il composer non deve citare "camera-3" a un estraneo."""
    assert carica(ESEMPIO).stanze[0].descrizione().startswith("[camera-3]")


def test_esiste_la_nota_sulle_utenze():
    """Senza questa, il composer scrive "tutto incluso" e mente sul preventivo."""
    assert "utenze" in carica(ESEMPIO).nota_utenze.lower()
