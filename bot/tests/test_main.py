"""Test del giro: quello che il dry-run deve e non deve toccare."""
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

from bot.main import giro
from bot.storage import Archivio

ESEMPIO = Path(__file__).parent.parent / "config.toml.example"


@dataclass
class FintoPost:
    post_id: str = "111"
    permalink: str = "https://fb.com/p/111"
    author_name: str = "Tizio"
    author_url: str | None = "https://fb.com/u/1"
    text: str = "Cerco una stanza singola a Monza da settembre"
    troncato: bool = False


def _config_con_token(tmp_path: Path) -> Path:
    testo = ESEMPIO.read_text().replace("METTI-QUI-IL-CHAT-ID", "1")
    f = tmp_path / "c.toml"
    f.write_text(testo)
    return f


def _giro(tmp_path, dry_run: bool):
    analisi = MagicMock(match=True, stanze_compatibili=["camera-3"], budget_max=None)
    analisi.model_dump.return_value = {}
    db = tmp_path / "t.db"
    with (
        patch("bot.main.raccogli", return_value=[FintoPost()]),
        patch("bot.main.Browser"),
        patch("bot.main.anthropic.Anthropic"),
        patch("bot.main.analizza", return_value=analisi),
        patch("bot.main.componi", return_value=MagicMock(commento_pubblico="a", privato="b")),
        patch("bot.main.Notifier") as notifier,
    ):
        giro(str(_config_con_token(tmp_path)), str(db), dry_run=dry_run, ignora_orario=True)
    return Archivio(db), notifier.return_value


def test_la_prova_non_sporca_il_database(tmp_path):
    """Se il dry-run registrasse i post, al giro vero risulterebbero già visti
    e i lead visti in prova non arriverebbero mai su Telegram."""
    archivio, notifier = _giro(tmp_path, dry_run=True)
    assert archivio.id_visti() == set()
    notifier.lead.assert_not_called()


def test_il_giro_vero_registra_e_notifica(tmp_path):
    archivio, notifier = _giro(tmp_path, dry_run=False)
    assert archivio.id_visti() == {"111"}
    notifier.lead.assert_called_once()


# --- più gruppi nello stesso giro -------------------------------------------

@dataclass
class FintaConfig:
    gruppi: tuple
    scroll_stop_after_seen: int = 10
    max_scroll: int = 5


def test_ogni_gruppo_viene_letto_e_i_post_si_sommano():
    from bot.main import _raccogli_dai_gruppi
    letti = []

    def finto_raccogli(browser, gid, **kw):
        letti.append(gid)
        return [FintoPost(post_id=f"{gid}-1")]

    with patch("bot.main.raccogli", side_effect=finto_raccogli):
        post, falliti = _raccogli_dai_gruppi(None, FintaConfig(("a", "b")), set())
    assert letti == ["a", "b"]
    assert [p.post_id for p in post] == ["a-1", "b-1"]
    assert falliti == []


def test_il_gruppo_muto_viene_segnalato():
    """Con l'archivio pieno `raccogli` non grida più: zero post e "non sono
    iscritto a quel gruppo" si somigliano troppo per lasciarli uguali."""
    from bot.main import _raccogli_dai_gruppi
    with patch("bot.main.raccogli", side_effect=[[FintoPost()], []]):
        post, falliti = _raccogli_dai_gruppi(None, FintaConfig(("a", "b")), {"x"})
    assert len(post) == 1
    assert [gid for gid, _ in falliti] == ["b"]


def test_chi_posta_in_due_gruppi_si_legge_una_volta_sola():
    from bot.main import _da_leggere
    doppio = [
        FintoPost(post_id="1", author_url="https://fb.com/u/9"),
        FintoPost(post_id="2", author_url="https://fb.com/u/9"),
        FintoPost(post_id="3", author_url="https://fb.com/u/7"),
    ]
    assert [p.post_id for p in _da_leggere(doppio, set())] == ["1", "3"]


def test_gli_anonimi_senza_profilo_non_si_annullano_a_vicenda():
    """Due «Partecipante anonimo» diversi hanno author_url vuoto: accorparli
    per quello butterebbe via un lead vero."""
    from bot.main import _da_leggere
    anonimi = [FintoPost(post_id="1", author_url=None), FintoPost(post_id="2", author_url=None)]
    assert len(_da_leggere(anonimi, set())) == 2
