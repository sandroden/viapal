"""Anteprime social della galleria pubblica (Open Graph).

I crawler di WhatsApp, Facebook, Telegram & co. non eseguono JavaScript:
sull'HTML della SPA non trovano nulla e il link dell'annuncio viene
condiviso come URL nudo. Perciò ``/g/<slug>`` non è più servito da nginx
ma da Django, che prende l'``index.html`` del frontend (``SPA_INDEX_URL``)
e vi inietta i meta tag calcolati sull'immobile — o sulla singola stanza,
con ``?stanza=<id>``, che dà un link diverso (e un'anteprima diversa) per
ogni camera senza moltiplicare le pagine.

L'immagine dell'anteprima non può essere la foto così com'è: quelle
caricate dalla galleria sono WebP (ridimensionamento lato client) e
WhatsApp non le renderizza. ``og_image`` ne deriva un JPEG 1200x630,
formato e peso che i crawler mostrano come card grande.
"""

import hashlib
import logging
import os
import re
import urllib.request
from collections import namedtuple
from io import BytesIO

from django.conf import settings
from django.core.cache import cache
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import escape
from django.utils.text import slugify
from PIL import Image, ImageOps

from .models import Property, Room

logger = logging.getLogger("viapal.og")

# L'index della SPA cambia solo a ogni deploy: 60" tengono il traffico
# verso il container del frontend a zero senza far vivere a lungo un
# index vecchio (i cui asset, dopo il deploy, non esistono più).
CACHE_INDEX = "og:index-spa"
CACHE_INDEX_TTL = 60

# Misura piena della card (rapporto 1.91:1 di Facebook) e le riduzioni a cui
# si ripiega quando la foto non sta nel budget di peso: i proxy delle chat
# scaricano un'anteprima solo se è leggera, e una card mostrata a 500-600 px
# non perde nulla di visibile a 1000 px di larghezza.
OG_LARGHEZZA = 1200
OG_ALTEZZA = 630
OG_PESO_MAX = 150 * 1024
OG_VARIANTI = [(1200, 78), (1200, 70), (1000, 78), (1000, 70), (800, 75), (600, 75)]
# Cambiando i parametri di resa cambia anche l'impronta, altrimenti l'URL
# resterebbe lo stesso e i client servirebbero la versione vecchia.
OG_RESA = "2"


# ── Testi ────────────────────────────────────────────────────────────────


def _testo(prop, chiave, fallback=""):
    """Testo pubblico editabile, con lo stesso fallback del frontend."""
    valore = (prop.testi_pubblici or {}).get(chiave)
    return str(valore or "").strip() or fallback


def _facts(prop):
    """Riga di numeri della hero ("180 m² · 5 camere · 2 bagni")."""
    facts = (prop.testi_pubblici or {}).get("facts") or {}
    etichette = [
        ("mq_totali", "m²"),
        ("n_camere", "camere"),
        ("n_bagni", "bagni"),
        ("n_posti_letto", "posti letto"),
    ]
    pezzi = []
    for chiave, label in etichette:
        valore = facts.get(chiave)
        if valore in (None, "", 0):
            continue
        numero = str(valore)
        if "." in numero:
            numero = numero.rstrip("0").rstrip(".")
        pezzi.append(f"{numero} {label}")
    return " · ".join(pezzi)


def _titolo(prop, room):
    titolo_casa = _testo(prop, "hero_titolo", prop.nome)
    if room is None:
        return titolo_casa
    return f"{room.nome} — {titolo_casa}"


