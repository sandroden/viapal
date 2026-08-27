"""Classificazione dei post: cerca o offre? stanza o appartamento? quale budget?

Una chiamata per post. Il testo arriva grezzo (innerText ripulito) e tutta
l'interpretazione è delegata al modello: è la scelta che tiene il codice
insensibile ai cambi di markup.
"""
from __future__ import annotations

import logging
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from .config import Config, Stanza

log = logging.getLogger(__name__)


class AnalisiPost(BaseModel):
    intent: Literal["cerca", "offre", "altro"]
    tipo_immobile: Literal[
        "stanza_singola", "stanza_doppia", "posto_letto",
        "monolocale", "bilocale", "appartamento", "non_specificato",
    ]
    zona: str | None = None
    budget_max: int | None = Field(
        default=None, description="Budget mensile massimo in euro, se dichiarato"
    )
    disponibile_da: str | None = None
    durata: str | None = None
    match: bool
    stanze_compatibili: list[str] = Field(
        default_factory=list, description="id delle stanze libere che reggono i vincoli"
    )
    motivo: str


ISTRUZIONI = """Sei il filtro di lettura di un gruppo Facebook di annunci di affitto \
della zona di Monza e Brianza. Leggi un post e decidi se è un potenziale inquilino \
per le stanze che abbiamo libere.

STANZE LIBERE (le uniche che possiamo proporre):
{stanze}

ZONE ACCETTABILI: {zone}
Le stanze sono a Monza: chi cerca in un comune limitrofo o "a Monza e dintorni" va \
tenuto. Chi cerca in una città lontana (Milano città, Como, Bergamo...) va scartato.

REGOLE DI MATCHING — applicale in quest'ordine:

1. match = true SOLO se intent == "cerca". Chi offre casa, chi commenta, chi fa altro: \
match = false.
2. Il tipo cercato dev'essere una stanza (singola, doppia, posto letto). \
Monolocali, bilocali e appartamenti interi vanno esclusi: non abbiamo niente da \
proporre. ATTENZIONE: chi scrive "monolocale o stanza" va TENUTO — una stanza gliela \
possiamo dare.
3. Zona incompatibile → match = false.
4. Se il post dichiara un budget massimo, metti in stanze_compatibili solo le stanze \
il cui TOTALE (canone + spese) sta entro quel budget. Se nessuna ci sta, match = false \
e scrivilo nel motivo. Se non dichiara budget, sono compatibili tutte.
5. In caso di dubbio genuino, match = true e segnala il dubbio nel motivo: una \
notifica da scartare costa dieci secondi, un lead perso costa un mese di sfitto.

Il campo `motivo` è una riga in italiano che spiega la decisione a chi legge la \
notifica sul telefono.{nota_troncato}"""

NOTA_TRONCATO = """

ATTENZIONE: questo post è TRONCATO (Facebook lo mostra collassato). Le informazioni \
mancanti potrebbero cambiare la valutazione: in caso di dubbio tieni il lead."""


def _elenco_stanze(stanze: tuple[Stanza, ...]) -> str:
    return "\n".join(f"- {s.descrizione()}" for s in stanze)


def analizza(client: anthropic.Anthropic, cfg: Config, post) -> AnalisiPost:
    istruzioni = ISTRUZIONI.format(
        stanze=_elenco_stanze(cfg.stanze_libere),
        zone=", ".join(cfg.zone_accettate),
        nota_troncato=NOTA_TRONCATO if getattr(post, "troncato", False) else "",
    )
    risposta = client.messages.parse(
        model=cfg.modello,
        max_tokens=2000,
        system=istruzioni,
        messages=[{"role": "user", "content": f"POST:\n\n{post.text}"}],
        output_format=AnalisiPost,
        output_config={"effort": "low"},
    )
    analisi = risposta.parsed_output

    # Rete di sicurezza: il modello non deve poter proporre una stanza occupata,
    # nemmeno sbagliando. Se una stanza è stata tolta dal TOML mentre il post
    # era in coda, qui sparisce comunque.
    libere = {s.id for s in cfg.stanze_libere}
    analisi.stanze_compatibili = [s for s in analisi.stanze_compatibili if s in libere]
    if analisi.match and not analisi.stanze_compatibili:
        analisi.match = False
        analisi.motivo = f"{analisi.motivo} [nessuna stanza libera compatibile]"
    return analisi
