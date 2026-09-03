"""L'identità di un post, l'arrivo tardivo del permalink e la regola di stop sull'ora."""
from datetime import datetime

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
         "marketplace": False, "raw": TESTO, "ora": None}
CON = dict(SENZA, post_id="7", permalink="https://www.facebook.com/groups/9/posts/7/")

# Il tooltip di Facebook, così come lo scrive lui.
ORA_NUOVA = "Mercoledì 2 settembre 2026 alle ore 22:30"
ORA_VECCHIA = "Mercoledì 2 settembre 2026 alle ore 21:00"
ORA_PIU_VECCHIA = "Mercoledì 2 settembre 2026 alle ore 20:30"

NUOVO = dict(CON, post_id="9", permalink="https://www.facebook.com/groups/9/posts/9/",
             raw="Nuovo post: cerco stanza a Monza da ottobre, sono referenziata", ora=ORA_NUOVA)
VECCHIO = dict(CON, post_id="8", permalink="https://www.facebook.com/groups/9/posts/8/",
               raw="Post di prima: cerco bilocale a Lissone, siamo in due", ora=ORA_VECCHIA)
PIU_VECCHIO = dict(CON, post_id="7", permalink="https://www.facebook.com/groups/9/posts/7/",
                   raw="Post ancora prima: offro camera singola a Muggiò", ora=ORA_PIU_VECCHIA)
OLTRE = dict(SENZA, raw="Post renderizzato oltre il fondo del viewport, mai a tiro di mouse")


class FintoBrowser:
    """Un browser che serve letture preconfezionate.

    Distingue le sonde dal loro JS: la diagnosi cerca `con_testo`, i bersagli
    dello sweep `botTentativi`, il timbro del tooltip `elementFromPoint`, la
    raccolta è quel che resta.
    """

    def __init__(self, letture, orari=(), tooltip=ORA_NUOVA):
        self._letture = iter(letture)
        self._orari = list(orari)
        self._tooltip = tooltip
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
        if "elementFromPoint" in js:
            return {"ora": self._tooltip, "stampato": True}
        if "botTentativi" in js:
            # dopo l'hover i post sono timbrati e smascherati: la rilettura è vuota
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

    post = scraper.raccogli(finto, "9", gia_visti=set(), max_scroll=2).post

    assert len(post) == 1
    assert post[0].post_id == "7"
    assert post[0].permalink.endswith("/posts/7/")
    assert post[0].permalink_e_del_profilo is False


def test_il_ripasso_in_coda_recupera_i_post_oltre_il_viewport():
    """Il DOM renderizza oltre il fondo del viewport: quei post sono raccolti
    ma l'orario non è mai stato a tiro di mouse. Il ripasso scende prima di
    risalire, e appena non manca niente si ferma."""
    finto = FintoBrowser([[SENZA], [CON]])

    post = scraper.raccogli(finto, "9", gia_visti=set(), max_scroll=1).post

    assert len(post) == 1
    assert post[0].permalink.endswith("/posts/7/")


def test_il_ripasso_risale_per_i_post_idratati_in_ritardo():
    """Un post idratato quando il suo orario era già sopra il viewport si
    smaschera solo tornando indietro (misurato sul campo: senza ripasso 7/10)."""
    finto = FintoBrowser([[SENZA], [], [], [], [CON]])

    post = scraper.raccogli(finto, "9", gia_visti=set(), max_scroll=1).post

    assert len(post) == 1
    assert post[0].permalink.endswith("/posts/7/")
    assert any(px < 0 for px in finto.scrollate), "il ripasso risale il feed"


def test_la_risalita_del_ripasso_ha_un_tetto():
    """Un solo post senza permalink dopo 90 passi di discesa non deve costare
    cinque minuti di risalita (misurato il 03/09 nel passaggio profondo)."""
    finto = FintoBrowser([[SENZA]])

    post = scraper.raccogli(finto, "9", gia_visti=set(), max_scroll=90).post

    assert len(post) == 1 and post[0].permalink_e_del_profilo
    risalite = [px for px in finto.scrollate if px < 0]
    assert len(risalite) == scraper.PASSI_MAX_RIPASSO


def test_l_id_arrivato_tardi_smaschera_anche_i_post_gia_in_database():
    """Raccolto id-less al passo 1, l'id vero al passo 2 rivela che il post è
    già in database: va TOLTO dai raccolti, o la persona viene ricontattata."""
    finto = FintoBrowser([[SENZA], [CON]])

    assert scraper.raccogli(finto, "9", gia_visti={"7"}, max_scroll=2).post == []


def test_il_post_noto_che_ricompare_senza_id_non_rientra():
    """Facebook rimaschera l'href quando reidrata un nodo: il post già tolto
    perché in archivio ripassa id-less un passo dopo, e non deve rientrare."""
    finto = FintoBrowser([[CON], [SENZA], [SENZA]])

    assert scraper.raccogli(finto, "9", gia_visti={"7"}, max_scroll=3).post == []


