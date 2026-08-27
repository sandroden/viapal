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
    group_id: str
    poll_interval_minutes: int
    active_hours: tuple[int, int]
    scroll_stop_after_seen: int
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
    firma: str
    zone_accettate: tuple[str, ...]
    escludi_tipologie: tuple[str, ...]
    telegram_token: str
    telegram_chat_id: str
    modello: str

    @property
    def stanze_libere(self) -> tuple[Stanza, ...]:
        return tuple(s for s in self.stanze if s.libera)


def carica(percorso: str | Path) -> Config:
    dati = tomllib.loads(Path(percorso).expanduser().read_text(encoding="utf-8"))
    fb, contatto = dati["facebook"], dati["contatto"]
    casa = dati.get("casa", {})
    matching, tg = dati["matching"], dati["telegram"]
    return Config(
        group_id=str(fb["group_id"]),
        poll_interval_minutes=int(fb.get("poll_interval_minutes", 25)),
        active_hours=tuple(fb.get("active_hours", [8, 23])),
        scroll_stop_after_seen=int(fb.get("scroll_stop_after_seen", 10)),
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
        zone_accettate=tuple(matching.get("zone_accettate", [])),
        escludi_tipologie=tuple(matching.get("escludi_tipologie", [])),
        telegram_token=tg["bot_token"],
        telegram_chat_id=str(tg["chat_id"]),
        modello=dati.get("llm", {}).get("modello", "claude-opus-5"),
    )
