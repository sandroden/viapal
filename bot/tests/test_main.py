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
    author_id: str | None = None


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


def test_gli_anonimi_diversi_non_si_annullano_a_vicenda():
    """Due «Partecipante anonimo» hanno entrambi author_url vuoto: accorparli
    per quello butterebbe via un lead vero. Li distingue il testo."""
    from bot.main import _da_leggere
    anonimi = [
        FintoPost(post_id="1", author_url=None, text="cerco stanza a Monza"),
        FintoPost(post_id="2", author_url=None, text="cerco stanza a Brugherio"),
    ]
    assert len(_da_leggere(anonimi, set())) == 2


def test_la_stessa_persona_in_due_gruppi_e_una_persona_sola():
    """author_url porta dentro il gruppo, l'uid no: confrontare gli URL fa
    ripassare chi è già stato contattato altrove."""
    from bot.main import _da_leggere
    stessa = [
        FintoPost(post_id="1", author_url="https://www.facebook.com/groups/111/user/999/",
                  author_id="999"),
        FintoPost(post_id="2", author_url="https://www.facebook.com/groups/222/user/999/",
                  author_id="999"),
    ]
    assert [p.post_id for p in _da_leggere(stessa, set())] == ["1"]


def test_chi_e_gia_contattato_in_un_altro_gruppo_non_ripassa():
    """È il caso vero: in archivio c'è l'URL del gruppo storico, il post nuovo
    arriva dall'altro gruppo con un URL diverso e lo stesso uid."""
    from bot.main import _da_leggere
    archivio = {"https://www.facebook.com/groups/2262271623946575/user/100000861947114/"}
    nuovo = [FintoPost(
        post_id="9",
        author_url="https://www.facebook.com/groups/2390898511097164/user/100000861947114/",
        author_id="100000861947114")]
    assert _da_leggere(nuovo, archivio) == []


def test_lo_stesso_post_ripescato_in_anonimo_non_raddoppia():
    """Lo stesso annuncio compare due volte, una con il nome e una anonimo:
    senza autore resta il testo a dire che è lo stesso."""
    from bot.main import _da_leggere
    testo = "Cerco una stanza a Monza, sono una docente. Budget 500€"
    doppio = [
        FintoPost(post_id="1", author_url=None, author_id=None, text=testo + " · 3 commenti"),
        FintoPost(post_id="2", author_url=None, author_id=None, text=testo + " · 7 commenti"),
    ]
    assert len(_da_leggere(doppio, set())) == 1


# --- gruppi che rifiutano i commenti con un link ------------------------------

def _config_con_gruppo_senza_link(tmp_path: Path) -> Path:
    testo = (
        ESEMPIO.read_text()
        .replace("METTI-QUI-IL-CHAT-ID", "1")
        .replace('"2262271623946575",   # AFFITTI Monza e Brianza - CERCO/OFFRO',
                 '"2262271623946575", "muto",')
        .replace("gruppi_senza_link = []", 'gruppi_senza_link = ["muto"]')
    )
    f = tmp_path / "c.toml"
    f.write_text(testo)
    return f


def test_estrai_marca_i_post_dei_gruppi_senza_link(tmp_path):
    """Il flag sta sul post: chi legge il JSON (Claude) non deve incrociare
    liste di gruppi, deve vederlo accanto al testo."""
    import json
    from bot.main import estrai
    from bot.scraper import Post

    def finto_raccogli(browser, gid, **kw):
        return [Post(
            post_id=f"{gid}-1", permalink="", author_name="A",
            author_url=f"https://fb.com/groups/{gid}/user/{gid}/",
            text="x" * 50, author_id=gid, group_id=gid,
        )]

    uscita = tmp_path / "post.json"
    with patch("bot.main.raccogli", side_effect=finto_raccogli), patch("bot.main.Browser"):
        estrai(str(_config_con_gruppo_senza_link(tmp_path)), str(tmp_path / "t.db"), str(uscita))
    per_gruppo = {
        p["group_id"]: p["commento_senza_link"]
        for p in json.loads(uscita.read_text())["post"]
    }
    assert per_gruppo == {"2262271623946575": False, "muto": True}


def test_notifica_dice_al_notifier_quale_commento_va_senza_link(tmp_path):
    import json
    from bot.main import notifica

    lead = {"lead": [
        {"post_id": "1", "author_id": "1", "text": "x", "group_id": "muto",
         "commento_pubblico": "ciao", "privato": "ciao"},
        {"post_id": "2", "author_id": "2", "text": "x", "group_id": "2262271623946575",
         "commento_pubblico": "ciao", "privato": "ciao"},
    ], "scartati": []}
    sorgente = tmp_path / "lead.json"
    sorgente.write_text(json.dumps(lead))
    with patch("bot.main.Notifier") as notifier, patch("bot.main.spedisci_coda"):
        notifica(str(_config_con_gruppo_senza_link(tmp_path)), str(tmp_path / "t.db"), str(sorgente))
    flag = [c.kwargs["senza_link"] for c in notifier.return_value.lead.call_args_list]
    assert flag == [True, False]
