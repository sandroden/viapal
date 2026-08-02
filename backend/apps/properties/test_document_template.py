"""
Test del modello ``DocumentTemplate``.

Il testo dei documenti generati è un dato dell'immobile, non codice: qui si
verifica l'unicità per immobile e l'indipendenza fra immobili diversi.
"""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
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


class TestCaricaModelliDocumenti:
    """Il comando che carica gli esempi sulla prima configurazione."""

    def _carica(self, immobile, **opzioni):
        call_command("carica_modelli_documenti", property=str(immobile.pk), **opzioni)

    def test_carica_tutti_i_documenti(self, immobile):
        self._carica(immobile)
        assert set(immobile.document_templates.values_list("codice", flat=True)) == {
            Codice.ATTO_SUBENTRO_LOCAZIONE,
            Codice.CESSIONE_FABBRICATO,
        }
        assert immobile.document_templates.first().corpo_html.strip()

    def test_non_sovrascrive_il_modello_adattato(self, immobile):
        _modello(immobile, corpo="<p>versione di casa</p>")
        self._carica(immobile)
        modello = immobile.document_templates.get(
            codice=Codice.ATTO_SUBENTRO_LOCAZIONE
        )
        assert modello.corpo_html == "<p>versione di casa</p>"

    def test_force_sovrascrive(self, immobile):
        _modello(immobile, corpo="<p>versione di casa</p>")
        self._carica(immobile, force=True)
        modello = immobile.document_templates.get(
            codice=Codice.ATTO_SUBENTRO_LOCAZIONE
        )
        assert modello.corpo_html != "<p>versione di casa</p>"

    def test_dry_run_non_scrive(self, immobile):
        self._carica(immobile, dry_run=True)
        assert immobile.document_templates.count() == 0

    def test_solo_il_codice_richiesto(self, immobile):
        self._carica(immobile, codice=[Codice.CESSIONE_FABBRICATO])
        assert immobile.document_templates.get().codice == Codice.CESSIONE_FABBRICATO

    def test_immobile_sconosciuto_solleva(self, immobile):
        with pytest.raises(CommandError):
            call_command("carica_modelli_documenti", property="non-esiste")
