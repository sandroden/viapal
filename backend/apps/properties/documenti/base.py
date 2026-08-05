"""
Infrastruttura comune ai documenti generati.

Un documento è dichiarato come una tupla di :class:`Campo`: da quella lista
discendono sia il contesto passato al modello HTML sia l'elenco dei dati
mancanti. Nessuna delle due viene scritta a mano, così non possono
divergere: se un campo si aggiunge al documento, compare da solo fra i
segnaposto disponibili e fra i dati da compilare.

Il modello HTML arriva dal database (``DocumentTemplate``, uno per
immobile) e la sostituzione dei segnaposto è una ``str.replace``: non è un
template engine, quindi un HTML caricato da un utente non può leggere
variabili, chiamare filtri né includere altri file. Per lo stesso motivo
WeasyPrint gira con un ``url_fetcher`` che rifiuta qualunque risorsa
esterna: senza, un ``<img src="file:///...">`` finirebbe dentro il PDF.
"""
import datetime
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

MESI = (
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
)


# ---------------------------------------------------------------------------
# Formattazione (in Python, come già fa billing.calc._email)
# ---------------------------------------------------------------------------


def data_it(valore) -> str:
    """``datetime.date`` → ``22/07/2026``. Stringa vuota se assente."""
    return f"{valore:%d/%m/%Y}" if valore else ""


def data_estesa(valore) -> str:
    """``datetime.date`` → ``22 luglio 2026``."""
    if not valore:
        return ""
    return f"{valore.day} {MESI[valore.month - 1]} {valore.year}"


def eur(valore) -> str:
    """Importo → ``1.234,56`` (separatore migliaia italiano)."""
    if valore is None:
        return ""
    intero, _, decimali = f"{Decimal(valore):,.2f}".partition(".")
    return f"{intero.replace(',', '.')},{decimali}"


def nome_cognome(persona) -> str:
    """``Cognome Nome``, oppure stringa vuota se manca uno dei due.

    Diverso da ``persona.nome_completo``, che ripiega su ``nominativo``:
    qui serve sapere se il dato c'è davvero, perché un modulo ufficiale ha
    due caselle separate e non accetta "un nome così com'è".
    """
    if not (persona.cognome or "").strip() or not (persona.nome or "").strip():
        return ""
    return f"{persona.cognome} {persona.nome}".strip()


def luogo_nascita(persona) -> str:
    """``Monza (MB)`` oppure ``El Oulfa (Marocco)``."""
    comune = (persona.comune_nascita or "").strip()
    provincia = (persona.provincia_nascita or "").strip()
    if comune and provincia:
        return f"{comune} ({provincia})"
    return comune or provincia


def residenza(persona) -> str:
    """``Monza (MB), Via Palestrina 20``."""
    comune = (persona.residenza_comune or "").strip()
    provincia = (persona.residenza_provincia or "").strip()
    via = (persona.residenza_via or "").strip()
    localita = f"{comune} ({provincia})" if comune and provincia else comune or provincia
    return ", ".join(p for p in (localita, via) if p)


def descrivi_persona(persona) -> str:
    """Riga anagrafica per esteso, come la vuole un atto:

    ``Rossi Mario, nato/a a Monza (MB) il 12/03/1990, residente a Monza (MB),
    Via Palestrina 20, C.F. RSSMRA90C12F704X``

    "nato/a" e non "nato": il sesso non è un dato che raccogliamo, e
    scriverlo al maschile su un atto che nomina anche delle donne è
    semplicemente sbagliato.
    """
    pezzi = [persona.nome_completo]
    if nato := luogo_nascita(persona):
        pezzi.append(f"nato/a a {nato} il {data_it(persona.data_nascita)}")
    if dove := residenza(persona):
        pezzi.append(f"residente a {dove}")
    if persona.codice_fiscale:
        pezzi.append(f"C.F. {persona.codice_fiscale}")
    return ", ".join(pezzi)


# ---------------------------------------------------------------------------
# Fonti
# ---------------------------------------------------------------------------


@dataclass
class Fonti:
    """Tutto ciò che i documenti leggono, risolto una volta sola."""

    tenant: Any
    assignment: Any
    property: Any
    contract: Any = None
    uscente: Any = None
    uscente_assignment: Any = None
    comproprietari: list = field(default_factory=list)
    firmatario: Any = None
    oneri_accessori: Decimal | None = None
    deposito: Decimal | None = None
    rate_deposito: int = 0
    oggi: datetime.date | None = None

    @property
    def canone(self):
        return self.assignment.canone_mensile

    @property
    def stanza(self):
        return self.assignment.room


class DatiInsufficienti(Exception):
    """Il documento non è nemmeno impostabile (manca l'assegnazione)."""