def _descrizione(prop, room):
    unita_intera = prop.tipo_gestione == Property.TipoGestione.UNITA_INTERA
    indirizzo = _testo(prop, "hero_indirizzo", prop.indirizzo or "")
    occhiello = _testo(
        prop,
        "hero_eyebrow",
        "Appartamento in affitto" if unita_intera else "Stanza in condivisione · disponibile",
    )
    if room is not None:
        pezzi = []
        if room.prezzo_mensile:
            pezzi.append(f"{room.prezzo_mensile:.0f} €/mese")
        if room.superficie_mq:
            pezzi.append(f"{room.superficie_mq:.0f} m²")
        if room.descrizione:
            pezzi.append(room.descrizione.strip())
        specifico = " · ".join(p for p in pezzi if p)
        # Una camera senza dati propri non merita una card muta: si ripiega
        # sulla descrizione della casa, che almeno dice dov'è.
        return _tronca(specifico or _descrizione(prop, None))
    # L'indirizzo spesso *è* il titolo dell'annuncio: ripeterlo nella
    # descrizione sprecherebbe l'unica riga che i social mostrano.
    titolo = _titolo(prop, None)
    if indirizzo and indirizzo.casefold() in titolo.casefold():
        indirizzo = ""
    return _tronca(" · ".join(p for p in (occhiello, indirizzo, _facts(prop)) if p))


def _tronca(testo, limite=200):
    testo = " ".join(testo.split())
    if len(testo) <= limite:
        return testo
    return testo[: limite - 1].rsplit(" ", 1)[0] + "…"


# ── Immagine ─────────────────────────────────────────────────────────────


def _sorgente(prop, room):
    """File immagine da cui derivare l'anteprima, dal più specifico in giù."""
    if room is not None:
        foto = room.gallery_images.order_by("ordinamento", "id").first()
        if foto and foto.image:
            return foto.image
    if prop.foto_hero:
        return prop.foto_hero
    for stanza in prop.rooms.filter(pubblica=True).order_by("ordinamento", "id"):
        foto = stanza.gallery_images.order_by("ordinamento", "id").first()
        if foto and foto.image:
            return foto.image
    for area in prop.gallery_areas.filter(pubblica=True).order_by("ordinamento", "id"):
        foto = area.gallery_images.order_by("ordinamento", "id").first()
        if foto and foto.image:
            return foto.image
    return None


def _impronta(filefield):
    """Impronta breve del file sorgente: cambia la foto, cambia l'URL.

    Facebook tiene in cache lo scrape per settimane: senza un URL nuovo
    l'anteprima resterebbe la vecchia foto.
    """
    pezzi = [filefield.name, OG_RESA]
    try:
        pezzi.append(str(filefield.size))
    except Exception:  # noqa: BLE001 - storage remoto muto: basta il nome
        logger.debug("Dimensione di %s non leggibile", filefield.name)
    return hashlib.sha1("|".join(pezzi).encode()).hexdigest()[:12]


def _deriva_jpeg(filefield):
    """JPEG in rapporto 1.91:1 dalla foto sorgente, entro il budget di peso.

    Si parte dalla misura piena e si scende solo quanto serve: una foto
    ordinaria resta a 1200x630, una difficile da comprimere (fogliame,
    tessiture fini) viene rimpicciolita finché non rientra. Ritorna i byte
    e le dimensioni effettive, che i meta devono dichiarare per davvero.
    """
    with filefield.open("rb") as fp:
        img = ImageOps.exif_transpose(Image.open(fp))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            fondo = Image.new("RGB", img.size, (255, 255, 255))
            fondo.paste(img, mask=img.split()[-1])
            img = fondo
        else:
            img = img.convert("RGB")

        ultimo = None
        for larghezza, qualita in OG_VARIANTI:
            misura = (larghezza, round(larghezza * OG_ALTEZZA / OG_LARGHEZZA))
            buffer = BytesIO()
            ImageOps.fit(img, misura, method=Image.LANCZOS).save(
                buffer, "JPEG", quality=qualita, optimize=True, progressive=True
            )
            ultimo = (buffer.getvalue(), misura)
            if len(ultimo[0]) <= OG_PESO_MAX:
                return ultimo
    # Nessuna variante rientra: si tiene la più piccola, meglio di niente.
    return ultimo


