"""Notifiche Telegram. Un messaggio per lead, con i due testi già pronti.

I testi vanno in blocchi di codice: su Telegram il tap su un blocco copia il
contenuto. Il flusso è tap → apri il post → incolla → invia.
"""
from __future__ import annotations

import logging

import httpx

from .classifier import AnalisiPost
from .composer import Messaggi

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/sendMessage"

# Caratteri che MarkdownV2 pretende siano preceduti da backslash.
DA_SCAPPARE = r"_*[]()~`>#+-=|{}.!"


def _esc(testo: str) -> str:
    return "".join("\\" + c if c in DA_SCAPPARE else c for c in str(testo))


class Notifier:
    def __init__(self, token: str, chat_id: str):
        self.token, self.chat_id = token, chat_id

    def _invia(self, testo: str) -> None:
        risposta = httpx.post(
            API.format(token=self.token),
            json={
                "chat_id": self.chat_id,
                "text": testo,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if risposta.status_code != 200:
            log.error("telegram: %s %s", risposta.status_code, risposta.text[:300])

    def lead(self, post, analisi: AnalisiPost, messaggi: Messaggi) -> None:
        estratto = post.text[:300] + ("…" if len(post.text) > 300 else "")
        campi = [f"*{_esc(post.author_name or 'anonimo')}*"]
        if analisi.zona:
            campi.append(f"📍 {_esc(analisi.zona)}")
        if analisi.budget_max:
            campi.append(f"💶 max {_esc(analisi.budget_max)}€")
        if analisi.disponibile_da:
            campi.append(f"📅 {_esc(analisi.disponibile_da)}")

        testo = (
            "🏠 " + " · ".join(campi) + "\n"
            f"➡️ {_esc(', '.join(analisi.stanze_compatibili))}\n"
            f"_{_esc(analisi.motivo)}_\n\n"
            f"{_esc(estratto)}\n\n"
            f"[apri il post]({post.permalink})\n\n"
            "*1\\. commento sotto il post:*\n"
            f"```\n{messaggi.commento_pubblico}\n```\n"
            "*2\\. privato su Messenger:*\n"
            f"```\n{messaggi.privato}\n```"
        )
        self._invia(testo)

    def allarme(self, messaggio: str) -> None:
        """Il markup è cambiato, o qualcosa si è rotto. Meglio saperlo subito che
        scoprire a fine campagna che il bot girava a vuoto."""
        self._invia(f"⚠️ *bot affitti*\n{_esc(messaggio)}")

    def riepilogo(self, testo: str) -> None:
        self._invia(_esc(testo))
