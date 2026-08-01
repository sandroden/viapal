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
``mancante``
    documento richiesto e mai caricato.
``attesa``
    documento a carico della proprietà (l'atto di subentro lo carica il
    proprietario, l'inquilino non deve fare nulla).

Le voci facoltative non caricate non compaiono nel fascicolo: non si può
dedurre chi ha bisogno di un permesso di soggiorno, e mostrarle come
"mancanti" sarebbe un allarme falso. Restano comunque caricabili scegliendo
il tipo dal modulo di caricamento.
"""
import datetime
from dataclasses import dataclass

from properties.models import TenantDocument

#: Un documento è "in scadenza" da qui in avanti (giorni prima della data).
GIORNI_PREAVVISO_SCADENZA = 60

Tipo = TenantDocument.Tipo


@dataclass(frozen=True)
class VoceAttesa:
    """Definizione di una voce della checklist (indipendente dai file)."""

    tipo: str
    richiesto: bool = False
    a_carico_proprieta: bool = False
    suggerimento: str = ""

    @property
    def tipo_display(self):
        return TenantDocument.Tipo(self.tipo).label


#: Voci della checklist, nell'ordine in cui compaiono nel fascicolo.
VOCI = (
    VoceAttesa(Tipo.CARTA_IDENTITA, richiesto=True, suggerimento="fronte e retro"),
    VoceAttesa(Tipo.CODICE_FISCALE, richiesto=True, suggerimento="tessera sanitaria"),
    VoceAttesa(Tipo.PASSAPORTO, suggerimento="pagina con la foto"),
    VoceAttesa(Tipo.PERMESSO_SOGGIORNO, suggerimento="o ricevuta di rinnovo"),
    VoceAttesa(Tipo.CONTRATTO_LAVORO, richiesto=True, suggerimento="o busta paga"),
    VoceAttesa(Tipo.RICEVUTA_SUBENTRO, suggerimento="ricevuta del subentro utenze"),
    VoceAttesa(
        Tipo.ATTO_SUBENTRO,
        a_carico_proprieta=True,
        suggerimento="utenze intestate all'inquilino",
    ),
)

#: Tipi che non entrano nella checklist: ogni file è una voce a sé.
TIPI_LIBERI = {Tipo.ALTRO}

STATI_DISPLAY = {
    "ok": "valido",
    "scadenza": "in scadenza",
    "scaduto": "scaduto",
    "mancante": "da caricare",
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
        stato = "attesa" if definizione.a_carico_proprieta else "mancante"
    else:
        stato = max((p["stato"] for p in pagine), key=lambda s: _GRAVITA[s])
    scadenze = [d.data_scadenza for d in documenti if d.data_scadenza]
    data_scadenza = min(scadenze) if scadenze else None
    return {
        "tipo": str(definizione.tipo),
        "tipo_display": definizione.tipo_display,
        "richiesto": definizione.richiesto,
        "a_carico_proprieta": definizione.a_carico_proprieta,
        "suggerimento": definizione.suggerimento,
        "stato": stato,
        "stato_display": STATI_DISPLAY[stato],
        "data_scadenza": data_scadenza,
        "giorni_alla_scadenza": (data_scadenza - oggi).days if data_scadenza else None,
        "caricato_il": min(d.created_at for d in documenti).date() if documenti else None,
        "pagine": pagine,
    }


def _altro(doc, oggi):
    """Documento fuori checklist: una voce per file, senza stato di completezza."""
    pagina = _pagina(doc, 1, oggi)
    return {
        "tipo": doc.tipo,
        "tipo_display": doc.get_tipo_display(),
        "richiesto": False,
        "a_carico_proprieta": False,
        "suggerimento": "",
        "stato": pagina["stato"],
        "stato_display": STATI_DISPLAY[pagina["stato"]],
        "data_scadenza": doc.data_scadenza,
        "giorni_alla_scadenza": (
            (doc.data_scadenza - oggi).days if doc.data_scadenza else None
        ),
        "caricato_il": doc.created_at.date(),
        "titolo": doc.descrizione or doc.get_tipo_display(),
        "pagine": [pagina],
    }


def costruisci_fascicolo(tenant, documenti=None, oggi=None):
    """Fascicolo di un inquilino: checklist per tipo + riepilogo.

    ``documenti`` permette di passare un queryset già filtrato/prefetchato
    (evita una query per inquilino quando si costruiscono più fascicoli).
    """
    oggi = oggi or datetime.date.today()
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
        # Facoltativo e mai caricato: non è una mancanza, non lo mostriamo.
        if not docs and not definizione.richiesto and not definizione.a_carico_proprieta:
            continue
        voci.append(_voce(definizione, docs, oggi))

    altri = [_altro(d, oggi) for d in liberi]

    conteggi = {stato: 0 for stato in STATI_DISPLAY}
    for voce in voci:
        conteggi[voce["stato"]] += 1
    completabili = [v for v in voci if not v["a_carico_proprieta"]]
    a_posto = sum(1 for v in completabili if v["stato"] in ("ok", "scadenza"))

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
            "completezza": (
                round(100 * a_posto / len(completabili)) if completabili else 100
            ),
        },
    }
