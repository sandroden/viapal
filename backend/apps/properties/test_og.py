"""Anteprime social della galleria pubblica (properties/og.py).

Quello che conta qui non si vede a schermo: sono i meta tag che i crawler
di WhatsApp & co. leggono, e il JPEG che ne deriva.
"""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from properties.models import GalleryImage, Property, Room


def _foto(nome="stanza.webp", colore=(120, 160, 90), formato="WEBP", dimensioni=(800, 600)):
    buffer = io.BytesIO()
    Image.new("RGB", dimensioni, colore).save(buffer, formato)
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type=f"image/{formato.lower()}")


@pytest.fixture
def annuncio(db, immobile):
    """Immobile pubblicato con hero e una camera fotografata."""
    immobile.pubblica = True
    immobile.slug = "immobile-test"
    immobile.indirizzo = "Via Palestrina 1, Monza"
    immobile.testi_pubblici = {
        "hero_titolo": "Casa di Via Palestrina",
        "hero_eyebrow": "Stanza in condivisione · disponibile",
        "facts": {"mq_totali": 180, "n_camere": 5, "n_bagni": 2},
    }
    immobile.foto_hero = _foto("hero.webp", (200, 120, 80))
    immobile.save()
    camera = Room.objects.create(
        property=immobile, nome="Camera Blu", pubblica=True, prezzo_mensile=390, ordinamento=1
    )
    GalleryImage.objects.create(property=immobile, room=camera, image=_foto())
    return immobile, camera


def _meta(html, chiave, attributo="property"):
    import re

    trovato = re.search(
        rf'<meta {attributo}="{chiave}" content="([^"]*)">', html
    )
    return trovato.group(1) if trovato else None


@pytest.mark.django_db
class TestPaginaOG:
    def test_immobile_pubblicato_espone_i_meta(self, client, annuncio):
        immobile, _ = annuncio
        html = client.get(f"/g/{immobile.slug}").content.decode()

        assert _meta(html, "og:title") == "Casa di Via Palestrina"
        assert "Stanza in condivisione" in _meta(html, "og:description")
        assert "180 m²" in _meta(html, "og:description")
        assert _meta(html, "og:url").endswith(f"/g/{immobile.slug}")
        assert f"/api/v1/public/og-image/{immobile.slug}.jpg" in _meta(html, "og:image")
        assert _meta(html, "og:image:width") == "1200"
        assert _meta(html, "twitter:card", attributo="name") == "summary_large_image"

    def test_immobile_non_pubblicato_e_404(self, client, immobile):
        immobile.slug = "riservato"
        immobile.save()
        assert client.get("/g/riservato").status_code == 404

    def test_slug_sconosciuto_restituisce_la_spa_con_404(self, client, monkeypatch):
        monkeypatch.setattr(
            "properties.og._scarica_index", lambda: "<html><head></head><body>SPA</body></html>"
        )
        risposta = client.get("/g/non-esiste")
        assert risposta.status_code == 404
        assert b"SPA" in risposta.content

    def test_link_di_una_camera_ha_titolo_e_url_propri(self, client, annuncio):
        immobile, camera = annuncio
        html = client.get(f"/g/{immobile.slug}?stanza={camera.pk}").content.decode()

        assert _meta(html, "og:title").startswith("Camera Blu — ")
        assert "390 €/mese" in _meta(html, "og:description")
        # og:url deve ripetere il parametro: senza, i social considerano i
        # cinque link della casa un unico URL e mostrano tutti la stessa card.
        assert _meta(html, "og:url").endswith(f"/g/{immobile.slug}?stanza={camera.pk}")
        assert f"stanza={camera.pk}" in _meta(html, "og:image")

    def test_camera_di_un_altro_immobile_viene_ignorata(self, client, annuncio, immobile2):
        immobile, _ = annuncio
        intrusa = Room.objects.create(property=immobile2, nome="Camera Altrui", pubblica=True)
        html = client.get(f"/g/{immobile.slug}?stanza={intrusa.pk}").content.decode()
        assert _meta(html, "og:title") == "Casa di Via Palestrina"

    def test_i_meta_finiscono_nell_index_della_spa(self, client, annuncio, monkeypatch):
        immobile, _ = annuncio
        monkeypatch.setattr(
            "properties.og._scarica_index",
            lambda: "<!DOCTYPE html><html><head><title>Viapal</title></head><body><div id=q></div></body></html>",
        )
        html = client.get(f"/g/{immobile.slug}").content.decode()

        assert '<div id=q></div>' in html
        assert html.count("<title>") == 1
        assert "<title>Casa di Via Palestrina</title>" in html

    def test_senza_index_resta_una_pagina_leggibile(self, client, annuncio):
        immobile, _ = annuncio
        html = client.get(f"/g/{immobile.slug}").content.decode()
        assert "<h1>Casa di Via Palestrina</h1>" in html


@pytest.mark.django_db
class TestImmagineOG:
    def test_jpeg_1200x630_dalla_hero(self, client, annuncio):
        immobile, _ = annuncio
        risposta = client.get(f"/api/v1/public/og-image/{immobile.slug}.jpg")

        assert risposta.status_code == 200
        assert risposta["Content-Type"] == "image/jpeg"
        img = Image.open(io.BytesIO(b"".join(risposta.streaming_content)))
        assert img.format == "JPEG"  # le foto sono WebP: WhatsApp non lo mostra
        assert img.size == (1200, 630)

    def test_la_camera_usa_la_propria_foto(self, client, annuncio):
        immobile, camera = annuncio
        risposta = client.get(
            f"/api/v1/public/og-image/{immobile.slug}.jpg?stanza={camera.pk}"
        )
        assert risposta.status_code == 200
        img = Image.open(io.BytesIO(b"".join(risposta.streaming_content)))
        assert img.size == (1200, 630)

    def test_immobile_senza_foto_non_ha_anteprima(self, client, db):
        nudo = Property.objects.create(nome="Senza foto", pubblica=True, slug="senza-foto")
        assert client.get(f"/api/v1/public/og-image/{nudo.slug}.jpg").status_code == 404
        html = client.get(f"/g/{nudo.slug}").content.decode()
        assert "og:image" not in html

    def test_non_pubblicato_niente_immagine(self, client, immobile):
        immobile.slug = "riservato"
        immobile.foto_hero = _foto("hero.webp")
        immobile.save()
        assert client.get("/api/v1/public/og-image/riservato.jpg").status_code == 404
