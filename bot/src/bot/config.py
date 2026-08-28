"""Configurazione: un TOML fuori dal repo, riletto a ogni giro del loop.

Rileggere ogni volta è il meccanismo con cui si toglie dal giro una stanza
appena affittata: si edita il file e si salva, senza riavviare niente.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Stanza:
    id: str
    libera: bool
    tipo: str
    prezzo: int
    spese_condominio: int
    disponibile_da: str = ""
    note: str = ""

    @property
    def totale(self) -> int:
        """Canone + spese. È l'unico numero che ha senso confrontare con il
        budget dichiarato in un post: quasi tutti scrivono "tutto incluso"."""
        return self.prezzo + self.spese_condominio

    def descrizione(self) -> str:
        pezzi = [f"[{self.id}] {self.tipo}, {self.prezzo}€ + {self.spese_condominio}€ "
                 f"di spese condominiali (totale {self.totale}€/mese)"]
        if self.disponibile_da:
            pezzi.append(f"libera dal {self.disponibile_da}")
        if self.note:
            pezzi.append(self.note)
        return ", ".join(pezzi)


@dataclass(frozen=True)
class Config:
    # I gruppi da leggere, in ordine. Uno solo è il caso normale; più d'uno
    # serve quando lo stesso annuncio si pesca in bacini diversi.
    gruppi: tuple[str, ...]
    poll_interval_minutes: int
    active_hours: tuple[int, int]
    scroll_stop_after_seen: int
    max_scroll: int
    headed: bool
    profilo_browser: str
    user_agent: str | None
    stanze: tuple[Stanza, ...]
    link_galleria: str
    link_post_fb: str
    cellulare: str
    nota_utenze: str
    indirizzo: str
    punti_forza: tuple[str, ...]
    regole: str
    non_abbiamo: str
    firma: str
    zone_accettate: tuple[str, ...]
    escludi_tipologie: tuple[str, ...]
    telegram_token: str
    telegram_chat_id: str
    modello_classifier: str
    modello_composer: str
    # Push dei lead su viapal: assente = disattivato, il bot resta com'era.
    api_base_url: str = ""
    api_user: str = ""
    api_password: str = ""
    api_property_id: str = ""

    @property
    def push_attivo(self) -> bool:
        return bool(self.api_base_url and self.api_user and self.api_property_id)

    @property
    def stanze_libere(self) -> tuple[Stanza, ...]:
        return tuple(s for s in self.stanze if s.libera)


def _gruppi(fb: dict) -> tuple[str, ...]:
    """`gruppi = [...]` è la forma buona; `group_id` singolo resta valido.

    Tenere il vecchio nome evita che una config non ancora migrata smetta di
    leggere il gruppo storico proprio mentre se ne aggiunge un altro.
    """
    elenco = [str(g) for g in fb.get("gruppi", []) if str(g).strip()]
    if not elenco and fb.get("group_id"):
        elenco = [str(fb["group_id"])]
    if not elenco:
        raise KeyError("serve facebook.gruppi (o il vecchio facebook.group_id)")
    return tuple(dict.fromkeys(elenco))   # senza doppioni, ordine tenuto


def carica(percorso: str | Path) -> Config:
    dati = tomllib.loads(Path(percorso).expanduser().read_text(encoding="utf-8"))
    fb, contatto = dati["facebook"], dati["contatto"]
    casa = dati.get("casa", {})
    matching, tg = dati["matching"], dati["telegram"]
    api = dati.get("api", {})
    return Config(
        gruppi=_gruppi(fb),
        poll_interval_minutes=int(fb.get("poll_interval_minutes", 25)),
        active_hours=tuple(fb.get("active_hours", [8, 23])),
        scroll_stop_after_seen=int(fb.get("scroll_stop_after_seen", 10)),
        max_scroll=int(fb.get("max_scroll", 45)),
        headed=bool(fb.get("headed", False)),
        profilo_browser=str(fb.get("profilo_browser", "~/.viapal-bot/fb-profile")),
        user_agent=fb.get("user_agent") or None,
        stanze=tuple(
            Stanza(
                id=s["id"],
                libera=bool(s.get("libera", True)),
                tipo=s.get("tipo", "singola"),
                prezzo=int(s["prezzo"]),
                spese_condominio=int(s.get("spese_condominio", 0)),
                disponibile_da=s.get("disponibile_da", ""),
                note=s.get("note", ""),
            )
            for s in dati.get("stanze", [])
        ),
        link_galleria=contatto["link_galleria"],
        link_post_fb=contatto["link_post_fb"],
        cellulare=contatto["cellulare"],
        nota_utenze=contatto.get(
            "nota_utenze",
            "il riscaldamento è già compreso nelle spese condominiali; le altre "
            "utenze (luce, gas, acqua, rifiuti) sono a parte e si dividono fra gli "
            "inquilini in base ai consumi.",
        ),
        firma=contatto.get("firma", ""),
        indirizzo=casa.get("indirizzo", ""),
        punti_forza=tuple(casa.get("punti_forza", [])),
        regole=casa.get("regole", ""),
        non_abbiamo=casa.get("non_abbiamo", ""),
        zone_accettate=tuple(matching.get("zone_accettate", [])),
        escludi_tipologie=tuple(matching.get("escludi_tipologie", [])),
        telegram_token=tg["bot_token"],
        telegram_chat_id=str(tg["chat_id"]),
        # Classificare è meccanico e va bene un modello piccolo; scrivere un
        # messaggio che non suoni un'agenzia no. Separarli taglia il conto di
        # quasi tutto, perché le classificazioni sono cento volte le scritture.
        modello_classifier=dati.get("llm", {}).get("classifier", "claude-haiku-4-5"),
        modello_composer=dati.get("llm", {}).get("composer", "claude-opus-5"),
        api_base_url=api.get("base_url", ""),
        api_user=api.get("user", ""),
        api_password=api.get("password", ""),
        api_property_id=str(api.get("property_id", "")),
    )
