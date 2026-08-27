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
