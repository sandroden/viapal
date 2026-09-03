"""Raccolta dei post dal gruppo, scorrendo il feed.

Il feed di Facebook è virtualizzato: i post lontani dal viewport vengono
svuotati. Quindi non si scrolla fino in fondo per poi estrarre — si estrae a
ogni passo e si accumula. Prima di ogni estrazione il mouse passa sugli orari
dei post nel viewport: Facebook riempie l'href col permalink e mostra il
tooltip con la data (vedi estrazione.py, trappole 4 e 5); i post sfuggiti li
recupera il ripasso in risalita.

Quando smettere di scorrere lo decide l'ORA dei post, non il conteggio dei
"già visti": il feed è cronologico, quindi appena compaiono un paio di post
non più recenti dell'ultimo letto al giro prima, sotto non c'è più niente di
nuovo. Il conteggio dei già visti resta come rete di sicurezza, perché era
inaffidabile: l'archivio conosce i post per id numerico, e l'id compare solo
dopo l'hover — i post oltre il viewport sembravano tutti nuovi, azzeravano il
contatore a ogni passo e la discesa andava avanti per 20-90 passi con 3 post
nuovi in cima (misurato il 02/09: 3 minuti a gruppo).
"""
from __future__ import annotations

import hashlib
import logging
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .browser import Browser
from .estrazione import BERSAGLI_ORARIO_JS, DIAGNOSI_JS, RACCOLTA_POST_JS, stampa_ora_js
from .pulizia import e_troncato, pulisci

log = logging.getLogger(__name__)

URL_GRUPPO = "https://www.facebook.com/groups/{group_id}?sorting_setting=CHRONOLOGICAL"

# La finestra in cui lo sweep può portare il mouse è [100px, viewport−15] —
# ~518px su un viewport headless di 633. In discesa si tiene un passo comodo e
# le fasce che restano cieche le copre il ripasso, che risale a passi PIÙ CORTI
# della finestra: così ogni riga del nastro ci passa dentro almeno una volta.
PASSO_SCROLL = 600
PASSO_RIPASSO = 400
# Tetto alla risalita del ripasso. Basta UN post rimasto senza permalink
# perché la risalita rifaccia tutto il nastro: nel passaggio profondo (70
# passi di discesa) sono 113 passi e 5 minuti, misurati il 03/09, per un
# post che verrà notificato comunque col link del profilo. Ventiquattro
# passi sono ~9600px, cioè le ultime 16 schermate di discesa: un giro
# normale ci sta dentro per intero.
PASSI_MAX_RIPASSO = 24

# Quanti post di fila non più recenti dell'ultima lettura bastano per fermarsi.
# Uno solo potrebbe essere un post tenuto in evidenza in cima; due di fila in
# un feed cronologico vogliono dire che la parte nuova è finita.
VECCHI_DI_FILA = 2
# Almeno un passo di scroll prima di fidarsi della regola sull'ora: la prima
# schermata può aprirsi con post fissati in cima, e un passo costa tre secondi.
PASSI_MINIMI = 1
# Il tooltip con la data compare ~200 ms dopo l'hover (misurato il 02/09 su
# orari mascherati e no): si aspetta un po' di più e si legge.
ATTESA_TOOLTIP = (0.3, 0.45)

MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
# "Mercoledì 2 settembre 2026 alle ore 16:23" — il giorno della settimana non serve.
RE_ORA = re.compile(r"(\d{1,2})\s+([a-zà]+)\s+(\d{4})\s+alle(?:\s+ore)?\s+(\d{1,2}):(\d{2})", re.I)
# Non l'ho mai vista nel tooltip, ma costa una riga e la forma è quella di Facebook.
RE_RELATIVA = re.compile(r"\b(oggi|ieri)\s+alle(?:\s+ore)?\s+(\d{1,2}):(\d{2})", re.I)


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
    # Il gruppo in cui il post è stato trovato lo sa lo scraper — è quello che
    # sta scorrendo — e non si ricava dal permalink, che spesso manca. Serve a
    # viapal, e servirà quando i gruppi monitorati saranno più d'uno.
    group_id: str = field(default="")
    # Data e ora di pubblicazione lette dal tooltip, ISO al minuto. Manca per i
    # post su cui il mouse non è mai riuscito a passare.
    ora: str | None = field(default=None)

    @property
    def link_messenger(self) -> str | None:
        """Apre la conversazione con questa persona.

        È il link giusto per il flusso: il messaggio privato va incollato lì.
        Il profilo dentro il gruppo (/groups/<gid>/user/<uid>/) invece l'app
        mobile non lo gestisce e ricade sul gruppo — era il motivo per cui
        certi link "apri il post" finivano sulla pagina sbagliata.
        """
        return f"https://m.me/{self.author_id}" if self.author_id else None


