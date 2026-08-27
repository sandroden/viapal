"""Raccolta dei post dal gruppo, scorrendo il feed.

Il feed di Facebook è virtualizzato: i post lontani dal viewport vengono
svuotati. Quindi non si scrolla fino in fondo per poi estrarre — si estrae a
ogni passo e si accumula. Vedi estrazione.py per il dettaglio.
"""
from __future__ import annotations

import hashlib
import logging
import random
import re
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
    author_id: str | None = field(default=None)
    troncato: bool = field(default=False)
    permalink_e_del_profilo: bool = field(default=False)

    @property
    def link_messenger(self) -> str | None:
        """Apre la conversazione con questa persona.

        È il link giusto per il flusso: il messaggio privato va incollato lì.
        Il profilo dentro il gruppo (/groups/<gid>/user/<uid>/) invece l'app
        mobile non lo gestisce e ricade sul gruppo — era il motivo per cui
        certi link "apri il post" finivano sulla pagina sbagliata.
        """
        return f"https://m.me/{self.author_id}" if self.author_id else None


def _impronta(author_url: str | None, testo: str) -> str:
    """Identità del post quando Facebook non espone il permalink.

    Serve solo a non riproporre lo stesso post due volte nella stessa campagna,
    quindi non deve essere l'id vero: basta che sia stabile fra un giro e
    l'altro. Il testo viene normalizzato perché il conteggio dei commenti e
    delle reazioni cambia da un'ora all'altra sullo stesso identico post.
    """
    testo_stabile = re.sub(r"\d+", "", testo)[:400].casefold()
    seme = f"{author_url or ''}|{' '.join(testo_stabile.split())}"
    return "h" + hashlib.sha1(seme.encode()).hexdigest()[:16]


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
    _attendi_post(browser)

    raccolti: dict[str, Post] = {}
    visti_di_fila = 0

    for giro in range(max_scroll):
        for grezzo in browser.valuta(RACCOLTA_POST_JS) or []:
            if grezzo.get("marketplace"):
                continue        # annuncio Marketplace: è sempre un'offerta
            testo = pulisci(grezzo["raw"])
            if len(testo) < 40:
                continue
            # Il permalink spesso non c'è (vedi estrazione.py, trappola 4):
            # in quel caso l'identità la fa un'impronta di autore + testo.
            post_id = grezzo["post_id"] or _impronta(grezzo["author_url"], testo)
            if post_id in gia_visti:
                visti_di_fila += 1
                continue
            precedente = raccolti.get(post_id)
            if precedente:
                # Il permalink può comparire dopo, quando lo scroll fa idratare
                # il post: se nel frattempo c'è, si prende, anche a testo
                # invariato. Costa nulla, ma non aspettarsi molto.
                #
                # Il 27/08 ho provato a farlo salire sopra il ~40%, senza
                # riuscirci. Per non rifare il giro alla prossima campagna:
                #   lettura singola, scroll 1200 ....... 40%  (16/40)
                #   due letture per passo .............. 40%  (16/40)
                #   pausa 2,5s fra le due letture ...... 40%  (16/40)
                #   scroll 500px (sotto il viewport) ... 37%  (13/35)
                #   pausa 7s dopo ogni scroll .......... 37%  (10/27)
                # Non dipende dal ritmo con cui si legge: Facebook lo espone su
                # una frazione dei post e basta. L'author_id invece c'è sempre,
                # ed è per questo che il flusso poggia su Messenger.
                if grezzo["permalink"] and precedente.permalink_e_del_profilo:
                    precedente.permalink = grezzo["permalink"]
                    precedente.permalink_e_del_profilo = False
                if len(precedente.text) >= len(testo):
                    continue
            visti_di_fila = 0
            # Senza permalink si ripiega sul profilo dell'autore: per scrivere
            # in privato è anche più utile del post.
            permalink = grezzo["permalink"] or grezzo["author_url"] or ""
            raccolti[post_id] = Post(
                post_id=post_id,
                permalink=permalink,
                author_name=grezzo["author_name"],
                author_url=grezzo["author_url"],
                text=testo,
                author_id=grezzo.get("author_id"),
                troncato=e_troncato(testo),
                permalink_e_del_profilo=not grezzo["permalink"],
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


def _attendi_post(browser: Browser, tentativi: int = 12) -> None:
    """Aspetta che il feed contenga post veri, non solo i contenitori vuoti.

    Un `sleep` fisso non basta: quanto ci mette Facebook a popolare il feed
    varia parecchio, e partire troppo presto significa raccogliere un post o
    due e credere che il gruppo sia fermo. Uno scroll ogni tanto aiuta, perché
    è il segnale che innesca il caricamento.
    """
    import json

    for tentativo in range(tentativi):
        time.sleep(2)
        diagnosi = json.loads(browser.valuta(DIAGNOSI_JS))
        if diagnosi.get("con_testo"):
            log.info("feed pronto dopo %.0fs: %s", (tentativo + 1) * 2, diagnosi)
            return
        if not diagnosi.get("feed"):
            raise MarkupCambiato(
                f"div[role=\"feed\"] non trovato su {diagnosi.get('url')} — "
                "markup cambiato, oppure Facebook ha chiesto un checkpoint"
            )
        if tentativo % 3 == 2:
            browser.scorri(600)

    raise MarkupCambiato(
        f"il feed è rimasto vuoto dopo {tentativi * 2}s: {diagnosi} — "
        "controlla in headed se Facebook sta chiedendo una verifica"
    )
