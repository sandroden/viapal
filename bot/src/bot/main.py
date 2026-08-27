"""Entrypoint. Un giro = --once; il loop lo fa bash (vedi README).

Niente systemd, niente scheduler interno: è uno strumento da campagna, dieci
giorni acceso e poi in cantina.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime

import anthropic

from .browser import Browser, ErroreBrowser
from .classifier import analizza
from .composer import componi
from .config import carica
from .notifier import Notifier
from .scraper import MarkupCambiato, raccogli
from .storage import Archivio

log = logging.getLogger("bot")

PERCORSO_CONFIG = os.environ.get("BOT_CONFIG", "~/.viapal-bot/config.toml")
PERCORSO_DB = os.environ.get("BOT_DB", "~/.viapal-bot/campagna.db")


def giro(
    percorso_config: str,
    percorso_db: str,
    dry_run: bool = False,
    ignora_orario: bool = False,
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
        post = raccogli(
            browser,
            cfg.group_id,
            gia_visti=archivio.id_visti(),
            stop_dopo_visti=cfg.scroll_stop_after_seen,
        )
    except MarkupCambiato as exc:
        log.error("estrazione a vuoto: %s", exc)
        notifier.allarme(
            f"Nessun post estratto: {exc}\n"
            "Controlla il JS in estrazione.py, oppure apri il browser in headed: "
            "Facebook potrebbe aver chiesto una verifica."
        )
        return 1
    except ErroreBrowser as exc:
        log.error("browser: %s", exc)
        notifier.allarme(f"agent-browser non risponde: {exc}")
        return 1

    client = anthropic.Anthropic()
    gia_contattati = archivio.autori_gia_contattati()
    trovati = 0

    for p in post:
        try:
            analisi = analizza(client, cfg, p)
        except Exception as exc:                      # noqa: BLE001
            log.exception("classificazione fallita su %s: %s", p.post_id, exc)
            continue

        # Dedup secondaria: a chi abbiamo già scritto non si riscrive, anche se
        # ripubblica l'annuncio con un post nuovo.
        gia_scritto = p.author_url and p.author_url in gia_contattati
        if not analisi.match or gia_scritto:
            if gia_scritto:
                log.info("%s: già contattato, salto", p.author_name)
            archivio.registra(p, analisi.model_dump(), matched=analisi.match)
            continue

        messaggi = componi(client, cfg, p, analisi)
        if dry_run:
            print(f"\n=== {p.author_name} — {analisi.motivo}")
            print(f"[pubblico] {messaggi.commento_pubblico}")
            print(f"[privato]  {messaggi.privato}")
        else:
            notifier.lead(p, analisi, messaggi)
        archivio.registra(p, analisi.model_dump(), matched=True, notificato=not dry_run)
        trovati += 1

    log.info("giro concluso: %d post nuovi, %d lead", len(post), trovati)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bot di monitoraggio affitti Monza")
    parser.add_argument("--once", action="store_true", help="un solo giro (default)")
    parser.add_argument("--config", default=PERCORSO_CONFIG)
    parser.add_argument("--db", default=PERCORSO_DB)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="stampa i messaggi invece di notificarli, e non segna nulla come inviato",
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
    return giro(
        args.config, args.db, dry_run=args.dry_run, ignora_orario=args.ignora_orario
    )


if __name__ == "__main__":
    sys.exit(main())
