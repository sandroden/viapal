from bot.notifier import _esc


def test_scappa_i_caratteri_che_romperebbero_markdownv2():
    assert _esc("470€ + spese (tutto)") == r"470€ \+ spese \(tutto\)"


def test_i_punti_nelle_cifre_non_rompono_il_messaggio():
    assert _esc("335 838.9194") == r"335 838\.9194"


def test_il_link_porta_in_chat_non_al_gruppo():
    """Il profilo dentro al gruppo l'app mobile non lo apre e ricade sul gruppo:
    m.me apre la conversazione, che è dove il messaggio va incollato."""
    from bot.notifier import _link
    from bot.scraper import Post

    post = Post(
        post_id="1", permalink="https://www.facebook.com/groups/9/user/42/",
        author_name="Anna", author_url="https://www.facebook.com/groups/9/user/42/",
        text="…", author_id="42", permalink_e_del_profilo=True,
    )
    link = _link(post)
    assert "https://m.me/42" in link
    assert "scrivi a Anna" in link
    assert "apri il post" not in link      # non c'è un post da aprire


def test_col_permalink_vero_compaiono_tutti_e_due():
    from bot.notifier import _link
    from bot.scraper import Post

    post = Post(
        post_id="1", permalink="https://www.facebook.com/groups/9/posts/7/",
        author_name="Anna", author_url="https://www.facebook.com/groups/9/user/42/",
        text="…", author_id="42",
    )
    link = _link(post)
    assert "https://m.me/42" in link and "/posts/7/" in link


def test_senza_id_non_si_inventa_un_link():
    from bot.notifier import _link
    from bot.scraper import Post

    post = Post(post_id="1", permalink="", author_name=None, author_url=None, text="…")
    assert _link(post) == ""


# --- gruppi che rifiutano i commenti con un link ------------------------------

def _testo_notifica(senza_link: bool, commento: str) -> str:
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from bot.notifier import Notifier
    from bot.scraper import Post

    post = Post(post_id="1", permalink="", author_name="Anna", author_url=None, text="…")
    analisi = SimpleNamespace(
        zona=None, budget_max=None, disponibile_da=None,
        stanze_compatibili=["camera-3"], motivo="ok",
    )
    messaggi = SimpleNamespace(commento_pubblico=commento, privato="p")
    with patch("bot.notifier.httpx.post", return_value=MagicMock(status_code=200)) as http:
        Notifier("t", "c").lead(post, analisi, messaggi, senza_link=senza_link)
    return http.call_args.kwargs["json"]["text"]


def test_la_notifica_dice_quando_il_commento_va_senza_link():
    testo = _testo_notifica(True, "Ciao, ti ho scritto in privato.")
    assert "senza link" in testo
    assert "⚠️" not in testo


def test_avvisa_se_il_commento_ha_un_link_dove_non_passa():
    """Passerebbe dal telefono a un gruppo che lo butta via in silenzio."""
    testo = _testo_notifica(True, "Foto qui: https://viapal.e-den.it/g/viapal")
    assert "⚠️" in testo and "non passerebbe" in testo


def test_col_link_ammesso_niente_etichetta_ne_avviso():
    testo = _testo_notifica(False, "Foto qui: https://viapal.e-den.it/g/viapal")
    assert "senza link" not in testo and "⚠️" not in testo


def test_contiene_link_riconosce_anche_gli_url_senza_schema():
    from bot.notifier import contiene_link
    assert contiene_link("le foto su viapal.e-den.it/g/viapal")
    assert contiene_link("www.esempio.it")
    assert not contiene_link("ti ho scritto in privato. A presto")
