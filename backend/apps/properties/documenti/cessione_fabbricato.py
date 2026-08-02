"""
Comunicazione di cessione di fabbricato (art. 12 D.L. 21.3.1978 n. 59).

Chi cede la disponibilità di un fabbricato a un cittadino deve comunicarlo
all'autorità. Il modulo è una griglia di caselle: cedente, cessionario e
fabbricato, ciascuno con i propri dati anagrafici o catastali.

Il cedente è **una persona sola** (``Property.owner_firmatario``), non
l'insieme dei comproprietari: il modulo dice "Il Signor" e prevede una
firma sola.
"""
from properties.models import DocumentTemplate, TenantDocument

from .base import Campo, Documento, Fonti


def _cedente(fonti: Fonti):
    return fonti.firmatario


def _campi_persona(prefisso, etichetta, fonte, estrai, richiede=None, oggetto=None):
    """Le caselle anagrafiche comuni a cedente e cessionario.

    ``richiede`` evita di elencare otto dati mancanti quando a mancare è la
    persona stessa: in quel caso lo dice una riga sola.
    """
    campi = (
        ("cognome", "Cognome", "cognome"),
        ("nome", "Nome", "nome"),
        ("data_nascita", "Data di nascita", "data_nascita"),
        ("comune_nascita", "Comune di nascita", "comune_nascita"),
        ("provincia_nascita", "Provincia o nazione estera di nascita",
         "provincia_nascita"),
        ("comune_residenza", "Comune di residenza", "residenza_comune"),
        ("via", "Via e numero civico", "residenza_via"),
        ("telefono", "Recapito telefonico", "telefono"),
    )
    return tuple(
        Campo(
            f"{prefisso}_{suffisso}",
            f"{testo} ({etichetta})",
            fonte,
            lambda f, a=attributo: getattr(estrai(f), a),
            campo_db=attributo,
            richiede=richiede,
            oggetto=oggetto,
        )
        for suffisso, testo, attributo in campi
    )


class CessioneFabbricato(Documento):
    chiave = DocumentTemplate.Codice.CESSIONE_FABBRICATO
    titolo = "Comunicazione di cessione di fabbricato"
    tipo_documento = TenantDocument.Tipo.CESSIONE_FABBRICATO
    prefisso_file = "cessione-fabbricato"

    campi = (
        # ── Cedente: il proprietario che firma ──────────────────────────
        Campo(
            "", "Proprietario che firma come cedente", "property",
            lambda f: f.firmatario, campo_db="owner_firmatario",
        ),
        *_campi_persona(
            "cedente", "cedente", "owner", _cedente,
            richiede=lambda f: f.firmatario is not None,
            oggetto=_cedente,
        ),
        # ── Cessione ────────────────────────────────────────────────────
        Campo(
            "data_cessione", "Data della cessione", "assignment",
            lambda f: f.assignment.valid_from,
        ),
        Campo(
            "motivo_cessione", "Motivo della cessione", "property",
            lambda f: "locazione", derivato=True,
        ),
        Campo(
            "uso", "Uso", "property", lambda f: "abitazione", derivato=True,
        ),
        # ── Cessionario: l'inquilino ────────────────────────────────────
        *_campi_persona("cessionario", "cessionario", "tenant", lambda f: f.tenant),
        Campo(
            "cessionario_cittadinanza", "Cittadinanza (cessionario)", "tenant",
            lambda f: f.tenant.cittadinanza, campo_db="cittadinanza",
        ),
        Campo(
            "cessionario_documento_tipo", "Tipo di documento (cessionario)",
            "tenant", lambda f: f.tenant.get_documento_tipo_display(),
            campo_db="documento_tipo",
        ),
        Campo(
            "cessionario_documento_numero", "Numero del documento (cessionario)",
            "tenant", lambda f: f.tenant.documento_numero,
            campo_db="documento_numero",
        ),
        Campo(
            "cessionario_documento_autorita",
            "Autorità che ha rilasciato il documento (cessionario)", "tenant",
            lambda f: f.tenant.documento_autorita, campo_db="documento_autorita",
        ),
        Campo(
            "cessionario_documento_rilascio", "Data di rilascio (cessionario)",
            "tenant", lambda f: f.tenant.documento_data_rilascio,
            campo_db="documento_data_rilascio",
        ),
        # ── Fabbricato ──────────────────────────────────────────────────
        Campo(
            "fabbricato_adibito_a", "Già adibito a", "property",
            lambda f: "abitazione", derivato=True,
        ),
        Campo(
            "fabbricato_comune", "Comune del fabbricato", "property",
            lambda f: f.property.comune, campo_db="comune",
        ),
        Campo(
            "fabbricato_provincia", "Provincia del fabbricato", "property",
            lambda f: f.property.provincia, campo_db="provincia",
        ),
        Campo(
            "fabbricato_via", "Via/piazza del fabbricato", "property",
            lambda f: f.property.via, campo_db="via",
        ),
        Campo(
            "fabbricato_civico", "Numero civico", "property",
            lambda f: f.property.civico, campo_db="civico",
        ),
        Campo(
            "fabbricato_cap", "CAP", "property",
            lambda f: f.property.cap, campo_db="cap",
        ),
        Campo(
            "fabbricato_piano", "Piano", "property",
            lambda f: f.property.piano, campo_db="piano",
        ),
        # Scala, interno, accessori e ingressi restano spesso vuoti in un
        # appartamento singolo: caselle da lasciare in bianco, non dati
        # mancanti.
        Campo(
            "fabbricato_scala", "Scala", "property",
            lambda f: f.property.scala, campo_db="scala", obbligatorio=False,
        ),
        Campo(
            "fabbricato_interno", "Interno", "property",
            lambda f: f.property.interno, campo_db="interno", obbligatorio=False,
        ),
        Campo(
            "fabbricato_vani", "Vani", "property",
            lambda f: f.property.vani, campo_db="vani",
        ),
        Campo(
            "fabbricato_accessori", "Accessori", "property",
            lambda f: f.property.accessori, campo_db="accessori",
            obbligatorio=False,
        ),
        Campo(
            "fabbricato_ingressi", "Ingressi", "property",
            lambda f: f.property.ingressi, campo_db="ingressi",
            obbligatorio=False,
        ),
        Campo(
            "data_compilazione", "Data di compilazione del modulo", "property",
            lambda f: f.oggi, derivato=True,
        ),
    )