def test_lo_sweep_muove_il_mouse_su_ogni_orario_da_leggere():
    finto = FintoBrowser([], orari=[{"n": 0, "x": 10, "y": 200}, {"n": 1, "x": 10, "y": 480}])

    scraper._sweep_orari(finto)

    assert finto.hover == 2


def test_timbrato_il_post_il_suo_secondo_anchor_non_si_tocca():
    """Due anchor per post coprono gli ordinamenti strani: se il primo era
    l'orario e ha dato il tooltip, il secondo è tempo perso."""
    finto = FintoBrowser([], orari=[{"n": 0, "x": 10, "y": 200}, {"n": 0, "x": 10, "y": 230}])

    scraper._sweep_orari(finto)

    assert finto.hover == 1


def test_senza_orari_da_leggere_il_mouse_sta_fermo():
    finto = FintoBrowser([])

    scraper._sweep_orari(finto)

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


# --- l'ora del post e la regola di stop ---------------------------------------

def test_parse_ora_legge_il_tooltip_di_facebook():
    assert scraper.parse_ora("Mercoledì 2 settembre 2026 alle ore 16:23") == datetime(2026, 9, 2, 16, 23)
    assert scraper.parse_ora("Merc͏oledì 2 sett͏embre 2026 alle ore 16:23") == datetime(2026, 9, 2, 16, 23)
    assert scraper.parse_ora("Ieri alle 10:05", adesso=datetime(2026, 9, 2, 12, 0)) == datetime(2026, 9, 1, 10, 5)
    assert scraper.parse_ora("dreptnSsool54712hm6uicfiaag0l4lmg3n126fh8886807") is None
    assert scraper.parse_ora(None) is None


def test_l_ora_arrivata_dopo_aggiorna_il_post_e_il_segnalibro():
    finto = FintoBrowser([[SENZA], [dict(CON, ora=ORA_NUOVA)]])

    lettura = scraper.raccogli(finto, "9", gia_visti=set(), max_scroll=2)

    assert lettura.post[0].ora == "2026-09-02T22:30"
    assert lettura.ultima_ora == datetime(2026, 9, 2, 22, 30)


def test_si_ferma_appena_rivede_due_post_non_piu_recenti_dell_ultima_lettura():
    """Feed cronologico: dopo il segnalibro c'è solo roba già letta. Un passo
    minimo, poi stop; i post oltre il punto di stop, mai a tiro di mouse, non
    tornano come nuovi e non tengono in piedi il ripasso."""
    finto = FintoBrowser([[NUOVO, VECCHIO, PIU_VECCHIO, OLTRE]] * 4)

    lettura = scraper.raccogli(
        finto, "9", gia_visti={"8", "7"}, max_scroll=10, ultima_ora=datetime(2026, 9, 2, 21, 0),
    )

    assert [p.post_id for p in lettura.post] == ["9"]
    assert lettura.ultima_ora == datetime(2026, 9, 2, 22, 30)
    assert finto.scrollate == [600]


def test_senza_segnalibro_comanda_l_orizzonte():
    """Primo giro su un gruppo: senza limite si leggerebbe tutto il feed. I
    post più vecchi dell'orizzonte valgono come già visti."""
    finto = FintoBrowser([[NUOVO, VECCHIO, PIU_VECCHIO]] * 4)

    lettura = scraper.raccogli(
        finto, "9", gia_visti=set(), max_scroll=10, orizzonte=datetime(2026, 9, 2, 21, 30),
    )

    assert [p.post_id for p in lettura.post] == ["9"]
    assert finto.scrollate == [600]


def test_i_post_senza_ora_non_interrompono_la_striscia():
    limite = datetime(2026, 9, 2, 21, 30)
    assert scraper._indice_stop([VECCHIO, OLTRE, PIU_VECCHIO], limite) == 2


def test_un_post_nuovo_azzera_la_striscia():
    limite = datetime(2026, 9, 2, 21, 30)
    assert scraper._indice_stop([VECCHIO, NUOVO, PIU_VECCHIO], limite) is None


def test_il_post_oltre_il_fondo_svuotato_prima_dello_stop_non_torna_come_nuovo():
    """Raccolto oltre il fondo del viewport al passo 0, al passo dello stop non
    è più nel DOM (virtualizzazione): senza ora e senza id, è vecchio per
    posizione. Non deve tornare come nuovo né far partire il ripasso."""
    finto = FintoBrowser([[NUOVO, VECCHIO, PIU_VECCHIO, OLTRE], [NUOVO, VECCHIO, PIU_VECCHIO]])

    lettura = scraper.raccogli(
        finto, "9", gia_visti={"8", "7"}, max_scroll=10, ultima_ora=datetime(2026, 9, 2, 21, 0),
    )

    assert [p.post_id for p in lettura.post] == ["9"]
    assert finto.scrollate == [600]
