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
    budget_tassativo: bool = Field(
        default=False,
        description="Vero solo se dichiara il budget come limite rigido "
        "('massimo', 'non posso superare', 'tassativo')",
    )
    animali: bool = Field(
        default=False, description="Vero se dichiara di avere un animale"
    )
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

Il criterio NON è la distanza, è il prezzo di mercato. Monza costa più dei comuni
intorno: chi cerca dove si paga meno (Lesmo, Limbiate, Bovisio, Cesano Maderno,
Seregno, Desio...) ha in testa cifre più basse delle nostre, e proporgli una stanza
a Monza significa competere con un mercato diverso. Non è un buon contatto, anche
se sulla mappa è a dieci chilometri.

Quindi: va tenuto chi nomina Monza — da sola, insieme ad altri comuni, o come
"Monza e dintorni" — e chi cerca in uno dei comuni in lista. Va scartato chi nomina
solo comuni fuori lista, e chi cerca in una città lontana (Milano città, Como,
Bergamo). Se non dichiara nessuna zona, non scartarlo per questo.

ATTENZIONE, la zona è l'ECCEZIONE alla regola 6 sul dubbio: le formule vaghe
attaccate a un comune fuori lista ("Lesmo o vicinanze", "Seregno e dintorni",
"zone ben collegate") NON bastano a tenerlo. Chi scrive così ha in testa i prezzi
di quel comune, non quelli di Monza. Serve che Monza o un comune della lista sia
nominato davvero.

REGOLE DI MATCHING — applicale in quest'ordine:

1. match = true SOLO se intent == "cerca". Chi offre casa, chi commenta, chi fa altro: \
match = false.
2. Il tipo cercato dev'essere una stanza (singola, doppia, posto letto). \
Monolocali, bilocali e appartamenti interi vanno esclusi: non abbiamo niente da \
proporre. ATTENZIONE: chi scrive "monolocale o stanza" va TENUTO — una stanza gliela \
possiamo dare.
3. Zona incompatibile → match = false.
4. ANIMALI: se dichiara di avere un cane, un gatto o un altro animale, animali = true \
e match = false. In casa non sono ammessi: non è negoziabile e non ha senso scrivergli. \
Se l'animale è solo ipotetico o non è chiaro, animali = false e vai avanti.
5. Sul BUDGET non essere rigido. Molti scrivono una cifra prima di essersi resi conto \
di quanto costa Monza, e la alzano quando vedono la casa. Quindi:
   - metti in stanze_compatibili le stanze il cui TOTALE (canone + spese) sta entro il \
     budget dichiarato;
   - se NESSUNA ci sta, NON scartarlo: match = true lo stesso, stanze_compatibili con \
     la più economica, e nel motivo scrivi di quanto siamo sopra;
   - l'unica eccezione è chi dichiara il budget come limite RIGIDO ("massimo", "non \
     posso superare", "tassativo", "oltre non vado"): allora budget_tassativo = true, \
     e se nessuna stanza ci sta match = false.
6. In caso di dubbio genuino, match = true e segnala il dubbio nel motivo: una \
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
        model=cfg.modello_classifier,
        max_tokens=2000,
        system=istruzioni,
        messages=[{"role": "user", "content": f"POST:\n\n{post.text}"}],
        output_format=AnalisiPost,
        output_config={"effort": "low"},
    )
    analisi = risposta.parsed_output
    if analisi is None:
        # Capita di rado (il modello non produce output valido). Non è fatale:
        # chi chiama salta il post e va avanti, ma deve saperlo.
        raise ValueError(
            f"il modello non ha restituito un'analisi valida "
            f"(stop_reason={risposta.stop_reason})"
        )

    # Reti di sicurezza: quello che segue non deve dipendere dal fatto che il
    # modello abbia seguito il prompt.

    # Gli animali non sono ammessi e non è una preferenza: se lo dichiara, si
    # chiude qui, senza notifica.
    if analisi.animali:
        analisi.match = False
        analisi.motivo = f"{analisi.motivo} [ha un animale: non possiamo]"
        analisi.stanze_compatibili = []
        return analisi

    # Una stanza tolta dal TOML mentre il post era in coda non dev'essere
    # proposta lo stesso.
    libere = {s.id for s in cfg.stanze_libere}
    analisi.stanze_compatibili = [s for s in analisi.stanze_compatibili if s in libere]

    # Budget sotto le nostre stanze: si scrive lo stesso, con la più economica —
    # tranne a chi l'ha dichiarato come limite rigido.
    if analisi.match and not analisi.stanze_compatibili:
        if analisi.budget_tassativo:
            analisi.match = False
            analisi.motivo = f"{analisi.motivo} [budget dichiarato rigido, siamo sopra]"
        elif cfg.stanze_libere:
            piu_economica = min(cfg.stanze_libere, key=lambda s: s.totale)
            analisi.stanze_compatibili = [piu_economica.id]
            analisi.motivo = f"{analisi.motivo} [sopra il budget indicato: si prova lo stesso]"
        else:
            analisi.match = False
            analisi.motivo = f"{analisi.motivo} [nessuna stanza libera]"
    return analisi
