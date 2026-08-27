"""L'identità di un post quando Facebook non dà il permalink."""
from bot.scraper import _impronta


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


def test_il_permalink_comparso_dopo_viene_raccolto(monkeypatch):
    """Il permalink compare quando lo scroll fa idratare il post: se a un passo
    successivo c'è, va preso anche se il testo è rimasto identico."""
    from bot import scraper

    testo = "Cerco una stanza singola a Monza da settembre, sono referenziato"
    senza = {"post_id": None, "permalink": None, "author_name": "Anna",
             "author_url": "https://fb.com/groups/9/user/42/", "author_id": "42",
             "marketplace": False, "raw": testo}
    con = dict(senza, permalink="https://www.facebook.com/groups/9/posts/7/")

    letture = iter([[senza], [con]])
    finto = type("B", (), {
        "apri": lambda self, url: None,
        "scorri": lambda self, px=0: None,
        "valuta": lambda self, js: (
            '{"feed": true, "figli": 1, "con_testo": 1}'
            if "con_testo" in js else next(letture, [])
        ),
    })()
    monkeypatch.setattr(scraper.time, "sleep", lambda s: None)

    post = scraper.raccogli(finto, "9", gia_visti=set(), max_scroll=2)  # due passi
    assert len(post) == 1
    assert post[0].permalink.endswith("/posts/7/")
    assert post[0].permalink_e_del_profilo is False
