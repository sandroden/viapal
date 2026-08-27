"""L'identità di un post e l'arrivo tardivo del permalink smascherato."""
import pytest

from bot import scraper
from bot.scraper import _impronta, _integra


def test_lo_stesso_post_ha_sempre_la_stessa_impronta():
    a = _impronta("https://fb.com/u/1", "Cerco stanza a Monza da settembre")
    b = _impronta("https://fb.com/u/1", "Cerco stanza a Monza da settembre")
    assert a == b


def test_i_contatori_che_cambiano_non_creano_un_post_nuovo():
    """Reazioni e commenti crescono nel corso della giornata sullo stesso post:
    se entrassero nell'impronta, ogni giro lo vedrebbe come nuovo."""
    a = _impronta("https://fb.com/u/1", "Cerco stanza a Monza\n3\n2")
    b = _impronta("https://fb.com/u/1", "Cerco stanza a Monza\n7\n5")
    assert a == b


def test_autori_diversi_con_lo_stesso_testo_restano_distinti():
    a = _impronta("https://fb.com/u/1", "Cerco stanza a Monza")
    b = _impronta("https://fb.com/u/2", "Cerco stanza a Monza")
    assert a != b


def test_post_diversi_dello_stesso_autore_restano_distinti():
    a = _impronta("https://fb.com/u/1", "Cerco stanza a Monza")
    b = _impronta("https://fb.com/u/1", "Cerco stanza a Villasanta")
    assert a != b


TESTO = "Cerco una stanza singola a Monza da settembre, sono referenziato"
SENZA = {"post_id": None, "permalink": None, "author_name": "Anna",
         "author_url": "https://fb.com/groups/9/user/42/", "author_id": "42",
         "marketplace": False, "raw": TESTO}
CON = dict(SENZA, post_id="7", permalink="https://www.facebook.com/groups/9/posts/7/")


class FintoBrowser:
    """Un browser che serve letture preconfezionate.

    Distingue le tre sonde dal loro JS: la diagnosi cerca `con_testo`, lo sweep
    degli orari `getBoundingClientRect`, la raccolta è quel che resta.
    """

    def __init__(self, letture, orari=()):
        self._letture = iter(letture)
        self._orari = list(orari)
        self.hover = 0
        self.scrollate = []

    def apri(self, url):
        pass

    def scorri(self, px=0):
        self.scrollate.append(px)

    def muovi_mouse(self, x, y):
        self.hover += 1

    def valuta(self, js):
        if "con_testo" in js:
            return '{"feed": true, "figli": 1, "con_testo": 1}'
        if "getBoundingClientRect" in js:
            # dopo l'hover gli anchor sono smascherati: la rilettura è vuota
            serviti, self._orari = self._orari, []
            return serviti
        return next(self._letture, [])


@pytest.fixture(autouse=True)
def _niente_pause(monkeypatch):
    monkeypatch.setattr(scraper.time, "sleep", lambda s: None)


def test_il_permalink_smascherato_dopo_aggiorna_senza_duplicare():
    """Il mouse passa sull'orario spesso un passo DOPO la prima raccolta:
    l'id vero che compare deve aggiornare il post, non aggiungerne un secondo."""
    finto = FintoBrowser([[SENZA], [CON]])

    post = scraper.raccogli(finto, "9", gia_visti=set(), max_scroll=2)

    assert len(post) == 1
    assert post[0].post_id == "7"
    assert post[0].permalink.endswith("/posts/7/")
    assert post[0].permalink_e_del_profilo is False


def test_il_ripasso_in_coda_recupera_i_post_oltre_il_viewport():
    """Il DOM renderizza oltre il fondo del viewport: quei post sono raccolti
    ma l'orario non è mai stato a tiro di mouse. Il ripasso scende prima di
    risalire, e appena non manca niente si ferma."""
    finto = FintoBrowser([[SENZA], [CON]])

    post = scraper.raccogli(finto, "9", gia_visti=set(), max_scroll=1)

    assert len(post) == 1
    assert post[0].permalink.endswith("/posts/7/")


def test_il_ripasso_risale_per_i_post_idratati_in_ritardo():
    """Un post idratato quando il suo orario era già sopra il viewport si
    smaschera solo tornando indietro (misurato sul campo: senza ripasso 7/10)."""
    finto = FintoBrowser([[SENZA], [], [], [], [CON]])

    post = scraper.raccogli(finto, "9", gia_visti=set(), max_scroll=1)

    assert len(post) == 1
    assert post[0].permalink.endswith("/posts/7/")
    assert any(px < 0 for px in finto.scrollate), "il ripasso risale il feed"


def test_l_id_arrivato_tardi_smaschera_anche_i_post_gia_in_database():
    """Raccolto id-less al passo 1, l'id vero al passo 2 rivela che il post è
    già in database: va TOLTO dai raccolti, o la persona viene ricontattata."""
    finto = FintoBrowser([[SENZA], [CON]])

    post = scraper.raccogli(finto, "9", gia_visti={"7"}, max_scroll=2)

    assert post == []


def test_lo_sweep_muove_il_mouse_su_ogni_orario_mascherato():
    finto = FintoBrowser([], orari=[{"x": 10, "y": 200}, {"x": 10, "y": 480}])

    scraper._smaschera_orari(finto)

    assert finto.hover == 2


def test_senza_orari_mascherati_il_mouse_sta_fermo():
    finto = FintoBrowser([])

    scraper._smaschera_orari(finto)

    assert finto.hover == 0


def test_integra_tiene_il_testo_piu_lungo():
    """A parità di impronta (le cifre non contano) il testo può crescere,
    per esempio quando compaiono contatori: si tiene il più lungo."""
    prima = dict(SENZA, raw=TESTO + " 3")
    dopo = dict(SENZA, raw=TESTO + " 375")
    raccolti = {}
    _integra([prima], raccolti, set(), 0)
    _integra([dopo], raccolti, set(), 0)

    assert len(raccolti) == 1
    assert list(raccolti.values())[0].text.endswith("375")
