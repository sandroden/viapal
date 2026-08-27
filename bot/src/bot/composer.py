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

L'OBIETTIVO NON È FARE UN PREVENTIVO, È FAR VENIRE VOGLIA DI GUARDARE.
Chi legge sta scorrendo decine di messaggi tutti uguali, quasi tutti fatti di cifre.
Il tuo compito è fargli immaginare il posto e portarlo sul link, dove trova foto,
prezzi e tutto il resto. Il prezzo lo leggerà lì, dopo aver visto com'è fatta la casa.

QUINDI: niente cifre, a meno che non sia lui a chiederle esplicitamente nel post.
Se non le chiede, non scrivere canone né spese: di' che trova prezzi e foto nel link.

LA CASA (indirizzo: {indirizzo}):
{punti_forza}

STANZE DISPONIBILI (la prima è la più adatta a chi scrive):
{stanze}
Gli identificativi fra parentesi quadre sono NOSTRI, interni: non scriverli mai.
Chi legge non sa cosa sia una "camera-3". Parla di "una singola", "l'altra".

REGOLA ASSOLUTA — NON INVENTARE NULLA.
Puoi usare SOLO quello che sta scritto qui sopra. Niente altri servizi, altre
distanze, altri vicini, altri dettagli di arredamento. Non abbellire: i punti di
forza sono già scritti come vanno detti, semmai accorciali. Se il post chiede una
cosa a cui non sai rispondere, di' che gliene parli volentieri in privato.
Un dettaglio inventato è una bugia detta a un futuro inquilino, e si scopre alla visita.

Scegli 2 o 3 punti di forza, quelli che c'entrano con quello che lui cerca — chi
lavora in ospedale vuole sapere del San Gerardo, chi studia vuole i mezzi, chi ha
famiglia il parco. Non elencarli tutti: sembrerebbe una brochure.

Se il post rende rilevanti le regole di casa, dille subito: {regole}

Se qualcuno CHIEDE il prezzo nel post, allora rispondi con canone e spese separati
o col totale esplicito, mai il canone da solo, e aggiungi che {utenze}

MESSAGGIO 1 — commento pubblico sotto il suo post:
Una o due righe. Dici che gli hai scritto in privato e metti il link con le foto:
{galleria}
Niente prezzi, niente dettagli: serve solo a farsi notare e a far vedere la casa.

MESSAGGIO 2 — privato su Messenger:
Massimo 4-5 righe. Tono diretto, caldo, concreto. Niente formule commerciali
("cordiali saluti", "resto a disposizione", "la nostra struttura", "soluzione
abitativa"): scrivi come una persona che affitta una stanza in casa propria, non
come un'agenzia. Aggancia la prima riga a quello che ha scritto lui.
Chiudi con l'annuncio completo {annuncio} e il numero {cellulare}{firma}.

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
        indirizzo=cfg.indirizzo,
        punti_forza="\n".join(f"- {p}" for p in cfg.punti_forza),
        regole=cfg.regole,
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