def raccogli_fonti(tenant, assignment=None, oggi=None) -> Fonti:
    """Risolve le fonti di un inquilino per il documento da generare.

    Solleva :class:`DatiInsufficienti` se l'inquilino non ha assegnazioni:
    senza stanza e senza date non c'è un documento da impostare, e non è
    un "campo mancante" da compilare.
    """
    from billing.models import Receivable
    from properties.models import quote_attive_at

    oggi = oggi or datetime.date.today()
    if assignment is None:
        assignment = tenant.assignments.order_by("-valid_from").first()
    if assignment is None:
        raise DatiInsufficienti("L'inquilino non ha assegnazioni di stanza.")

    immobile = assignment.room.property
    alla_data = assignment.valid_from
    contract = immobile.contratto_attivo(alla_data)

    uscente_assignment = assignment.subentra_a
    uscente = uscente_assignment.tenant if uscente_assignment else None

    quote = quote_attive_at(immobile, alla_data)
    comproprietari = sorted(quote, key=lambda o: o.nominativo)

    depositi = Receivable.objects.filter(
        assignment__tenant=tenant,
        causale=Receivable.Causale.DEPOSITO,
        importo_dovuto__gt=0,
    )
    totale_deposito = sum((r.importo_dovuto for r in depositi), Decimal("0"))

    return Fonti(
        tenant=tenant,
        assignment=assignment,
        property=immobile,
        contract=contract,
        uscente=uscente,
        uscente_assignment=uscente_assignment,
        comproprietari=comproprietari,
        firmatario=immobile.owner_firmatario,
        oneri_accessori=_quota_condominio(assignment, alla_data),
        deposito=totale_deposito or tenant.deposito_versato,
        rate_deposito=depositi.count(),
        oggi=oggi,
    )


def _quota_condominio(assignment, alla_data):
    """Quota mensile di oneri accessori in vigore a una data.

    Delega alla stessa funzione che genera gli addebiti d'affitto: il
    documento deve dichiarare la cifra che l'inquilino paga davvero. Il
    criterio è per **immobile**, non per contratto attivo — con contratti
    che si accavallano (o una decorrenza spostata) le due letture
    divergerebbero, e a divergere sarebbe l'atto.
    """
    from billing.calc.rent import _quota_condominio_per

    quota = _quota_condominio_per(assignment, alla_data)
    return quota or None


# ---------------------------------------------------------------------------
# Campi
# ---------------------------------------------------------------------------

#: Dove si compila ogni fonte, e come ci si arriva.
DOVE = {
    "tenant": "Scheda inquilino → Profilo",
    "uscente": "Scheda dell'inquilino uscente → Profilo",
    "property": "Immobile → Dati",
    "contract": "Immobile → Contratti",
    "assignment": "Assegnazione stanza (admin)",
    "deposito": "Deposito dell'inquilino (admin)",
    "owner": "Profilo proprietario (admin)",
    "modello": "Immobile → Modelli documenti",
}

#: Fonti che si compilano solo dall'admin Django, fuori dalla PWA.
FONTI_ESTERNE = {"assignment", "deposito", "owner"}


@dataclass(frozen=True)
class Campo:
    """Un segnaposto del documento e la sua provenienza."""

    chiave: str
    etichetta: str
    fonte: str
    valore: Callable[[Fonti], Any]
    campo_db: str = ""
    #: Se ``False`` la sua assenza non blocca la generazione (es. "scala").
    obbligatorio: bool = True
    #: Composto da altri campi già controllati: non entra fra i mancanti.
    derivato: bool = False
    #: Riferimento specifico per il link (es. il singolo comproprietario).
    oggetto: Callable[[Fonti], Any] | None = None
    #: Se presente e falso, il campo non si applica a questo caso e la sua
    #: assenza non è un dato mancante (es. l'uscente quando non c'è subentro).
    richiede: Callable[[Fonti], bool] | None = None

    def leggi(self, fonti: Fonti):
        try:
            return self.valore(fonti)
        except (AttributeError, TypeError, IndexError):
            return None


def _vuoto(valore) -> bool:
    if valore is None:
        return True
    if isinstance(valore, str):
        return not valore.strip()
    if isinstance(valore, (list, tuple, dict)):
        return not valore
    return False


def link_per(campo: Campo, fonti: Fonti) -> str:
    """URL della pagina in cui si compila il campo."""
    oggetto = campo.oggetto(fonti) if campo.oggetto else None
    ancora = f"&campo={campo.campo_db}" if campo.campo_db else ""
    if campo.fonte == "tenant":
        return f"/p/inquilini/{fonti.tenant.pk}?tab=profilo&modifica=anagrafica{ancora}"
    if campo.fonte == "uscente":
        return f"/p/inquilini/{fonti.uscente.pk}?tab=profilo&modifica=anagrafica{ancora}"
    if campo.fonte == "property":
        return f"/p/impostazioni?tab=dati{ancora}"
    if campo.fonte == "contract":
        contratto = f"&contratto={fonti.contract.pk}" if fonti.contract else ""
        return f"/p/impostazioni?tab=contratti{contratto}{ancora}"
    if campo.fonte == "owner":
        if oggetto is None:
            return "/admin/properties/ownerprofile/"
        return f"/admin/properties/ownerprofile/{oggetto.pk}/change/"
    if campo.fonte == "assignment":
        return f"/admin/properties/roomassignment/{fonti.assignment.pk}/change/"
    if campo.fonte == "deposito":
        # Il deposito non sta nel form anagrafica: nasce da
        # ``deposito_versato`` o dalle rate della prima assegnazione, e si
        # sistema dalla scheda admin dell'inquilino.
        return f"/admin/properties/tenantprofile/{fonti.tenant.pk}/change/"
    return "/p/impostazioni?tab=modelli"


