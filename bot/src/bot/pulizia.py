"""Ripulisce l'innerText grezzo di un post di Facebook.

Sta qui e non nel JS apposta: è la parte che si testa senza browser, e quando
il markup cambia non è questa a rompersi.
"""
from __future__ import annotations

# Righe di chrome dell'interfaccia che compaiono dentro ogni post.
# "Facebook" è il <title> degli SVG delle icone e si ripete decine di volte.
RIGHE_DA_BUTTARE = {"Facebook", "·", "Segui", "Tutte le reazioni:", ""}

# Dove cominciano i commenti. Tagliare qui è importante: un commento
# "cerco stanza" sotto un post "affitto bilocale" farebbe classificare male
# il post.
INIZIO_COMMENTI = ("Rispondi", "Visualizza altri commenti", "Visualizza 1 risposta")

# Coda fissa del box commenti.
CODA = ("Commenta come", "Scrivi un commento")


def pulisci(raw: str) -> str:
    righe = [r.strip() for r in raw.split("\n")]
    righe = [r for r in righe if r not in RIGHE_DA_BUTTARE]

    taglio = _inizio_commenti(righe)
    righe = righe[:taglio]

    # I contatori di reazioni finiscono in coda come righe di soli numeri.
    while righe and righe[-1].isdigit():
        righe.pop()

    return "\n".join(righe).strip()


def _inizio_commenti(righe: list[str]) -> int:
    """Indice della prima riga da buttare.

    Sotto il testo del post Facebook mette il blocco dei contatori di reazioni
    (righe di soli numeri) e subito dopo i commenti, ognuno nella forma
    ``nome / orario / testo / Rispondi``. Non basta tagliare a "Rispondi":
    resterebbero attaccati al post il nome e il commento di chi ha risposto.
    Quindi si trova "Rispondi" e si risale al blocco di contatori, che è il
    confine vero fra post e commenti.
    """
    for i, riga in enumerate(righe):
        if riga.startswith(CODA):
            return i
        if riga not in INIZIO_COMMENTI:
            continue
        j = i - 1
        while j >= 0 and not righe[j].isdigit():   # indietro fino ai contatori
            j -= 1
        while j >= 0 and righe[j].isdigit():       # e fino a inizio blocco
            j -= 1
        return j + 1 if j >= 0 else max(0, i - 3)
    return len(righe)


def e_troncato(testo: str) -> bool:
    """Facebook collassa i post lunghi. Il click su "Altro" è escluso (è
    un'azione, e in prova ha fatto perdere il feed): il post arriva mozzato e
    lo si segnala al classifier, che in caso di dubbio deve tenere il lead."""
    return "Altro..." in testo or testo.endswith("…")