@dataclass
class Lettura:
    """Cosa ha dato la scorsa di un gruppo: i post nuovi e fin dove si è letto.

    `ultima_ora` è l'ora del post più recente incontrato, nuovo o già noto: è
    il segnalibro da cui il giro dopo saprà fermarsi. `letti` conta i post
    trovati nel feed, nuovi o no: zero vuol dire gruppo muto, non tranquillo.
    """
    post: list[Post]
    ultima_ora: datetime | None = None
    letti: int = 0


def parse_ora(testo: str | None, adesso: datetime | None = None) -> datetime | None:
    """Data e ora dal testo del tooltip, in ora locale (quella dell'account).

    Torna None su qualunque cosa non capisca: meglio un post senza ora, che
    non decide niente, di un'ora sbagliata che ferma lo scroll troppo presto.
    """
    if not testo:
        return None
    pulito = " ".join(testo.replace("͏", "").split())
    trovato = RE_ORA.search(pulito)
    if trovato:
        giorno, mese, anno, ore, minuti = trovato.groups()
        numero_mese = MESI.get(mese.lower())
        if numero_mese is None:
            return None
        try:
            return datetime(int(anno), numero_mese, int(giorno), int(ore), int(minuti))
        except ValueError:
            return None
    trovato = RE_RELATIVA.search(pulito)
    if trovato:
        base = (adesso or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
        if trovato.group(1).lower() == "ieri":
            base -= timedelta(days=1)
        try:
            return base.replace(hour=int(trovato.group(2)), minute=int(trovato.group(3)))
        except ValueError:
            return None
    return None


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
    ultima_ora: datetime | None = None,
    orizzonte: datetime | None = None,
) -> Lettura:
    """Scorre il feed finché non arriva ai post letti al giro prima.

    `ultima_ora` è l'ora del post più recente letto l'ultima volta in questo
    gruppo: incontrati `VECCHI_DI_FILA` post non più recenti, ci si ferma.
    `orizzonte` è la data prima della quale un post non interessa più: fa da
    limite al primo giro su un gruppo nuovo (senza, si leggerebbero 90 passi
    di feed) e da rete quando il bot è stato spento per giorni. I post più
    vecchi dell'orizzonte si trattano come già visti.

    `gia_visti` sono i post_id già in database (id veri o impronte): servono a
    non riproporre i post, e a fermare lo scroll se l'ora non fosse leggibile.
    """
    browser.apri(URL_GRUPPO.format(group_id=group_id))
    _attendi_post(browser)

    limite = max((t for t in (ultima_ora, orizzonte) if t is not None), default=None)
    # Copia: dentro il giro cresce con le impronte dei post scoperti noti (id
    # in archivio, o troppo vecchi). Serve perché lo stesso post può tornare
    # id-less a un passo dopo — Facebook rimaschera l'href reidratando il
    # nodo — e senza memoria rientrerebbe come nuovo.
    noti = set(gia_visti)
    raccolti: dict[str, Post] = {}
    visti_di_fila = 0
    discese = 0
    letti = 0
    ora_max: datetime | None = None

    for giro in range(max_scroll):
        _sweep_orari(browser)
        grezzi = browser.valuta(RACCOLTA_POST_JS) or []
        letti += len(grezzi)
        visti_di_fila = _integra(grezzi, raccolti, noti, visti_di_fila, orizzonte)
        ora_max = _piu_recente(ora_max, _ora_massima(grezzi))
        if log.isEnabledFor(logging.DEBUG):
            ore = [parse_ora(g.get("ora")) for g in grezzi]
            con_ora = [o for o in ore if o is not None]
            log.debug(
                "giro %d: %d nel DOM, %d con ora (%s → %s), sequenza %s, raccolti %d, visti di fila %d",
                giro, len(grezzi), len(con_ora),
                _iso(min(con_ora)) if con_ora else "-", _iso(max(con_ora)) if con_ora else "-",
                " ".join(o.strftime("%d/%H:%M") if o else "?" for o in ore),
                len(raccolti), visti_di_fila,
            )
        if visti_di_fila >= stop_dopo_visti:
            log.info("giro %d: %d post già visti di fila, mi fermo", giro, visti_di_fila)
            break
        if limite is not None and discese >= PASSI_MINIMI:
            fermo = _indice_stop(grezzi, limite)
            if fermo is not None:
                log.info("giro %d: %d post di fila non più recenti di %s, mi fermo",
                         giro, VECCHI_DI_FILA, limite.isoformat(timespec="minutes"))
                _scarta_oltre(grezzi[fermo + 1:], raccolti, noti)
                _scarta_senza_ora(raccolti)
                break

        browser.scorri(PASSO_SCROLL)
        discese += 1
        time.sleep(random.uniform(1.1, 2.0))  # ritmo irregolare, non da script

    _ripasso(browser, raccolti, noti, discese, orizzonte)

    if not letti and not gia_visti:
        raise MarkupCambiato("nessun post estratto al primo giro")

    for p in raccolti.values():
        p.group_id = group_id
    senza = sum(1 for p in raccolti.values() if p.permalink_e_del_profilo)
    log.info("raccolti %d post nuovi (%d senza permalink), letto fino a %s",
             len(raccolti), senza, ora_max.isoformat(timespec="minutes") if ora_max else "?")
    return Lettura(list(raccolti.values()), ora_max, letti)