# ---------------------------------------------------------------------------
# Documento
# ---------------------------------------------------------------------------


class Documento:
    """Base dei documenti generabili."""

    #: Corrisponde a ``DocumentTemplate.Codice``.
    chiave: str = ""
    titolo: str = ""
    #: Corrisponde a ``TenantDocument.Tipo``.
    tipo_documento: str = ""
    #: Prefisso del nome file generato.
    prefisso_file: str = "documento"
    campi: tuple[Campo, ...] = ()

    def campi_extra(self, fonti: Fonti) -> tuple[Campo, ...]:
        """Campi che dipendono dai dati (es. uno per comproprietario)."""
        return ()

    def tutti_i_campi(self, fonti: Fonti) -> tuple[Campo, ...]:
        return (*self.campi, *self.campi_extra(fonti))

    def mancanti(self, fonti: Fonti) -> list[dict]:
        """Campi obbligatori non compilati, con il posto dove compilarli."""
        fuori = []
        for campo in self.tutti_i_campi(fonti):
            if campo.derivato or not campo.obbligatorio:
                continue
            if campo.richiede is not None and not campo.richiede(fonti):
                continue
            if not _vuoto(campo.leggi(fonti)):
                continue
            fuori.append(
                {
                    "campo": campo.chiave,
                    "etichetta": campo.etichetta,
                    "fonte": campo.fonte,
                    "dove": DOVE.get(campo.fonte, ""),
                    "link": link_per(campo, fonti),
                    "esterno": campo.fonte in FONTI_ESTERNE,
                }
            )
        return fuori

    def contesto(self, fonti: Fonti) -> dict[str, str]:
        """Valori dei segnaposto, già formattati come stringhe."""
        return {
            campo.chiave: _stringa(campo.leggi(fonti))
            for campo in self.tutti_i_campi(fonti)
            if campo.chiave
        }

    def segnaposto(self) -> list[dict]:
        """Elenco dei segnaposto disponibili, per chi scrive il modello.

        ``derivato`` distingue i segnaposto *composti* da altri campi (una
        riga anagrafica intera, il blocco firme) da quelli semplicemente
        facoltativi: i primi non mancano mai, si compilano da soli.
        """
        return [
            {
                "chiave": campo.chiave,
                "etichetta": campo.etichetta,
                "fonte": campo.fonte,
                "obbligatorio": campo.obbligatorio,
                "derivato": campo.derivato,
            }
            for campo in self.campi
            if campo.chiave
        ]

    def riepilogo(self, fonti: Fonti) -> dict:
        """I dati che l'utente vuole rileggere prima di premere Genera.

        Dichiarato da ciascun documento e non qui: il riepilogo deve mostrare
        quello che finisce *in quel* documento. Una base che elencasse canoni
        e depositi li farebbe comparire anche dove non c'entrano.
        """
        return {}

    def nome_file(self, fonti: Fonti) -> str:
        from django.utils.text import slugify

        chi = slugify(fonti.tenant.nominativo) or "inquilino"
        return f"{self.prefisso_file}-{chi}-{fonti.oggi:%Y%m%d}.pdf"


def _stringa(valore) -> str:
    if valore is None:
        return ""
    if isinstance(valore, datetime.date):
        return data_it(valore)
    if isinstance(valore, Decimal):
        return eur(valore)
    return str(valore)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def applica(modello: str, contesto: dict) -> str:
    """Sostituisce i segnaposto ``{{chiave}}``.

    Stessa meccanica di ``billing.calc._email._applica``: nessun engine, e
    quindi nessuna superficie d'attacco su HTML caricato da un utente.
    """
    fuori = modello
    for chiave, valore in contesto.items():
        fuori = fuori.replace("{{" + chiave + "}}", str(valore))
    return fuori


def _nessuna_risorsa_esterna(url: str):
    """``url_fetcher`` di WeasyPrint che rifiuta tutto tranne i data URI.

    Il modello HTML è caricato da un utente: senza questo, un
    ``<img src="file:///etc/passwd">`` verrebbe letto dal server e
    incorporato nel PDF.
    """
    from weasyprint.urls import default_url_fetcher

    if url.startswith("data:"):
        return default_url_fetcher(url)
    raise ValueError(f"Risorsa esterna non consentita nel modello: {url}")


def render_pdf(modello: str, contesto: dict) -> bytes:
    """HTML del modello + contesto → PDF."""
    from weasyprint import HTML

    html = applica(modello, contesto)
    return HTML(
        string=html, base_url=None, url_fetcher=_nessuna_risorsa_esterna
    ).write_pdf()