def _percorso_cache(slug, impronta):
    cartella = os.path.join(settings.MEDIA_ROOT, "og")
    os.makedirs(cartella, exist_ok=True)
    return os.path.join(cartella, f"{slug}-{impronta}.jpg")


Anteprima = namedtuple("Anteprima", "percorso larghezza altezza impronta")


def _anteprima(prop, room):
    """Anteprima pronta su disco, generandola alla prima richiesta.

    La misura effettiva torna al chiamante perché i meta devono dichiarare
    quella vera: se `og:image:width` non corrisponde al file, Facebook
    scarta l'immagine. ``None`` se non c'è una foto o non è elaborabile —
    i meta semplicemente non parleranno di immagini.
    """
    filefield = _sorgente(prop, room)
    if filefield is None:
        return None
    impronta = _impronta(filefield)
    percorso = _percorso_cache(prop.slug, impronta)
    if os.path.exists(percorso):
        try:
            with Image.open(percorso) as img:
                return Anteprima(percorso, *img.size, impronta)
        except Exception:  # noqa: BLE001 - cache illeggibile: si rifà
            logger.warning("Anteprima OG in cache illeggibile: %s", percorso)
            os.remove(percorso)
    try:
        dati, (larghezza, altezza) = _deriva_jpeg(filefield)
    except Exception:
        logger.exception("Anteprima OG non derivabile da %s", filefield.name)
        return None
    temporaneo = f"{percorso}.{os.getpid()}"
    with open(temporaneo, "wb") as fp:
        fp.write(dati)
    os.replace(temporaneo, percorso)
    return Anteprima(percorso, larghezza, altezza, impronta)


def _url_immagine(request, prop, room, anteprima):
    if anteprima is None:
        return None
    url = reverse("public-og-image", kwargs={"slug": prop.slug})
    query = f"?v={anteprima.impronta}"
    if room is not None:
        query += f"&stanza={room.pk}"
    return request.build_absolute_uri(url + query)


def og_image(request, slug):
    """L'anteprima in JPEG, derivata dalla foto e messa in cache su disco."""
    prop = get_object_or_404(Property.objects.filter(pubblica=True), slug=slug)
    anteprima = _anteprima(prop, _stanza_richiesta(prop, request))
    if anteprima is None:
        raise Http404("Nessuna foto da cui derivare l'anteprima.")

    # FileResponse chiude lui il file quando ha finito di servirlo.
    risposta = FileResponse(open(anteprima.percorso, "rb"), content_type="image/jpeg")  # noqa: SIM115
    # L'URL contiene l'impronta del sorgente: il contenuto non cambia mai.
    risposta["Cache-Control"] = "public, max-age=31536000, immutable"
    return risposta


# ── Pagina ───────────────────────────────────────────────────────────────


def _stanza_richiesta(prop, request):
    """Stanza indicata da ``?stanza=…``: id numerico o nome in forma di slug.

    Il nome (`?stanza=camera-3`) è la forma da condividere, leggibile da chi
    riceve il link; l'id resta valido perché i link già mandati in giro non
    smettano di funzionare.
    """
    grezzo = (request.GET.get("stanza") or "").strip()
    if not grezzo:
        return None
    stanze = Room.objects.filter(property=prop, pubblica=True).order_by("ordinamento", "id")
    if grezzo.isdigit():
        per_id = stanze.filter(pk=int(grezzo)).first()
        if per_id is not None:
            return per_id
    voluto = slugify(grezzo)
    if not voluto:
        return None
    return next((s for s in stanze if slugify(s.nome) == voluto), None)


