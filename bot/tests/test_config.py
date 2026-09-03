from pathlib import Path

from bot.config import carica

ESEMPIO = Path(__file__).parent.parent / "config.toml.example"


def test_il_file_di_esempio_si_carica():
    cfg = carica(ESEMPIO)
    assert cfg.gruppi == ("2262271623946575",)
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


def test_i_due_modelli_sono_separati():
    """Classificare è meccanico, scrivere no: tenerli sullo stesso modello
    significa pagare il composer per ogni post letto."""
    cfg = carica(ESEMPIO)
    assert cfg.modello_classifier != cfg.modello_composer
    assert "haiku" in cfg.modello_classifier


def test_quello_che_non_abbiamo_e_dichiarato():
    """Chi chiede il bagno privato resta un lead, ma deve saperlo dal primo
    messaggio, non alla visita."""
    cfg = carica(ESEMPIO)
    assert "bagn" in cfg.non_abbiamo.lower()
    assert "condivis" in " ".join(cfg.punti_forza).lower()


def test_il_vecchio_group_id_singolo_vale_ancora(tmp_path):
    """Una config non ancora migrata non deve smettere di leggere il gruppo
    storico proprio mentre se ne aggiunge un altro."""
    f = tmp_path / "c.toml"
    f.write_text(ESEMPIO.read_text().replace(
        'gruppi = [\n    "2262271623946575",   # AFFITTI Monza e Brianza - CERCO/OFFRO\n]',
        'group_id = "2262271623946575"',
    ))
    assert carica(f).gruppi == ("2262271623946575",)


def test_i_gruppi_ripetuti_si_leggono_una_volta_sola(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text(ESEMPIO.read_text().replace(
        '"2262271623946575",   # AFFITTI Monza e Brianza - CERCO/OFFRO',
        '"2262271623946575", "99", "2262271623946575",',
    ))
    assert carica(f).gruppi == ("2262271623946575", "99")


# --- gruppi che rifiutano i commenti con un link ------------------------------

def _con_gruppi_senza_link(tmp_path, gruppi_senza_link):
    f = tmp_path / "c.toml"
    f.write_text(ESEMPIO.read_text().replace(
        "gruppi_senza_link = []", f"gruppi_senza_link = {gruppi_senza_link!r}"
    ))
    return f


def test_i_gruppi_senza_link_si_leggono_e_rispondono_per_gruppo(tmp_path):
    cfg = carica(_con_gruppi_senza_link(tmp_path, ["2262271623946575"]))
    assert cfg.gruppi_senza_link == ("2262271623946575",)
    assert cfg.commento_senza_link("2262271623946575")
    assert not cfg.commento_senza_link("")
    assert not cfg.commento_senza_link(None)


def test_di_default_nessun_gruppo_e_senza_link():
    cfg = carica(ESEMPIO)
    assert cfg.gruppi_senza_link == ()
    assert not cfg.commento_senza_link("2262271623946575")


def test_un_gruppo_senza_link_che_non_si_legge_ferma_il_caricamento(tmp_path):
    """Lo stesso gruppo ha uno slug e un numero: scritto con l'altro, la regola
    non aggancerebbe niente e i commenti uscirebbero col link come prima."""
    import pytest
    with pytest.raises(ValueError, match="1765622897069363"):
        carica(_con_gruppi_senza_link(tmp_path, ["1765622897069363"]))


def test_margine_e_passaggio_profondo_hanno_un_default(tmp_path):
    """Le config reali scritte prima del 03/09 non li nominano: devono
    accendersi da sole, non restare a zero."""
    testo = ESEMPIO.read_text().replace("margine_segnalibro_ore = 6\n", "").replace(
        "passaggio_profondo_dalle = 12\n", ""
    ).replace("passaggio_profondo_ore = 36\n", "")
    assert "margine_segnalibro_ore" not in testo
    f = tmp_path / "c.toml"
    f.write_text(testo)
    cfg = carica(f)
    assert cfg.margine_segnalibro_ore == 6
    assert cfg.passaggio_profondo_dalle == 12
    assert cfg.passaggio_profondo_ore == 36
