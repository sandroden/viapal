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


def _link(post) -> str:
    """I due link della notifica, nell'ordine in cui servono.

    Prima Messenger — è lì che si incolla il privato — poi il post, ma solo se
    è davvero il permalink del post: senza, il fallback aprirebbe il gruppo, e
    sul cellulare succedeva anche col profilo dentro al gruppo.
    """
    voci = []
    messenger = getattr(post, "link_messenger", None)
    if messenger:
        nome = post.author_name or "questa persona"
        voci.append(f"[scrivi a {_esc(nome)}]({messenger})")
    if post.permalink and not getattr(post, "permalink_e_del_profilo", False):
        voci.append(f"[apri il post]({post.permalink})")
    return " · ".join(voci) if voci else ""


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
            f"{_link(post)}\n\n"
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

    def svuota_chat(self, fino_a: int = 400) -> int:
        """Cancella i messaggi che il bot ha mandato in questa chat.

        Telegram non offre un "svuota tutto": si cancella un messaggio per volta
        e solo entro 48 ore dall'invio. Gli id sono progressivi nella chat, quindi
        si prova tutto il range e si ignorano i buchi — i messaggi tuoi il bot non
        li può toccare, quindi non c'è nulla da rovinare.

        Per la roba più vecchia di 48 ore non c'è API: si svuota la chat dal
        telefono (menu della chat → Elimina chat).
        """
        url = f"https://api.telegram.org/bot{self.token}/deleteMessage"
        cancellati = 0
        with httpx.Client(timeout=15) as http:
            for message_id in range(1, fino_a + 1):
                try:
                    esito = http.post(
                        url, json={"chat_id": self.chat_id, "message_id": message_id}
                    )
                except httpx.HTTPError:
                    continue
                if esito.status_code == 200 and esito.json().get("ok"):
                    cancellati += 1
        return cancellati
