"""Pagina pubblica ``/scopri``: il video di presentazione di Viapal.

Come per la galleria (``properties/og.py``), la pagina è della SPA ma passa
da Django: il link si manda ai proprietari che potrebbero provare Viapal, e
senza meta Open Graph server-side WhatsApp e Facebook lo mostrerebbero come
URL nudo. Qui i meta sono fissi: il video e le sue immagini stanno in
``MEDIA_ROOT/scopri/``, caricati a mano (non sono nel repository).
"""

from django.conf import settings
from django.http import HttpResponse
from django.utils.html import escape
from properties.og import _inietta, _pagina_minima, _scarica_index

TITOLO = "Viapal — il gestionale per chi affitta camere"
DESCRIZIONE = (
    "Affitti a stanze, senza fogli Excel. In tre minuti: incassi e ritardi, "
    "bollette divise per presenza, conti fra comproprietari e l'app dell'inquilino."
)
CARTELLA = "scopri"
# Misure reali dei file: Facebook scarta l'immagine se i meta non tornano.
ANTEPRIMA = ("anteprima.jpg", 1200, 630)
VIDEO = ("viapal-demo.mp4", 1280, 720)


def _media(request, nome):
    return request.build_absolute_uri(f"{settings.MEDIA_URL}{CARTELLA}/{nome}")


def _meta(request):
    url_pagina = request.build_absolute_uri(request.path)
    immagine, larghezza, altezza = ANTEPRIMA
    url_immagine = _media(request, immagine)
    video, v_larghezza, v_altezza = VIDEO
    url_video = _media(request, video)
    tag = [
        f"<title>{escape(TITOLO)}</title>",
        f'<meta name="description" content="{escape(DESCRIZIONE)}">',
        f'<link rel="canonical" href="{escape(url_pagina)}">',
        '<meta property="og:type" content="video.other">',
        '<meta property="og:site_name" content="Viapal">',
        '<meta property="og:locale" content="it_IT">',
        f'<meta property="og:title" content="{escape(TITOLO)}">',
        f'<meta property="og:description" content="{escape(DESCRIZIONE)}">',
        f'<meta property="og:url" content="{escape(url_pagina)}">',
        f'<meta property="og:image" content="{escape(url_immagine)}">',
        f'<meta property="og:image:secure_url" content="{escape(url_immagine)}">',
        '<meta property="og:image:type" content="image/jpeg">',
        f'<meta property="og:image:width" content="{larghezza}">',
        f'<meta property="og:image:height" content="{altezza}">',
        f'<meta property="og:image:alt" content="{escape(TITOLO)}">',
        f'<meta property="og:video" content="{escape(url_video)}">',
        f'<meta property="og:video:secure_url" content="{escape(url_video)}">',
        '<meta property="og:video:type" content="video/mp4">',
        f'<meta property="og:video:width" content="{v_larghezza}">',
        f'<meta property="og:video:height" content="{v_altezza}">',
        '<meta name="twitter:card" content="summary_large_image">',
    ]
    return url_immagine, "\n    ".join(tag)


def scopri_og(request):
    """``/scopri``: l'HTML della SPA con i meta tag del video."""
    url_immagine, tag = _meta(request)
    index = _scarica_index()
    html = _inietta(index, tag) if index else None
    if html is None:
        html = _pagina_minima(TITOLO, DESCRIZIONE, url_immagine, tag)
    risposta = HttpResponse(html, content_type="text/html; charset=utf-8")
    risposta["Cache-Control"] = "public, max-age=300"
    return risposta