def _sweep_orari(browser: Browser) -> None:
    """Passa il mouse sugli orari nel viewport: l'href si riempie e compare
    il tooltip con la data, che viene scritta sul nodo del post.

    L'evento deve essere trusted, quindi mouse CDP vero (vedi estrazione.py).
    Smascheramento e timbro persistono sul nodo, ma i nodi ricreati dalla
    virtualizzazione tornano vergini: si ripassa a ogni passo, e il JS elenca
    solo i post senza timbro.

    Si ripete finché la lista dei bersagli non si svuota (max 3 giri), per due
    ragioni misurate sul campo: i post si idratano ANCHE DOPO il primo sweep
    del passo, e tra la lettura delle coordinate e il mouse il layout può
    essersi spostato (immagini che caricano sopra) facendo mancare il colpo.
    Rileggere a ogni giro dà coordinate fresche e bersagli nuovi.
    """
    for _ in range(3):
        bersagli = browser.valuta(BERSAGLI_ORARIO_JS) or []
        if not bersagli:
            return
        timbrati: set[int] = set()
        for bersaglio in bersagli:
            if bersaglio.get("n") in timbrati:
                continue        # il primo anchor del post era l'orario: il secondo non serve
            browser.muovi_mouse(bersaglio["x"], bersaglio["y"])
            time.sleep(random.uniform(*ATTESA_TOOLTIP))
            esito = browser.valuta(stampa_ora_js(bersaglio["x"], bersaglio["y"])) or {}
            if esito.get("stampato"):
                timbrati.add(bersaglio.get("n"))


def _integra(
    grezzi: list[dict],
    raccolti: dict[str, Post],
    gia_visti: set[str],
    visti_di_fila: int,
    orizzonte: datetime | None = None,
) -> int:
    """Fonde una lettura del feed dentro `raccolti`; ritorna il contatore visti.

    La chiave è sempre l'impronta: così il post raccolto prima dello sweep e
    quello con l'id vero del passo dopo restano UNO, e l'id arrivato tardi
    aggiorna il record invece di duplicarlo. Lo stesso vale per l'ora.
    """
    for grezzo in grezzi:
        if grezzo.get("marketplace"):
            continue        # annuncio Marketplace: è sempre un'offerta
        testo = pulisci(grezzo["raw"])
        if len(testo) < 40:
            continue
        chiave = _impronta(grezzo["author_url"], testo)
        reale = grezzo["post_id"]
        ora = parse_ora(grezzo.get("ora"))
        stantio = orizzonte is not None and ora is not None and ora < orizzonte
        if chiave in gia_visti or (reale and reale in gia_visti) or stantio:
            # Se l'id vero (o l'ora) rivela solo ORA che il post è in database
            # o troppo vecchio, va tolto: rinotificarlo è il peggio. E ci si
            # segna l'impronta: la prossima volta che passa id-less non rientra.
            raccolti.pop(chiave, None)
            gia_visti.add(chiave)
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
                ora=_iso(ora),
            )
            continue
        visti_di_fila = 0
        if grezzo["permalink"] and post.permalink_e_del_profilo:
            post.post_id = reale or post.post_id
            post.permalink = grezzo["permalink"]
            post.permalink_e_del_profilo = False
        if len(testo) > len(post.text):
            post.text, post.troncato = testo, e_troncato(testo)
        if ora is not None and not post.ora:
            post.ora = _iso(ora)
    return visti_di_fila


