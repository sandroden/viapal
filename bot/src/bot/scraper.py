"""Raccolta dei post dal gruppo, scorrendo il feed.

Il feed di Facebook è virtualizzato: i post lontani dal viewport vengono
svuotati. Quindi non si scrolla fino in fondo per poi estrarre — si estrae a
ogni passo e si accumula. Prima di ogni estrazione il mouse passa sugli orari
mascherati e Facebook riempie l'href col permalink (vedi estrazione.py,
trappola 4); i post sfuggiti li recupera il ripasso in risalita.
"""
from __future__ import annotations

import hashlib
import logging
import random
import re
import time
from dataclasses import dataclass, field

from .browser import Browser
from .estrazione import DIAGNOSI_JS, ORARI_MASCHERATI_JS, RACCOLTA_POST_JS
from .pulizia import e_troncato, pulisci

log = logging.getLogger(__name__)

URL_GRUPPO = "https://www.facebook.com/groups/{group_id}?sorting_setting=CHRONOLOGICAL"

# La finestra in cui lo sweep può portare il mouse è [100px, viewport−15] —
# ~518px su un viewport headless di 633. In discesa si tiene un passo comodo e
# le fasce che restano cieche le copre il ripasso, che risale a passi PIÙ CORTI
# della finestra: così ogni riga del nastro ci passa dentro almeno una volta.
PASSO_SCROLL = 600
PASSO_RIPASSO = 400


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
    """Identità del post DENTRO un giro, stabile fra un passo e l'altro.

    L'id vero arriva solo quando il mouse è passato sull'orario, cioè spesso a
    un passo successivo alla prima raccolta: se la chiave fosse l'id, lo stesso
    post entrerebbe due volte (prima senza, poi con). Il testo viene
    normalizzato perché il conteggio dei commenti e delle reazioni cambia da
    un'ora all'altra sullo stesso identico post.
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

    `gia_visti` sono i post_id già in database (id veri o impronte): servono a
    fermare lo scroll, non a filtrare (la deduplica vera la fa il database).
    """
    browser.apri(URL_GRUPPO.format(group_id=group_id))
    _attendi_post(browser)

    raccolti: dict[str, Post] = {}
    visti_di_fila = 0
    discese = 0

    for giro in range(max_scroll):
        _smaschera_orari(browser)
        visti_di_fila = _integra(
            browser.valuta(RACCOLTA_POST_JS) or [], raccolti, gia_visti, visti_di_fila
        )
        if visti_di_fila >= stop_dopo_visti:
            log.info("giro %d: %d post già visti di fila, mi fermo", giro, visti_di_fila)
            break

        browser.scorri(PASSO_SCROLL)
        discese += 1
        time.sleep(random.uniform(1.1, 2.0))  # ritmo irregolare, non da script

    _ripasso(browser, raccolti, gia_visti, discese)

    if not raccolti and not gia_visti:
        raise MarkupCambiato("nessun post estratto al primo giro")

    senza = sum(1 for p in raccolti.values() if p.permalink_e_del_profilo)
    log.info("raccolti %d post nuovi (%d senza permalink)", len(raccolti), senza)
    return list(raccolti.values())


def _smaschera_orari(browser: Browser) -> None:
    """Passa il mouse sugli orari mascherati visibili: l'href si riempie.

    L'evento deve essere trusted, quindi mouse CDP vero (vedi estrazione.py).
    Lo smascheramento persiste sul nodo, ma i nodi ricreati dalla
    virtualizzazione tornano mascherati: si ripassa a ogni passo.

    Si ripete finché la lista dei bersagli non si svuota (max 3 giri), per due
    ragioni misurate sul campo: i post si idratano ANCHE DOPO il primo sweep
    del passo, e tra la lettura delle coordinate e il mouse il layout può
    essersi spostato (immagini che caricano sopra) facendo mancare il colpo.
    Rileggere a ogni giro dà coordinate fresche e bersagli nuovi.
    """
    for _ in range(3):
        bersagli = browser.valuta(ORARI_MASCHERATI_JS) or []
        if not bersagli:
            return
        for bersaglio in bersagli:
            browser.muovi_mouse(bersaglio["x"], bersaglio["y"])
            time.sleep(random.uniform(0.08, 0.2))


