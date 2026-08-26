"""
Generazione dei documenti legali dell'immobile.

Due documenti, dichiarati come tuple di campi (vedi :mod:`.base`):

* :class:`~.atto_subentro.AttoSubentro` — atto di subentro nel contratto;
* :class:`~.cessione_fabbricato.CessioneFabbricato` — comunicazione ex
  art. 12 D.L. 59/1978.

Il testo non sta qui: arriva da ``DocumentTemplate``, uno per immobile.
Nel package resta solo un **esempio** per ciascun documento
(``esempi/``), da scaricare e adattare quando si aggiunge una proprietà.
Se il modello non è caricato, il documento non si genera e la cosa compare
fra i dati mancanti come tutti gli altri.
"""
from pathlib import Path

from .atto_subentro import AttoSubentro
from .base import (
    DatiInsufficienti,
    Fonti,
    fonti_facsimile,
    raccogli_fonti,
    render_pdf,
)
from .cessione_fabbricato import CessioneFabbricato

ESEMPI = Path(__file__).parent / "esempi"

#: I documenti generabili, per codice.
GENERATORI = {
    documento.chiave: documento
    for documento in (AttoSubentro(), CessioneFabbricato())
}

__all__ = [
    "GENERATORI",
    "AttoSubentro",
    "CessioneFabbricato",
    "DatiInsufficienti",
    "Fonti",
    "anteprima",
    "anteprima_facsimile",
    "esempio",
    "fonti_facsimile",
    "genera_facsimile",
    "genera_pdf",
    "raccogli_fonti",
    "segnaposto",
]


def _documento(codice):
    documento = GENERATORI.get(str(codice))
    if documento is None:
        raise KeyError(codice)
    return documento


def _modello(immobile, codice):
    from properties.models import DocumentTemplate

    return DocumentTemplate.objects.filter(
        property=immobile, codice=codice
    ).first()


def anteprima(tenant, codice, assignment=None, oggi=None) -> dict:
    """Cosa serve e cosa manca per generare un documento.

    Solleva :class:`DatiInsufficienti` se l'inquilino non ha assegnazioni:
    non è un campo da compilare, è un documento che non ha senso.
    """
    documento = _documento(codice)
    fonti = raccogli_fonti(tenant, assignment=assignment, oggi=oggi)
    mancanti = documento.mancanti(fonti)
    if _modello(fonti.property, documento.chiave) is None:
        mancanti.insert(0, _modello_mancante(documento))
    return {
        "documento": str(documento.chiave),
        "documento_display": documento.titolo,
        "tenant": tenant.pk,
        "assignment": fonti.assignment.pk,
        "completo": not mancanti,
        "mancanti": mancanti,
        "riepilogo": documento.riepilogo(fonti),
    }


def _modello_mancante(documento) -> dict:
    return {
        "campo": "modello",
        "etichetta": f"Modello del documento «{documento.titolo}»",
        "fonte": "modello",
        "dove": "Immobile → Modelli documenti",
        "link": f"/p/impostazioni?tab=modelli&codice={documento.chiave}",
        "esterno": False,
    }


def genera_pdf(tenant, codice, assignment=None, oggi=None) -> tuple[bytes, str, str]:
    """``(pdf, nome_file, tipo_documento)``.

    Presuppone che l'anteprima sia completa: chi chiama deve averlo
    verificato (l'API restituisce 400 con l'elenco dei mancanti).
    """
    documento = _documento(codice)
    fonti = raccogli_fonti(tenant, assignment=assignment, oggi=oggi)
    modello = _modello(fonti.property, documento.chiave)
    if modello is None:
        raise DatiInsufficienti(
            f"Nessun modello caricato per «{documento.titolo}»."
        )
    pdf = render_pdf(modello.corpo_html, documento.contesto(fonti))
    return pdf, documento.nome_file(fonti), str(documento.tipo_documento)


def segnaposto(codice) -> list[dict]:
    """Segnaposto disponibili in un modello, per chi lo scrive."""
    return _documento(codice).segnaposto()


def esempio(codice) -> str:
    """HTML di esempio versionato nel repository, da adattare."""
    documento = _documento(codice)
    return (ESEMPI / f"{documento.chiave}.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fac-simile
# ---------------------------------------------------------------------------
#
# Lo stesso documento senza nessuna persona e senza nessuna stanza: si manda
# a chi deve ancora decidere, come anteprima di cosa si firmerà. Non è la
# copia oscurata di un atto già firmato — quello nominerebbe qualcuno — ma
# lo stesso modello compilato con OMISSIS al posto delle parti che cambiano
# da un caso all'altro. Per questo un fac-simile solo vale per tutti i
# candidati e per tutte le stanze.


def anteprima_facsimile(immobile, codice, contract=None, oggi=None) -> dict:
    """Cosa manca per generare il fac-simile di un documento."""
    documento = _documento(codice)
    fonti = fonti_facsimile(immobile, contract=contract, oggi=oggi)
    mancanti = documento.mancanti(fonti)
    if fonti.contract is None:
        mancanti.insert(0, _contratto_mancante())
    if _modello(immobile, documento.chiave) is None:
        mancanti.insert(0, _modello_mancante(documento))
    return {
        "documento": str(documento.chiave),
        "documento_display": documento.titolo,
        "completo": not mancanti,
        "mancanti": mancanti,
    }


def _contratto_mancante() -> dict:
    return {
        "campo": "contract",
        "etichetta": "Contratto dell'immobile",
        "fonte": "contract",
        "dove": "Immobile → Contratti",
        "link": "/p/impostazioni?tab=contratti",
        "esterno": False,
    }


def genera_facsimile(immobile, codice, contract=None, oggi=None) -> tuple[bytes, str]:
    """``(pdf, nome_file)`` del fac-simile.

    Presuppone che l'anteprima sia completa, come ``genera_pdf``.
    """
    from django.utils.text import slugify

    documento = _documento(codice)
    fonti = fonti_facsimile(immobile, contract=contract, oggi=oggi)
    modello = _modello(immobile, documento.chiave)
    if modello is None:
        raise DatiInsufficienti(
            f"Nessun modello caricato per «{documento.titolo}»."
        )
    if fonti.contract is None:
        raise DatiInsufficienti(
            "L'immobile non ha un contratto: il fac-simile di un atto di "
            "subentro ne cita gli estremi di registrazione."
        )
    pdf = render_pdf(modello.corpo_html, documento.contesto(fonti))
    casa = slugify(immobile.nome) or "immobile"
    nome = f"facsimile-{documento.prefisso_file}-{casa}-{fonti.oggi:%Y%m%d}.pdf"
    return pdf, nome
