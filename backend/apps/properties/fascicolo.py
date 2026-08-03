"""Fascicolo documenti dell'inquilino: la checklist con gli stati derivati.

L'elenco piatto dei ``TenantDocument`` risponde alla domanda «quali file ci
sono»; l'interfaccia deve invece rispondere a «cosa manca e cosa scade».
Questo modulo fa la trasformazione una volta sola — raggruppa i file per
*tipo* (fronte/retro diventano due pagine dello stesso documento) e calcola
lo stato di ogni voce — così inquilino e proprietario vedono gli stessi
stati con la stessa soglia di scadenza.

Stati di una voce:

``ok``
    caricato e senza scadenza, o con scadenza lontana.
``scadenza``
    scade entro :data:`GIORNI_PREAVVISO_SCADENZA` giorni.
``scaduto``
    la data di scadenza è passata.

**Nessun documento è obbligatorio**: non esiste uno stato "mancante" e il
fascicolo non conta quanto manca. I documenti sono copie di cortesia, e dopo
la verifica possono anche essere cancellati (meno dati conservati, meno
rischio).

**Il fascicolo elenca solo i file che esistono** (2026-08-03): nessuna voce
vuota, nemmeno per i documenti che produce l'applicazione. Una riga in attesa
di un documento è già una richiesta, e non tutti i casi la meritano — la
comunicazione di cessione di fabbricato, per dire, non serve per ogni
inquilino. Generare è quindi un'**azione che si invoca** (l'elenco dei
documenti producibili sta in ``documenti.GENERATORI``, servito
dall'endpoint ``generabili/``), non un posto vuoto che chiede di essere
riempito.
"""
from dataclasses import dataclass

from django.utils import timezone

from properties.models import TenantDocument

#: Un documento è "in scadenza" da qui in avanti (giorni prima della data).
GIORNI_PREAVVISO_SCADENZA = 60

Tipo = TenantDocument.Tipo


@dataclass(frozen=True)
class VoceFascicolo:
    """Definizione di una voce della checklist (indipendente dai file)."""

    tipo: str
    suggerimento: str = ""
    #: Codice del generatore, se il documento lo produce l'applicazione:
    #: serve alla UI per offrire "Rigenera" invece di "Sostituisci".
    generabile: str = ""

    @property
    def tipo_display(self):
        return TenantDocument.Tipo(self.tipo).label


#: Ordine in cui i tipi compaiono nel fascicolo (solo quelli con file).
VOCI = (
    VoceFascicolo(Tipo.CARTA_IDENTITA, suggerimento="fronte e retro"),
    VoceFascicolo(Tipo.CODICE_FISCALE, suggerimento="tessera sanitaria"),
    VoceFascicolo(Tipo.PASSAPORTO, suggerimento="pagina con la foto"),
    VoceFascicolo(Tipo.PERMESSO_SOGGIORNO, suggerimento="o ricevuta di rinnovo"),
    VoceFascicolo(Tipo.CONTRATTO_LAVORO, suggerimento="o busta paga"),
    VoceFascicolo(
        Tipo.RICEVUTA_REGISTRAZIONE,
        suggerimento="ricevuta telematica dell'agenzia",
    ),
    # Il subentro delle utenze non è un documento dell'inquilino: riguarda
    # l'immobile e semmai va fra i documenti della casa.
    VoceFascicolo(
        Tipo.ATTO_SUBENTRO_LOCAZIONE,
        # I suggerimenti descrivono il documento e nient'altro: lo stesso
        # payload alimenta il fascicolo dell'inquilino e quello del
        # proprietario.
        suggerimento="ingresso nel contratto già in corso",
        generabile="atto_subentro_locazione",
    ),
    VoceFascicolo(
        Tipo.CESSIONE_FABBRICATO,
        suggerimento="comunicazione all'autorità (art. 12)",
        generabile="cessione_fabbricato",
    ),
)

#: Tipi che non entrano nella checklist: ogni file è una voce a sé.
TIPI_LIBERI = {Tipo.ALTRO}

STATI_DISPLAY = {
    "ok": "valido",
    "scadenza": "in scadenza",
    "scaduto": "scaduto",
}

#: Ordine di gravità: lo stato di una voce è il peggiore delle sue pagine.
_GRAVITA = {"ok": 0, "scadenza": 1, "scaduto": 2}


def _estensione(doc):
    nome = doc.file.name or ""
    _, _, ext = nome.rpartition(".")
    return ext.lower() if ext else ""