def _integra(
    grezzi: list[dict],
    raccolti: dict[str, Post],
    gia_visti: set[str],
    visti_di_fila: int,
) -> int:
    """Fonde una lettura del feed dentro `raccolti`; ritorna il contatore visti.

    La chiave è sempre l'impronta: così il post raccolto prima dello sweep e
    quello con l'id vero del passo dopo restano UNO, e l'id arrivato tardi
    aggiorna il record invece di duplicarlo.
    """
    for grezzo in grezzi:
        if grezzo.get("marketplace"):
            continue        # annuncio Marketplace: è sempre un'offerta
        testo = pulisci(grezzo["raw"])
        if len(testo) < 40:
            continue
        chiave = _impronta(grezzo["author_url"], testo)
        reale = grezzo["post_id"]
        if chiave in gia_visti or (reale and reale in gia_visti):
            # Se l'id vero rivela solo ORA che il post è in database (raccolto
            # id-less a un passo prima), va tolto: rinotificarlo è il peggio.
            raccolti.pop(chiave, None)
            visti_di_fila += 1
            continue
        post = raccolti.get(chiave)
        if post is None:
            visti_di_fila = 0
            # Senza permalink si ripiega sul profilo dell'autore: per scrivere
            # in privato è anche più utile del post.
            raccolti[chiave] = Post(
                post_id=reale or chiave,
                permalink=grezzo["permalink"] or grezzo["author_url"] or "",
                author_name=grezzo["author_name"],
                author_url=grezzo["author_url"],
                text=testo,
                author_id=grezzo.get("author_id"),
                troncato=e_troncato(testo),
                permalink_e_del_profilo=not grezzo["permalink"],
            )
            continue
        visti_di_fila = 0
        if grezzo["permalink"] and post.permalink_e_del_profilo:
            post.post_id = reale or post.post_id
            post.permalink = grezzo["permalink"]
            post.permalink_e_del_profilo = False
        if len(testo) > len(post.text):
            post.text, post.troncato = testo, e_troncato(testo)
    return visti_di_fila


def _ripasso(
    browser: Browser, raccolti: dict[str, Post], gia_visti: set[str], passi: int
) -> None:
    """Risale il feed smascherando gli orari sfuggiti alla discesa.

    Alla fine della discesa restano mascherati i post che il mouse non ha mai
    potuto raggiungere: quelli raccolti dal render OLTRE il fondo del viewport,
    quelli idratati in ritardo quando l'orario era già passato sopra, e quelli
    caduti nelle fasce cieche del passo di discesa (600px di passo contro
    ~518px di finestra utile). Nella prova sul campo la sola discesa si è
    fermata a 7 permalink su 10 — e proprio su questi tre casi. Si ferma
    appena non manca più niente, quindi a regime costa quasi zero.
    """
    def _mancano() -> bool:
        return any(p.permalink_e_del_profilo for p in raccolti.values())

    def _passo(pixel: int) -> None:
        browser.scorri(pixel)
        # i nodi ricreati dalla virtualizzazione vanno lasciati idratare:
        # senza respiro lo sweep arriva prima del render e non trova niente
        time.sleep(random.uniform(1.4, 2.0))
        _smaschera_orari(browser)
        _integra(browser.valuta(RACCOLTA_POST_JS) or [], raccolti, gia_visti, 0)

    # Coda: il DOM renderizza un paio di schermate OLTRE il fondo del viewport,
    # e quei post sono già raccolti ma il loro orario non è mai stato a tiro di
    # mouse. Prima di risalire, qualche passo in giù per coprirli.
    for _ in range(3):
        if not _mancano():
            return
        _passo(PASSO_SCROLL)

    # Risalita fitta, fino in cima o finché non manca più niente.
    percorso = (passi + 3) * PASSO_SCROLL
    for _ in range(percorso // PASSO_RIPASSO + 2):
        if not _mancano():
            return
        _passo(-PASSO_RIPASSO)


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
