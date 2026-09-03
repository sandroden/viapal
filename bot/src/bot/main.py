"""Entrypoint. Un giro = --once; il loop lo fa bash (vedi README).

Niente systemd, niente scheduler interno: è uno strumento da campagna, dieci
giorni acceso e poi in cantina.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import os
import sys
from dataclasses import asdict
from pathlib import Path
from datetime import datetime, timedelta
from types import SimpleNamespace

import anthropic

from .api_push import ApiViapal, spedisci_coda
from .browser import Browser, ErroreBrowser
from .classifier import analizza
from .composer import componi
from .config import carica
from .notifier import Notifier
from .report import scrivi as scrivi_report
from .scraper import MarkupCambiato, Post, raccogli
from .storage import Archivio

log = logging.getLogger("bot")

PERCORSO_CONFIG = os.environ.get("BOT_CONFIG", "~/.viapal-bot/config.toml")
PERCORSO_DB = os.environ.get("BOT_DB", "~/.viapal-bot/campagna.db")


def _api_viapal(cfg):
    """Il client viapal, o None se in configurazione non c'è la sezione [api].

    Senza, il bot funziona esattamente come prima: Telegram e basta.
    """
    if not cfg.push_attivo:
        return None
    return ApiViapal(cfg.api_base_url, cfg.api_user, cfg.api_password, cfg.api_property_id)


def _raccogli_dai_gruppi(
    browser: Browser, cfg, archivio: Archivio, adesso: datetime | None = None
) -> tuple[list, list[tuple[str, str]]]:
    """Scorre i gruppi uno dopo l'altro; ritorna i post e i gruppi muti.

    L'archivio dà a ogni gruppo il suo segnalibro (`ultima_ora`) e riceve
    quello nuovo, in sospeso: lo conferma chi gestisce i post, cioè `giro` o
    `--notifica`. I `gia_visti` sono condivisi apposta — sono il database — ma
    questo rende cieco il controllo di `raccogli`, che grida solo quando
    l'archivio è vuoto. Da qui in poi il gruppo che non dà niente va segnalato
    a mano: zero post e "non sono iscritto a quel gruppo" si somigliano troppo.

    Il segnalibro non si usa com'è: lo scroll scende `margine_segnalibro_ore`
    più in basso, perché nei gruppi moderati un post compare all'approvazione
    con l'ora in cui è stato scritto, cioè già sotto la linea di stop. E una
    volta al giorno, da `passaggio_profondo_dalle` in poi, un gruppo per giro
    si legge senza segnalibro per le ultime `passaggio_profondo_ore`: è la
    rete per i post approvati con più ritardo del margine. Un gruppo per giro
    e non l'orizzonte intero perché `--estrai` deve restare sotto il timeout
    con cui lo lancia /affitti: sul gruppo grande tre giorni sono 7 minuti.
    """
    post, falliti = [], []
    gia_visti = archivio.id_visti()
    adesso = adesso or datetime.now()
    orizzonte = (
        adesso - timedelta(days=cfg.orizzonte_giorni)
        if cfg.orizzonte_giorni else None
    )
    profondo_fatto = False
    for gid in cfg.gruppi:
        segnalibro = archivio.ultima_ora(gid)
        orizzonte_gruppo = orizzonte
        profondo = not profondo_fatto and _tocca_al_passaggio_profondo(cfg, archivio, gid, adesso)
        if profondo:
            log.info("gruppo %s: passaggio profondo del giorno, segnalibro ignorato", gid)
            segnalibro = None
            orizzonte_gruppo = _piu_recente(orizzonte, adesso - timedelta(hours=cfg.passaggio_profondo_ore))
        elif segnalibro is not None:
            segnalibro -= timedelta(hours=cfg.margine_segnalibro_ore)
        try:
            lettura = raccogli(
                browser,
                gid,
                gia_visti=gia_visti,
                stop_dopo_visti=cfg.scroll_stop_after_seen,
                max_scroll=cfg.max_scroll,
                ultima_ora=segnalibro,
                orizzonte=orizzonte_gruppo,
            )
        except MarkupCambiato as exc:
            log.error("gruppo %s: estrazione a vuoto: %s", gid, exc)
            falliti.append((gid, str(exc)))
            continue
        if profondo:
            # Subito, non in sospeso: se questo giro muore, il prossimo
            # passaggio profondo è domani e l'orizzonte copre il buco.
            archivio.segna_profondo(gid, adesso.date())
            profondo_fatto = True
        trovati = lettura.post
        archivio.segna_lettura(gid, lettura.ultima_ora)
        log.info("gruppo %s: %d post nuovi su %d letti", gid, len(trovati), lettura.letti)
        if not lettura.letti:
            # Zero post NUOVI è il giro normale; zero post nel feed no.
            falliti.append((gid, "nessun post nel feed"))
        post.extend(trovati)
    return post, falliti


def _piu_recente(a: datetime | None, b: datetime | None) -> datetime | None:
    return max((t for t in (a, b) if t is not None), default=None)


def _tocca_al_passaggio_profondo(cfg, archivio: Archivio, gid: str, adesso: datetime) -> bool:
    """Oggi, da `passaggio_profondo_dalle` in poi, e non ancora fatto oggi."""
    dalle = cfg.passaggio_profondo_dalle
    if dalle < 0 or adesso.hour < dalle:
        return False
    return archivio.profondo_fatto_il(gid) != adesso.date()


def identita(author_url: str | None, author_id: str | None = None, testo: str = "") -> str:
    """Chi è la persona, a prescindere dal gruppo in cui ha scritto.

    `author_url` porta dentro il gruppo — `/groups/<gid>/user/<uid>/` — quindi
    la stessa persona ha due URL diversi nei due gruppi e il confronto per URL
    la lascia passare due volte. L'uid invece è lo stesso ovunque: si prende da
    `author_id`, e se manca si sfila dall'URL (lo storico in archivio è tutto
    così). Per chi posta in anonimo non resta che il testo.
    """
    if author_id:
        return f"id:{author_id}"
    trovato = re.search(r"/user/(\d+)", author_url or "")
    if trovato:
        return f"id:{trovato.group(1)}"
    if author_url:
        return author_url
    return "t:" + " ".join(re.sub(r"\d+", "", testo)[:400].casefold().split())


def _da_leggere(post: list, gia_contattati: set[str]) -> list:
    """Toglie chi è già stato contattato e i doppioni dentro lo stesso giro.

    Lo stesso annuncio pubblicato in due gruppi arriva due volte: senza questo
    filtro la persona riceverebbe due notifiche e due lead su viapal.
    """
    noti = {identita(u) for u in gia_contattati}
    fuori, ids = [], set()
    for p in post:
        chi = identita(p.author_url, getattr(p, "author_id", None), p.text)
        if p.post_id in ids or chi in noti:
            continue
        ids.add(p.post_id)
        noti.add(chi)
        fuori.append(p)
    return fuori


def giro(
    percorso_config: str,
    percorso_db: str,
    dry_run: bool = False,
    ignora_orario: bool = False,
    percorso_report: str = "~/.viapal-bot/prova.html",
) -> int:
    cfg = carica(percorso_config)   # riletto a ogni giro: è così che si toglie
                                    # dal giro una stanza appena affittata
    notifier = Notifier(cfg.telegram_token, cfg.telegram_chat_id)

    if not cfg.stanze_libere:
        log.info("nessuna stanza libera in configurazione: niente da fare")
        return 0

    ora = datetime.now().hour
    inizio, fine = cfg.active_hours
    if not ignora_orario and not (inizio <= ora < fine):
        log.info("fuori dalle ore attive (%d-%d), salto il giro", inizio, fine)
        return 0

    archivio = Archivio(percorso_db)
    browser = Browser(
        profilo=cfg.profilo_browser, headed=cfg.headed, user_agent=cfg.user_agent
    )

    try:
        post, falliti = _raccogli_dai_gruppi(browser, cfg, archivio)
    except ErroreBrowser as exc:
        log.error("browser: %s", exc)
        notifier.allarme(f"agent-browser non risponde: {exc}")
        return 1

    if falliti:
        # Un gruppo rotto non deve fermare gli altri, ma nemmeno passare in
        # silenzio: senza allarme somiglia a un gruppo semplicemente tranquillo.
        notifier.allarme(
            "Gruppi che non hanno dato nulla: "
            + ", ".join(f"{gid} ({motivo})" for gid, motivo in falliti)
            + "\nControlla di essere iscritto, o apri il browser in headed: "
            "Facebook potrebbe aver chiesto una verifica."
        )
        if len(falliti) == len(cfg.gruppi):
            return 1

    client = anthropic.Anthropic()
    gia_contattati = {identita(u) for u in archivio.autori_gia_contattati()}
    trovati = 0
    lead, scartati = [], []   # solo per il rapporto della prova

    for p in post:
        try:
            analisi = analizza(client, cfg, p)
        except Exception as exc:                      # noqa: BLE001
            log.exception("classificazione fallita su %s: %s", p.post_id, exc)
            if dry_run:
                # nel rapporto va segnalato: potrebbe essere un lead perso
                scartati.append(
                    {"post": p, "analisi": SimpleNamespace(motivo=f"⚠ classificazione fallita: {exc}")}
                )
            continue

        # Dedup secondaria: a chi abbiamo già scritto non si riscrive, anche se
        # ripubblica l'annuncio con un post nuovo.
        gia_scritto = identita(p.author_url, p.author_id, p.text) in gia_contattati
        if not analisi.match or gia_scritto:
            if gia_scritto:
                log.info("%s: già contattato, salto", p.author_name)
            if dry_run:
                scartati.append({"post": p, "analisi": analisi})
            else:
                archivio.registra(p, analisi.model_dump(), matched=analisi.match)
            continue

        messaggi = componi(client, cfg, p, analisi)
        if dry_run:
            # La prova non tocca il database: altrimenti i lead che vedi qui
            # risulterebbero "già visti" e non ti arriverebbero mai su Telegram.
            lead.append({"post": p, "analisi": analisi, "messaggi": messaggi})
            log.info("lead: %s — %s", p.author_name, analisi.motivo)
        else:
            notifier.lead(
                p, analisi, messaggi,
                senza_link=cfg.commento_senza_link(getattr(p, "group_id", None)),
            )
            archivio.registra(
                p, analisi.model_dump(), matched=True, notificato=True, messaggi=messaggi
            )
            # Chi posta lo stesso annuncio in due gruppi arriva qui due volte
            # nello stesso giro: senza questo si prende due messaggi.
            gia_contattati.add(identita(p.author_url, p.author_id, p.text))
        trovati += 1

    if dry_run:
        percorso = scrivi_report(percorso_report, lead, scartati)
        log.info("rapporto: %s", percorso)
        print(f"\n→ apri file://{percorso}")

    # Dopo le notifiche: se il server è giù la coda resta piena e il prossimo
    # giro ci riprova, ma il lead su Telegram è già arrivato comunque.
    if not dry_run:
        archivio.conferma_letture()   # i post sono gestiti: il segnalibro avanza
        spedisci_coda(_api_viapal(cfg), archivio, notifier)

    log.info("giro concluso: %d post nuovi, %d lead", len(post), trovati)
    return 0


def estrai(percorso_config: str, percorso_db: str, destinazione: str) -> int:
    """Raccoglie i post nuovi in un JSON, senza chiamare nessun modello.

    È la metà del lavoro che non ha bisogno dell'API. Serve a far classificare i
    post da Claude Code — che sta nell'abbonamento — invece che a consumo:
    Claude legge questo file, decide, e riconsegna i lead a `--notifica`.
    """
    cfg = carica(percorso_config)
    archivio = Archivio(percorso_db)
    browser = Browser(
        profilo=cfg.profilo_browser, headed=cfg.headed, user_agent=cfg.user_agent
    )
    post, falliti = _raccogli_dai_gruppi(browser, cfg, archivio)
    for gid, motivo in falliti:
        print(f"⚠ gruppo {gid}: {motivo} — controlla di essere iscritto a quel gruppo")
    # Il flag sta sul post, non a parte in una lista di gruppi: chi legge il
    # JSON (Claude) deve vederlo accanto al testo, senza incrociare niente.
    da_leggere = [
        {**asdict(p), "commento_senza_link": cfg.commento_senza_link(p.group_id)}
        for p in _da_leggere(post, archivio.autori_gia_contattati())
    ]
    if not da_leggere:
        # Niente da consegnare a Claude, quindi niente che possa andare perso:
        # il segnalibro avanza subito. Altrimenti lo conferma --notifica, e un
        # giro a vuoto (che --notifica non lo chiama) lo lascerebbe fermo.
        archivio.conferma_letture()
    percorso = Path(destinazione).expanduser()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(
        json.dumps(
            {
                "stanze": [asdict(s) for s in cfg.stanze_libere],
                "zone_accettate": list(cfg.zone_accettate),
                "post": da_leggere,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    log.info("%d post nuovi scritti in %s", len(da_leggere), percorso)
    print(f"{len(da_leggere)} post nuovi da leggere → {percorso}")
    return 0


def notifica(percorso_config: str, percorso_db: str, sorgente: str) -> int:
    """Manda le notifiche partendo da un JSON di lead già classificati e scritti.

    Formato: {"lead": [...], "scartati": [...]}. Gli scartati vanno passati
    anche loro, altrimenti al giro dopo ricompaiono come nuovi.
    """
    cfg = carica(percorso_config)
    archivio = Archivio(percorso_db)
    notifier = Notifier(cfg.telegram_token, cfg.telegram_chat_id)
    dati = json.loads(Path(sorgente).expanduser().read_text(encoding="utf-8"))

    for voce in dati.get("scartati", []):
        archivio.registra(
            Post(**_campi_post(voce)),
            {"motivo": voce.get("motivo", "")},
            matched=False,
        )

    inviati = 0
    for voce in dati.get("lead", []):
        post = Post(**_campi_post(voce))
        analisi = SimpleNamespace(
            zona=voce.get("zona"),
            budget_max=voce.get("budget_max"),
            disponibile_da=voce.get("disponibile_da"),
            stanze_compatibili=voce.get("stanze_compatibili", []),
            motivo=voce.get("motivo", ""),
        )
        notifier.lead(
            post,
            analisi,
            SimpleNamespace(
                commento_pubblico=voce["commento_pubblico"], privato=voce["privato"]
            ),
            senza_link=cfg.commento_senza_link(post.group_id),
        )
        archivio.registra(
            post,
            vars(analisi),
            matched=True,
            notificato=True,
            messaggi=SimpleNamespace(
                commento_pubblico=voce["commento_pubblico"], privato=voce["privato"]
            ),
        )
        inviati += 1

    # Lead e scarti sono registrati: la lettura di --estrai diventa il
    # segnalibro. Se questo passo salta, il giro dopo rilegge gli stessi post.
    archivio.conferma_letture()
    spedisci_coda(_api_viapal(cfg), archivio, notifier)

    scarti = len(dati.get("scartati", []))
    log.info("notificati %d lead, registrati %d scarti", inviati, scarti)
    print(f"{inviati} notifiche inviate, {scarti} scarti registrati")
    return 0


def _campi_post(voce: dict) -> dict:
    """Ricostruisce un Post vero, non un SimpleNamespace: serve la property
    link_messenger, che è quella che porta il tap dritto in chat."""
    return {
        "post_id": voce["post_id"],
        "permalink": voce.get("permalink", ""),
        "author_name": voce.get("author_name"),
        "author_url": voce.get("author_url"),
        "author_id": voce.get("author_id"),
        "text": voce.get("text", ""),
        "permalink_e_del_profilo": voce.get("permalink_e_del_profilo", False),
        # `--estrai` lo scrive nel JSON (asdict): senza rileggerlo qui, il
        # giro che passa da Claude Code perderebbe per strada il gruppo.
        "group_id": voce.get("group_id", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Bot di monitoraggio affitti Monza")
    parser.add_argument("--once", action="store_true", help="un solo giro (default)")
    parser.add_argument(
        "--estrai", metavar="FILE",
        help="scrive i post nuovi in JSON senza classificarli (per Claude Code)",
    )
    parser.add_argument(
        "--notifica", metavar="FILE",
        help="manda le notifiche da un JSON di lead già classificati e scritti",
    )
    parser.add_argument("--config", default=PERCORSO_CONFIG)
    parser.add_argument("--db", default=PERCORSO_DB)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="stampa i messaggi invece di notificarli, e non segna nulla come inviato",
    )
    parser.add_argument(
        "--report", default="~/.viapal-bot/prova.html",
        help="dove scrivere il rapporto HTML della prova",
    )
    parser.add_argument(
        "--ignora-orario", action="store_true",
        help="gira anche fuori da active_hours (per le prove a mano)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    if args.estrai:
        return estrai(args.config, args.db, args.estrai)
    if args.notifica:
        return notifica(args.config, args.db, args.notifica)
    return giro(
        args.config,
        args.db,
        dry_run=args.dry_run,
        ignora_orario=args.ignora_orario,
        percorso_report=args.report,
    )


if __name__ == "__main__":
    sys.exit(main())
