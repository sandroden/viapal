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
``attesa``
    documento a carico della proprietà (l'atto di subentro lo carica il
    proprietario, l'inquilino non deve fare nulla).

**Nessun documento è obbligatorio**: non esiste uno stato "mancante" e il
fascicolo non conta quanto manca. I documenti sono copie di cortesia, e dopo
la verifica possono anche essere cancellati (meno dati conservati, meno
rischio). Una voce senza file compare solo quando è a carico della proprietà.

Corollario: una voce a carico della proprietà che *non si applica* a quel
rapporto non deve comparire affatto. L'atto di subentro nel contratto ha
senso solo per chi è subentrato a qualcuno; per il primo occupante di una
stanza resterebbe in ``attesa`` per sempre, aspettando un documento che non
esisterà mai. Per questo :func:`costruisci_fascicolo` conosce anche
l'assegnazione dell'inquilino.
"""
from collections.abc import Callable
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
    a_carico_proprieta: bool = False
    suggerimento: str = ""
    #: Codice del generatore, se il documento lo produce l'applicazione.
    generabile: str = ""
    #: Se presente e falso per quell'assegnazione, la voce non compare.
    applicabile: Callable | None = None

    @property
    def tipo_display(self):
        return TenantDocument.Tipo(self.tipo).label


def _e_un_subentro(assignment) -> bool:
    return assignment is not None and assignment.subentra_a_id is not None


#: Voci della checklist, nell'ordine in cui compaiono nel fascicolo.
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
    VoceFascicolo(
        Tipo.ATTO_SUBENTRO,
        a_carico_proprieta=True,
        suggerimento="utenze intestate all'inquilino",
    ),
    VoceFascicolo(
        Tipo.ATTO_SUBENTRO_LOCAZIONE,
        a_carico_proprieta=True,
        # I suggerimenti descrivono il documento e nient'altro: lo stesso
        # payload alimenta il fascicolo dell'inquilino, a cui un "lo generi
        # tu" non direbbe nulla. L'invito ad agire sta nella UI del
        # proprietario, che sa di essere tale.
        suggerimento="ingresso nel contratto già in corso",
        generabile="atto_subentro_locazione",
        # Solo per chi è subentrato a qualcuno: al primo occupante di una
        # stanza questo atto non serve, e la voce non deve comparire.
        applicabile=_e_un_subentro,
    ),
    VoceFascicolo(
        Tipo.CESSIONE_FABBRICATO,
        a_carico_proprieta=True,
        suggerimento="comunicazione all'autorità (art. 12)",
        generabile="cessione_fabbricato",
        # Incondizionata: l'art. 12 obbliga il cedente per ogni nuovo
        # occupante, non solo per i subentri.
    ),
)

#: Tipi che non entrano nella checklist: ogni file è una voce a sé.
TIPI_LIBERI = {Tipo.ALTRO}

STATI_DISPLAY = {
    "ok": "valido",
    "scadenza": "in scadenza",
    "scaduto": "scaduto",
    "attesa": "lo carica la proprietà",
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
    """Voce della checklist per un tipo, con le sue pagine."""
    pagine = [_pagina(d, i + 1, oggi) for i, d in enumerate(documenti)]
    if not pagine:
        stato = "attesa"  # senza file esistono solo le voci a carico nostro
    else:
        stato = max((p["stato"] for p in pagine), key=lambda s: _GRAVITA[s])
    scadenze = [d.data_scadenza for d in documenti if d.data_scadenza]
    data_scadenza = min(scadenze) if scadenze else None
    return {
        "tipo": str(definizione.tipo),
        "tipo_display": definizione.tipo_display,
        "a_carico_proprieta": definizione.a_carico_proprieta,
        "generabile": definizione.generabile or None,
        "suggerimento": definizione.suggerimento,
        "stato": stato,
        "stato_display": STATI_DISPLAY[stato],
        "data_scadenza": data_scadenza,
        "giorni_alla_scadenza": (data_scadenza - oggi).days if data_scadenza else None,
        "caricato_il": (
            timezone.localtime(min(d.created_at for d in documenti)).date()
            if documenti
            else None
        ),
        "pagine": pagine,
    }


def _altro(doc, oggi):
    """Documento fuori checklist: una voce per file, senza stato di completezza."""
    pagina = _pagina(doc, 1, oggi)
    return {
        "tipo": doc.tipo,
        "tipo_display": doc.get_tipo_display(),
        "a_carico_proprieta": False,
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


def costruisci_fascicolo(tenant, documenti=None, oggi=None, assignment=None):
    """Fascicolo di un inquilino: checklist per tipo + riepilogo.

    ``documenti`` permette di passare un queryset già filtrato/prefetchato
    (evita una query per inquilino quando si costruiscono più fascicoli).

    ``assignment`` (default: l'ultima assegnazione dell'inquilino) serve
    alle voci condizionate: senza sapere se c'è stato un subentro non si
    può dire se l'atto di subentro nel contratto vada preteso o ignorato.
    """
    # Ora locale, non del server: un documento caricato alle 00:30 a Roma è
    # delle 22:30 del giorno prima in UTC, e mostrerebbe la data sbagliata.
    oggi = oggi or timezone.localdate()
    if documenti is None:
        documenti = tenant.documenti.all()
    if assignment is None:
        assignment = tenant.assignments.order_by("-valid_from").first()
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
        # Nessun documento è dovuto: una voce senza file compare solo se la
        # deve caricare la proprietà...
        if not docs and not definizione.a_carico_proprieta:
            continue
        # ...e solo se quel documento ha senso per questo rapporto. Un file
        # già caricato invece si mostra sempre: esiste, va visto.
        if (
            not docs
            and definizione.applicabile is not None
            and not definizione.applicabile(assignment)
        ):
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
