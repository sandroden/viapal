from dataclasses import dataclass

from bot.storage import Archivio


@dataclass
class FintoPost:
    post_id: str
    permalink: str = "https://fb.com/p/1"
    author_name: str = "Tizio"
    author_url: str | None = "https://fb.com/u/1"
    text: str = "Cerco stanza"


def test_il_secondo_giro_non_ripropone_il_primo(tmp_path):
    a = Archivio(tmp_path / "t.db")
    a.registra(FintoPost("1"))
    assert a.id_visti() == {"1"}


def test_chi_e_stato_contattato_non_si_ricontatta(tmp_path):
    a = Archivio(tmp_path / "t.db")
    a.registra(FintoPost("1"), matched=True, notificato=True)
    a.registra(FintoPost("2", author_url="https://fb.com/u/2"), matched=False)
    assert a.autori_gia_contattati() == {"https://fb.com/u/1"}


def test_rivedere_lo_stesso_post_non_lo_duplica(tmp_path):
    a = Archivio(tmp_path / "t.db")
    a.registra(FintoPost("1"))
    a.registra(FintoPost("1"))
    assert a.statistiche()["totali"] == 1
