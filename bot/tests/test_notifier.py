from bot.notifier import _esc


def test_scappa_i_caratteri_che_romperebbero_markdownv2():
    assert _esc("470€ + spese (tutto)") == r"470€ \+ spese \(tutto\)"


def test_i_punti_nelle_cifre_non_rompono_il_messaggio():
    assert _esc("335 838.9194") == r"335 838\.9194"