def _indice_stop(grezzi: list[dict], limite: datetime) -> int | None:
    """Dove, nell'ordine del DOM, si chiude la striscia di `VECCHI_DI_FILA`
    post consecutivi non più recenti di `limite`; None se non si chiude.

    L'ordine del DOM è quello del feed. I post senza ora (mai a tiro di
    mouse, o tooltip mancato) non contano e non interrompono la striscia:
    sono quasi sempre quelli oltre il fondo del viewport.
    """
    striscia = 0
    for indice, grezzo in enumerate(grezzi):
        ora = parse_ora(grezzo.get("ora"))
        if ora is None:
            continue
        striscia = striscia + 1 if ora <= limite else 0
        if striscia >= VECCHI_DI_FILA:
            return indice
    return None


def _scarta_oltre(grezzi: list[dict], raccolti: dict[str, Post], noti: set[str]) -> None:
    """I post sotto il punto di stop sono vecchi per posizione, ora o non ora.

    Sono quelli raccolti dal render oltre il fondo del viewport: il mouse non
    ci è mai passato, quindi non hanno né id né data, e senza questo taglio
    tornerebbero come nuovi (senza permalink) e terrebbero in piedi il ripasso.
    """
    for grezzo in grezzi:
        chiave = _impronta(grezzo["author_url"], pulisci(grezzo["raw"]))
        raccolti.pop(chiave, None)
        noti.add(chiave)


def _scarta_senza_ora(raccolti: dict[str, Post]) -> None:
    """Fermati sull'ora, chi è rimasto senza ora non era nel viewport.

    Sopra il punto di stop il mouse è passato su tutto; quel che resta senza
    data è stato raccolto oltre il fondo del viewport a un passo precedente e
    poi svuotato dalla virtualizzazione prima che `_scarta_oltre` lo vedesse.
    Misurato: senza questo, due post così tenevano in piedi il ripasso per
    30 secondi e tornavano come nuovi senza permalink. Non si segnano fra i
    noti: se per caso uno era nuovo e il tooltip è mancato, torna al giro dopo.
    """
    for chiave in [k for k, p in raccolti.items() if p.ora is None]:
        del raccolti[chiave]


def _ora_massima(grezzi: list[dict]) -> datetime | None:
    ore = [parse_ora(g.get("ora")) for g in grezzi]
    return max((o for o in ore if o is not None), default=None)


def _piu_recente(a: datetime | None, b: datetime | None) -> datetime | None:
    return max((t for t in (a, b) if t is not None), default=None)


def _iso(ora: datetime | None) -> str | None:
    return ora.isoformat(timespec="minutes") if ora else None


def _ripasso(
    browser: Browser,
    raccolti: dict[str, Post],
    gia_visti: set[str],
    passi: int,
    orizzonte: datetime | None = None,
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
        _sweep_orari(browser)
        _integra(browser.valuta(RACCOLTA_POST_JS) or [], raccolti, gia_visti, 0, orizzonte)

    # Coda: il DOM renderizza un paio di schermate OLTRE il fondo del viewport,
    # e quei post sono già raccolti ma il loro orario non è mai stato a tiro di
    # mouse. Prima di risalire, qualche passo in giù per coprirli.
    for _ in range(3):
        if not _mancano():
            return
        _passo(PASSO_SCROLL)

    # Risalita fitta, fino in cima o finché non manca più niente — ma non
    # oltre il tetto: quel che resta senza permalink va col link del profilo.
    percorso = (passi + 3) * PASSO_SCROLL
    for _ in range(min(percorso // PASSO_RIPASSO + 2, PASSI_MAX_RIPASSO)):
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
