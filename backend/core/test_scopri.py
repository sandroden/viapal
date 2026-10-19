"""Meta Open Graph della pagina pubblica /scopri (core/scopri.py)."""

import pytest


@pytest.mark.parametrize("percorso", ["/scopri", "/scopri/"])
def test_scopri_espone_meta_video(client, percorso):
    risposta = client.get(percorso)

    assert risposta.status_code == 200
    html = risposta.content.decode()
    assert "<title>Viapal — il gestionale per chi affitta camere</title>" in html
    assert 'property="og:image" content="http://testserver/media/scopri/anteprima.jpg"' in html
    assert 'property="og:video" content="http://testserver/media/scopri/viapal-demo.mp4"' in html
    # L'URL canonico non si porta dietro la query di chi ha condiviso.
    assert 'property="og:url" content="http://testserver/scopri' in html


def test_scopri_canonico_senza_query(client):
    html = client.get("/scopri?fbclid=abc").content.decode()

    assert "fbclid" not in html
