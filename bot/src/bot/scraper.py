"""Raccolta dei post dal gruppo, scorrendo il feed.

Il feed di Facebook è virtualizzato: i post lontani dal viewport vengono
svuotati. Quindi non si scrolla fino in fondo per poi estrarre — si estrae a
ogni passo e si accumula. Vedi estrazione.py per il dettaglio.
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field

from .browser import Browser
from .estrazione import DIAGNOSI_JS, RACCOLTA_POST_JS
from .pulizia import e_troncato, pulisci

log = logging.getLogger(__name__)

URL_GRUPPO = "https://www.facebook.com/groups/{group_id}?sorting_setting=CHRONOLOGICAL"


class MarkupCambiato(RuntimeError):
    """Nessun post trovato: quasi certamente il markup di Facebook è cambiato.

    Non si fallisce in silenzio — chi chiama deve avvisare su Telegram.
    """


@dataclass
class Post:
    post_id: str
    permalink: str
    author_name: str | None
    author_url: str | None
    text: str
    troncato: bool = field(default=False)


def raccogli(
    browser: Browser,
    group_id: str,
    gia_visti: set[str],
    stop_dopo_visti: int = 10,
    max_scroll: int = 25,
) -> list[Post]:
    """Scorre il feed finché non incontra `stop_dopo_visti` post già noti.

    `gia_visti` sono i post_id già in database: servono a fermare lo scroll,
    non a filtrare (la deduplica vera la fa il database).
    """
    browser.apri(URL_GRUPPO.format(group_id=group_id))
    time.sleep(5)  # il primo rendering del feed non è immediato

    _verifica_feed(browser)

    raccolti: dict[str, Post] = {}
    visti_di_fila = 0

    for giro in range(max_scroll):
        for grezzo in browser.valuta(RACCOLTA_POST_JS) or []:
            post_id = grezzo["post_id"]
            testo = pulisci(grezzo["raw"])
            if len(testo) < 40:
                continue
            if post_id in gia_visti:
                visti_di_fila += 1
                continue
            precedente = raccolti.get(post_id)
            # scrollando, un post può ricomparire più espanso: si tiene il più lungo
            if precedente and len(precedente.text) >= len(testo):
                continue
            visti_di_fila = 0
            raccolti[post_id] = Post(
                post_id=post_id,
                permalink=grezzo["permalink"],
                author_name=grezzo["author_name"],
                author_url=grezzo["author_url"],
                text=testo,
                troncato=e_troncato(testo),
            )

        if visti_di_fila >= stop_dopo_visti:
            log.info("giro %d: %d post già visti di fila, mi fermo", giro, visti_di_fila)
            break

        browser.scorri(1200)
        time.sleep(random.uniform(1.1, 2.0))  # ritmo irregolare, non da script

    if not raccolti and not gia_visti:
        raise MarkupCambiato("nessun post estratto al primo giro")

    log.info("raccolti %d post nuovi", len(raccolti))
    return list(raccolti.values())


def _verifica_feed(browser: Browser) -> None:
    import json

    diagnosi = json.loads(browser.valuta(DIAGNOSI_JS))
    log.info("feed: %s", diagnosi)
    if not diagnosi.get("feed"):
        raise MarkupCambiato(
            f"div[role=\"feed\"] non trovato su {diagnosi.get('url')} — "
            "markup cambiato, oppure Facebook ha chiesto un checkpoint di sicurezza"
        )
