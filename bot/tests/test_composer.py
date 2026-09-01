"""Il prompt del composer, senza chiamare nessun modello."""
from pathlib import Path
from types import SimpleNamespace

from bot.composer import istruzioni
from bot.config import carica

ESEMPIO = Path(__file__).parent.parent / "config.toml.example"
ANALISI = SimpleNamespace(budget_max=None, zona="Monza", disponibile_da="", durata="")


def _cfg(tmp_path, senza_link=()):
    testo = ESEMPIO.read_text().replace(
        '"2262271623946575",   # AFFITTI Monza e Brianza - CERCO/OFFRO',
        '"2262271623946575", "muto",',
    ).replace("gruppi_senza_link = []", f"gruppi_senza_link = {list(senza_link)!r}")
    f = tmp_path / "c.toml"
    f.write_text(testo)
    return carica(f)


def _post(group_id):
    return SimpleNamespace(text="cerco stanza", group_id=group_id)


def test_di_norma_il_commento_porta_il_link_della_galleria(tmp_path):
    cfg = _cfg(tmp_path, senza_link=["muto"])
    prompt = istruzioni(cfg, _post("2262271623946575"), ANALISI, cfg.stanze_libere[:1])
    assert cfg.link_galleria in prompt
    assert "SENZA NESSUN LINK" not in prompt


def test_nei_gruppi_che_li_rifiutano_il_commento_e_senza_link(tmp_path):
    """Il link della galleria sparisce dal prompt del tutto: se restasse anche
    solo citato, il modello lo rimetterebbe nel commento."""
    cfg = _cfg(tmp_path, senza_link=["muto"])
    prompt = istruzioni(cfg, _post("muto"), ANALISI, cfg.stanze_libere[:1])
    assert cfg.link_galleria not in prompt
    assert "SENZA NESSUN LINK" in prompt
    assert cfg.link_post_fb in prompt      # il privato tiene l'annuncio completo


def test_senza_gruppo_si_ricade_sul_commento_col_link(tmp_path):
    cfg = _cfg(tmp_path, senza_link=["muto"])
    prompt = istruzioni(cfg, SimpleNamespace(text="x"), ANALISI, cfg.stanze_libere[:1])
    assert cfg.link_galleria in prompt
