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