def _stato_documento(doc, oggi):
    """Stato di un singolo file in base alla sua scadenza."""
    if not doc.data_scadenza:
        return "ok"
    if doc.data_scadenza < oggi:
        return "scaduto"
    if (doc.data_scadenza - oggi).days <= GIORNI_PREAVVISO_SCADENZA:
        return "scadenza"
    return "ok"


def _pagina(doc, indice, oggi):
    """Un file del fascicolo, come lo consuma il visore."""
    ext = _estensione(doc)
    return {
        "id": doc.pk,
        "file": doc.file.url,
        "nome_file": (doc.file.name or "").rsplit("/", 1)[-1],
        "estensione": ext,
        "is_pdf": ext == "pdf",
        "descrizione": doc.descrizione,
        "etichetta": doc.descrizione or f"pagina {indice}",
        "data_scadenza": doc.data_scadenza,
        "stato": _stato_documento(doc, oggi),
        "created_at": doc.created_at,
    }


def _voce(definizione, documenti, oggi):
    """Voce della checklist per un tipo, con le sue pagine (mai vuota)."""
    pagine = [_pagina(d, i + 1, oggi) for i, d in enumerate(documenti)]
    stato = max((p["stato"] for p in pagine), key=lambda s: _GRAVITA[s])
    scadenze = [d.data_scadenza for d in documenti if d.data_scadenza]
    data_scadenza = min(scadenze) if scadenze else None
    return {
        "tipo": str(definizione.tipo),
        "tipo_display": definizione.tipo_display,
        "generabile": definizione.generabile or None,
        "suggerimento": definizione.suggerimento,
        "stato": stato,
        "stato_display": STATI_DISPLAY[stato],
        "data_scadenza": data_scadenza,
        "giorni_alla_scadenza": (data_scadenza - oggi).days if data_scadenza else None,
        "caricato_il": timezone.localtime(
            min(d.created_at for d in documenti)
        ).date(),
        "pagine": pagine,
    }


def _altro(doc, oggi):
    """Documento fuori checklist: una voce per file, senza stato di completezza."""
    pagina = _pagina(doc, 1, oggi)
    return {
        "tipo": doc.tipo,
        "tipo_display": doc.get_tipo_display(),
        "generabile": None,
        "suggerimento": "",
        "stato": pagina["stato"],
        "stato_display": STATI_DISPLAY[pagina["stato"]],
        "data_scadenza": doc.data_scadenza,
        "giorni_alla_scadenza": (
            (doc.data_scadenza - oggi).days if doc.data_scadenza else None
        ),
        "caricato_il": timezone.localtime(doc.created_at).date(),
        "titolo": doc.descrizione or doc.get_tipo_display(),
        "pagine": [pagina],
    }


def costruisci_fascicolo(tenant, documenti=None, oggi=None):
    """Fascicolo di un inquilino: checklist per tipo + riepilogo.

    ``documenti`` permette di passare un queryset già filtrato/prefetchato
    (evita una query per inquilino quando si costruiscono più fascicoli).
    """
    # Ora locale, non del server: un documento caricato alle 00:30 a Roma è
    # delle 22:30 del giorno prima in UTC, e mostrerebbe la data sbagliata.
    oggi = oggi or timezone.localdate()
    if documenti is None:
        documenti = tenant.documenti.all()
    per_tipo = {}
    liberi = []
    for doc in sorted(documenti, key=lambda d: (d.created_at, d.pk)):
        if doc.tipo in TIPI_LIBERI:
            liberi.append(doc)
        else:
            per_tipo.setdefault(doc.tipo, []).append(doc)

    voci = []
    for definizione in VOCI:
        docs = per_tipo.get(definizione.tipo, [])
        # Nessun documento è dovuto: il fascicolo elenca ciò che c'è, non
        # ciò che manca. Anche per i documenti che generiamo noi — la
        # generazione è un'azione a parte, non un vuoto da riempire.
        if not docs:
            continue
        voci.append(_voce(definizione, docs, oggi))

    altri = [_altro(d, oggi) for d in liberi]

    conteggi = {stato: 0 for stato in STATI_DISPLAY}
    for voce in voci:
        conteggi[voce["stato"]] += 1

    return {
        "tenant": tenant.pk,
        "tenant_nominativo": tenant.nominativo,
        "oggi": oggi,
        "giorni_preavviso_scadenza": GIORNI_PREAVVISO_SCADENZA,
        "voci": voci,
        "altri": altri,
        "riepilogo": {
            **conteggi,
            "voci": len(voci),
            "da_sistemare": conteggi["scaduto"] + conteggi["scadenza"],
        },
    }
