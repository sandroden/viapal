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
from .base import DatiInsufficienti, Fonti, raccogli_fonti, render_pdf
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
    "esempio",
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
