"""
Test del modello ``DocumentTemplate``.

Il testo dei documenti generati è un dato dell'immobile, non codice: qui si
verifica l'unicità per immobile e l'indipendenza fra immobili diversi.
"""
import pytest
from django.db import IntegrityError, transaction

from properties.models import DocumentTemplate

pytestmark = pytest.mark.django_db

Codice = DocumentTemplate.Codice


def _modello(immobile, codice=Codice.ATTO_SUBENTRO_LOCAZIONE, corpo="<p>ciao</p>"):
    return DocumentTemplate.objects.create(
        property=immobile, codice=codice, corpo_html=corpo
    )


def test_un_solo_modello_per_codice_e_immobile(immobile):
    _modello(immobile)
    with transaction.atomic(), pytest.raises(IntegrityError):
        _modello(immobile)


def test_due_immobili_hanno_modelli_indipendenti(immobile, immobile2):
    a = _modello(immobile, corpo="<p>Palestrina</p>")
    b = _modello(immobile2, corpo="<p>Altrove</p>")
    assert a.pk != b.pk
    assert immobile.document_templates.get().corpo_html == "<p>Palestrina</p>"
    assert immobile2.document_templates.get().corpo_html == "<p>Altrove</p>"


def test_codici_diversi_convivono(immobile):
    _modello(immobile, Codice.ATTO_SUBENTRO_LOCAZIONE)
    _modello(immobile, Codice.CESSIONE_FABBRICATO)
    assert immobile.document_templates.count() == 2


def test_str_usa_il_nome_o_l_etichetta_del_codice(immobile):
    modello = _modello(immobile)
    assert str(modello) == "Atto di subentro nel contratto"
    modello.nome = "Atto 2026"
    assert str(modello) == "Atto 2026"
