"""Test del giro: quello che il dry-run deve e non deve toccare."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from bot.main import giro
from bot.scraper import Lettura
from bot.storage import Archivio

GRUPPO_ESEMPIO = "2262271623946575"
LETTO_FINO_A = datetime(2026, 9, 2, 22, 16)

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
        patch("bot.main.raccogli", return_value=Lettura([FintoPost()], LETTO_FINO_A, letti=1)),
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
    assert archivio.ultima_ora(GRUPPO_ESEMPIO) is None, "la prova non sposta il segnalibro"
    notifier.lead.assert_not_called()


def test_il_giro_vero_registra_e_notifica(tmp_path):
    archivio, notifier = _giro(tmp_path, dry_run=False)
    assert archivio.id_visti() == {"111"}
    assert archivio.ultima_ora(GRUPPO_ESEMPIO) == LETTO_FINO_A
    notifier.lead.assert_called_once()


# --- più gruppi nello stesso giro -------------------------------------------

@dataclass
class FintaConfig:
    gruppi: tuple
    scroll_stop_after_seen: int = 10
    max_scroll: int = 5
    orizzonte_giorni: int = 3
    margine_segnalibro_ore: int = 6
    passaggio_profondo_dalle: int = -1     # spento: si accende nel test apposta
    passaggio_profondo_ore: int = 36


def test_ogni_gruppo_viene_letto_e_i_post_si_sommano(tmp_path):
    from bot.main import _raccogli_dai_gruppi
    letti = []

    def finto_raccogli(browser, gid, **kw):
        letti.append(gid)
        return Lettura([FintoPost(post_id=f"{gid}-1")], letti=5)

    with patch("bot.main.raccogli", side_effect=finto_raccogli):
        post, falliti = _raccogli_dai_gruppi(None, FintaConfig(("a", "b")), Archivio(tmp_path / "t.db"))
    assert letti == ["a", "b"]
    assert [p.post_id for p in post] == ["a-1", "b-1"]
    assert falliti == []


def test_il_gruppo_muto_viene_segnalato(tmp_path):
    """Con l'archivio pieno `raccogli` non grida più: un feed vuoto e "non sono
    iscritto a quel gruppo" si somigliano troppo per lasciarli uguali. Zero
    post NUOVI invece è il giro normale, e non va segnalato."""
    from bot.main import _raccogli_dai_gruppi
    archivio = Archivio(tmp_path / "t.db")
    archivio.registra(FintoPost(post_id="x"))
    letture = [Lettura([FintoPost()], letti=4), Lettura([], letti=0), Lettura([], letti=6)]
    with patch("bot.main.raccogli", side_effect=letture):
        post, falliti = _raccogli_dai_gruppi(None, FintaConfig(("a", "b", "c")), archivio)
    assert len(post) == 1
    assert [gid for gid, _ in falliti] == ["b"]


def test_ogni_gruppo_riparte_dal_suo_segnalibro(tmp_path):
    """Il segnalibro è per gruppo: quello del gruppo storico non deve far
    saltare i post del gruppo aggiunto ieri."""
    from bot.main import _raccogli_dai_gruppi
    archivio = Archivio(tmp_path / "t.db")
    archivio.segna_lettura("a", LETTO_FINO_A)
    archivio.conferma_letture()
    segnalibri = {}

    def finto_raccogli(browser, gid, **kw):
        segnalibri[gid] = kw["ultima_ora"]
        return Lettura([])

    with patch("bot.main.raccogli", side_effect=finto_raccogli):
        _raccogli_dai_gruppi(None, FintaConfig(("a", "b"), margine_segnalibro_ore=0), archivio)
    assert segnalibri == {"a": LETTO_FINO_A, "b": None}


def test_lo_scroll_scende_qualche_ora_sotto_il_segnalibro(tmp_path):
    """Nei gruppi moderati un post compare all'approvazione con l'ora in cui
    è stato scritto: fermarsi esattamente al segnalibro lo perde per sempre
    (7 su ~46 in un giorno, misurato il 03/09)."""
    from datetime import timedelta
    from bot.main import _raccogli_dai_gruppi
    archivio = Archivio(tmp_path / "t.db")
    archivio.segna_lettura("a", LETTO_FINO_A)
    archivio.conferma_letture()
    segnalibri = {}

    def finto_raccogli(browser, gid, **kw):
        segnalibri[gid] = kw["ultima_ora"]
        return Lettura([])

    with patch("bot.main.raccogli", side_effect=finto_raccogli):
        _raccogli_dai_gruppi(None, FintaConfig(("a", "b"), margine_segnalibro_ore=6), archivio)
    assert segnalibri == {"a": LETTO_FINO_A - timedelta(hours=6), "b": None}


def _segnalibri_del_giro(cfg, archivio, adesso):
    from bot.main import _raccogli_dai_gruppi
    segnalibri = {}

    def finto_raccogli(browser, gid, **kw):
        segnalibri[gid] = kw["ultima_ora"]
        return Lettura([])

    with patch("bot.main.raccogli", side_effect=finto_raccogli):
        _raccogli_dai_gruppi(None, cfg, archivio, adesso=adesso)
    return segnalibri


def test_il_passaggio_profondo_e_uno_al_giorno_e_un_gruppo_per_giro(tmp_path):
    """Da mezzogiorno in poi ogni gruppo si legge una volta senza segnalibro,
    ma uno solo per giro: un passaggio profondo costa minuti, e --estrai deve
    restare sotto il timeout di /affitti. Il giorno dopo si ricomincia."""
    archivio = Archivio(tmp_path / "t.db")
    for gid in ("a", "b"):
        archivio.segna_lettura(gid, LETTO_FINO_A)
    archivio.conferma_letture()
    cfg = FintaConfig(("a", "b"), margine_segnalibro_ore=0, passaggio_profondo_dalle=12)

    mattina = datetime(2026, 9, 4, 11, 59)
    assert _segnalibri_del_giro(cfg, archivio, mattina) == {"a": LETTO_FINO_A, "b": LETTO_FINO_A}

    mezzogiorno = datetime(2026, 9, 4, 12, 5)
    assert _segnalibri_del_giro(cfg, archivio, mezzogiorno) == {"a": None, "b": LETTO_FINO_A}
    assert _segnalibri_del_giro(cfg, archivio, mezzogiorno) == {"a": LETTO_FINO_A, "b": None}
    assert _segnalibri_del_giro(cfg, archivio, mezzogiorno) == {"a": LETTO_FINO_A, "b": LETTO_FINO_A}

    domani = datetime(2026, 9, 5, 15, 0)
    assert _segnalibri_del_giro(cfg, archivio, domani) == {"a": None, "b": LETTO_FINO_A}


def test_il_passaggio_profondo_guarda_indietro_di_36_ore_non_di_3_giorni(tmp_path):
    """Tre giorni sul gruppo grande sono 7 minuti: con gli altri gruppi
    dietro si sfora il timeout di /affitti."""
    from datetime import timedelta
    from bot.main import _raccogli_dai_gruppi
    archivio = Archivio(tmp_path / "t.db")
    cfg = FintaConfig(("a", "b"), passaggio_profondo_dalle=12, orizzonte_giorni=3)
    adesso = datetime(2026, 9, 4, 12, 5)
    orizzonti = {}

    def finto_raccogli(browser, gid, **kw):
        orizzonti[gid] = kw["orizzonte"]
        return Lettura([])

    with patch("bot.main.raccogli", side_effect=finto_raccogli):
        _raccogli_dai_gruppi(None, cfg, archivio, adesso=adesso)
    assert orizzonti == {"a": adesso - timedelta(hours=36), "b": adesso - timedelta(days=3)}


def test_il_passaggio_profondo_fallito_si_ritenta_al_giro_dopo(tmp_path):
    from bot.main import _raccogli_dai_gruppi
    from bot.scraper import MarkupCambiato
    archivio = Archivio(tmp_path / "t.db")
    cfg = FintaConfig(("a",), passaggio_profondo_dalle=12)
    adesso = datetime(2026, 9, 4, 12, 5)
    with patch("bot.main.raccogli", side_effect=MarkupCambiato("feed vuoto")):
        _, falliti = _raccogli_dai_gruppi(None, cfg, archivio, adesso=adesso)
    assert [g for g, _ in falliti] == ["a"]
    assert archivio.profondo_fatto_il("a") is None
    assert _segnalibri_del_giro(cfg, archivio, adesso) == {"a": None}


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
        return Lettura([Post(
            post_id=f"{gid}-1", permalink="", author_name="A",
            author_url=f"https://fb.com/groups/{gid}/user/{gid}/",
            text="x" * 50, author_id=gid, group_id=gid,
        )])

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


# --- il segnalibro fra --estrai e --notifica ----------------------------------

def _post_vero():
    from bot.scraper import Post
    return Post(post_id="111", permalink="", author_name="A", author_url="https://fb.com/u/1",
                text="x" * 50, author_id="1", group_id=GRUPPO_ESEMPIO)


def test_estrai_annota_il_segnalibro_e_notifica_lo_conferma(tmp_path):
    """Se Claude non arriva a --notifica (giro ucciso), il giro dopo deve
    rileggere gli stessi post: il segnalibro avanza solo alla conferma."""
    import json
    from bot.main import estrai, notifica

    db = tmp_path / "t.db"
    with (
        patch("bot.main.raccogli", return_value=Lettura([_post_vero()], LETTO_FINO_A, letti=3)),
        patch("bot.main.Browser"),
    ):
        estrai(str(_config_con_token(tmp_path)), str(db), str(tmp_path / "post.json"))
    assert Archivio(db).ultima_ora(GRUPPO_ESEMPIO) is None

    sorgente = tmp_path / "lead.json"
    sorgente.write_text(json.dumps({"lead": [], "scartati": []}))
    with patch("bot.main.Notifier"), patch("bot.main.spedisci_coda"):
        notifica(str(_config_con_token(tmp_path)), str(db), str(sorgente))
    assert Archivio(db).ultima_ora(GRUPPO_ESEMPIO) == LETTO_FINO_A


def test_con_zero_post_estrai_conferma_da_solo_il_segnalibro(tmp_path):
    """Il comando /affitti a zero post non chiama --notifica: senza questo il
    segnalibro non avanzerebbe mai nei giri a vuoto, che sono la maggioranza."""
    from bot.main import estrai

    db = tmp_path / "t.db"
    with (
        patch("bot.main.raccogli", return_value=Lettura([], LETTO_FINO_A, letti=3)),
        patch("bot.main.Browser"),
    ):
        estrai(str(_config_con_token(tmp_path)), str(db), str(tmp_path / "post.json"))
    assert Archivio(db).ultima_ora(GRUPPO_ESEMPIO) == LETTO_FINO_A
