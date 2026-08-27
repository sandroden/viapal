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