def _meta(request, prop, room):
    titolo = _titolo(prop, room)
    descrizione = _descrizione(prop, room)
    url_pagina = request.build_absolute_uri()
    anteprima = _anteprima(prop, room)
    url_immagine = _url_immagine(request, prop, room, anteprima)

    tag = [
        f"<title>{escape(titolo)}</title>",
        f'<meta name="description" content="{escape(descrizione)}">',
        f'<link rel="canonical" href="{escape(url_pagina)}">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="Viapal">',
        '<meta property="og:locale" content="it_IT">',
        f'<meta property="og:title" content="{escape(titolo)}">',
        f'<meta property="og:description" content="{escape(descrizione)}">',
        f'<meta property="og:url" content="{escape(url_pagina)}">',
    ]
    if url_immagine:
        tag += [
            f'<meta property="og:image" content="{escape(url_immagine)}">',
            f'<meta property="og:image:secure_url" content="{escape(url_immagine)}">',
            '<meta property="og:image:type" content="image/jpeg">',
            f'<meta property="og:image:width" content="{anteprima.larghezza}">',
            f'<meta property="og:image:height" content="{anteprima.altezza}">',
            f'<meta property="og:image:alt" content="{escape(titolo)}">',
            '<meta name="twitter:card" content="summary_large_image">',
        ]
    else:
        tag.append('<meta name="twitter:card" content="summary">')
    return titolo, descrizione, url_immagine, "\n    ".join(tag)


def _scarica_index():
    """``index.html`` del frontend, dal container Quasar (o dal dev server)."""
    url = getattr(settings, "SPA_INDEX_URL", "")
    if not url:
        return None
    html = cache.get(CACHE_INDEX)
    if html is None:
        try:
            with urllib.request.urlopen(url, timeout=3) as risposta:
                html = risposta.read().decode("utf-8", "replace")
        except Exception:
            logger.warning("index.html della SPA non raggiungibile su %s", url, exc_info=True)
            return None
        cache.set(CACHE_INDEX, html, CACHE_INDEX_TTL)
    return html


def _inietta(html, tag):
    """Sostituisce il ``<title>`` e infila i meta prima di ``</head>``."""
    if "</head>" not in html:
        return None
    html = re.sub(r"<title>.*?</title>\s*", "", html, count=1, flags=re.IGNORECASE | re.DOTALL)
    return html.replace("</head>", f"    {tag}\n  </head>", 1)


def _pagina_minima(titolo, descrizione, url_immagine, tag):
    """Ripiego se il frontend non risponde: i crawler leggono comunque i meta."""
    immagine = f'<img src="{escape(url_immagine)}" alt="">' if url_immagine else ""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="it">\n  <head>\n    <meta charset="utf-8">\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"    {tag}\n  </head>\n"
        f"  <body>\n    <h1>{escape(titolo)}</h1>\n"
        f"    <p>{escape(descrizione)}</p>\n    {immagine}\n  </body>\n</html>\n"
    )


def galleria_og(request, slug):
    """``/g/<slug>``: l'HTML della SPA con i meta tag dell'annuncio."""
    prop = (
        Property.objects.filter(pubblica=True, slug=slug)
        .prefetch_related("rooms", "rooms__gallery_images", "gallery_areas__gallery_images")
        .first()
    )
    if prop is None:
        # Slug sbagliato o annuncio ritirato: 404 per i crawler, ma la SPA
        # va servita lo stesso, così il visitatore legge il suo "Galleria
        # non disponibile" invece della pagina d'errore di Django.
        index = _scarica_index()
        if index:
            return HttpResponse(index, content_type="text/html; charset=utf-8", status=404)
        raise Http404("Galleria non pubblicata.")
    room = _stanza_richiesta(prop, request)
    titolo, descrizione, url_immagine, tag = _meta(request, prop, room)

    index = _scarica_index()
    html = _inietta(index, tag) if index else None
    if html is None:
        html = _pagina_minima(titolo, descrizione, url_immagine, tag)
    risposta = HttpResponse(html, content_type="text/html; charset=utf-8")
    risposta["Cache-Control"] = "public, max-age=300"
    return risposta
