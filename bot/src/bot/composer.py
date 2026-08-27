"""Composizione dei due messaggi da inviare a mano.

Vincolo non negoziabile: nessun dettaglio che non sia in configurazione.
Inventare un prezzo o un servizio qui significa mentire a un potenziale
inquilino, e lo si scopre solo alla visita.
"""
from __future__ import annotations

import anthropic
from pydantic import BaseModel, Field

from .classifier import AnalisiPost
from .config import Config


class Messaggi(BaseModel):
    commento_pubblico: str = Field(
        description="Commento da lasciare sotto il post, 1-2 righe"
    )
    privato: str = Field(description="Messaggio privato su Messenger, 4-5 righe")


ISTRUZIONI = """Scrivi i due messaggi con cui rispondere a chi cerca una stanza in un \
gruppo Facebook di affitti. Li invierà una persona, a mano: tu prepari solo il testo.

STANZE DA PROPORRE (in ordine: la prima è la più adatta):
{stanze}

Gli identificativi fra parentesi quadre sono NOSTRI, interni: non scriverli mai
nei messaggi. Chi legge non sa cosa sia una "camera-3". Parla di "una singola",
"l'altra", "quella che si libera il 13".

REGOLA ASSOLUTA — NON INVENTARE NULLA.
Puoi usare solo i dati qui sopra. Non scrivere metrature, arredamento, servizi, \
mezzi pubblici, tipo di coinquilini o qualsiasi altro dettaglio che non sia scritto \
sopra. Se il post fa una domanda a cui i dati non rispondono, di' che se ne parla in \
privato. Un dettaglio inventato è una bugia detta a un futuro inquilino.

Sui prezzi: cita SEMPRE canone e spese condominiali separati, oppure il totale \
esplicito. Mai il canone da solo — chi legge lo prenderebbe per il costo finale.
E MAI scrivere "tutto incluso", "tutto compreso" o "spese incluse": {utenze}
Non è un dettaglio di stile, è la differenza fra un preventivo giusto e uno falso.

MESSAGGIO 1 — commento pubblico sotto il post:
Una o due righe. Dice che hai scritto in privato e mette il link alla galleria: {galleria}
Niente prezzi né dettagli: serve solo a farsi notare e a far trovare le foto.

MESSAGGIO 2 — privato su Messenger:
Massimo 4-5 righe, tono diretto e concreto, niente formule commerciali \
("cordiali saluti", "resto a disposizione", "la nostra struttura"). Scrivi come una \
persona che affitta una stanza, non come un'agenzia.
Aggancia il messaggio a quello che ha chiesto lui (zona, data, budget).
Se le stanze compatibili sono più di una, citane al massimo due, la migliore per prima.
Chiudi sempre con l'annuncio completo {annuncio} e il numero {cellulare}{firma}.

Scrivi in italiano, dando del tu."""


def componi(
    client: anthropic.Anthropic, cfg: Config, post, analisi: AnalisiPost
) -> Messaggi:
    per_id = {s.id: s for s in cfg.stanze_libere}
    scelte = [per_id[i] for i in analisi.stanze_compatibili if i in per_id]
    if not scelte:
        raise ValueError("composer chiamato senza stanze compatibili")

    istruzioni = ISTRUZIONI.format(
        stanze="\n".join(f"- {s.descrizione()}" for s in scelte),
        galleria=cfg.link_galleria,
        annuncio=cfg.link_post_fb,
        utenze=cfg.nota_utenze,
        cellulare=cfg.cellulare,
        firma=f", firmandoti {cfg.firma}" if cfg.firma else "",
    )
    contesto = (
        f"POST DI CHI CERCA:\n{post.text}\n\n"
        f"COSA ABBIAMO CAPITO: zona={analisi.zona}, budget={analisi.budget_max}, "
        f"da={analisi.disponibile_da}, durata={analisi.durata}"
    )
    risposta = client.messages.parse(
        model=cfg.modello,
        max_tokens=2000,
        system=istruzioni,
        messages=[{"role": "user", "content": contesto}],
        output_format=Messaggi,
    )
    return risposta.parsed_output
