"""
Atto di subentro nel contratto di locazione.

Il subentrante prende il posto dell'uscente nel contratto già registrato,
alle stesse condizioni: l'atto cita per esteso le parti, gli estremi di
registrazione del contratto, la data di effetto del recesso dell'uscente e
le condizioni economiche del subentrante.
"""
import datetime

from properties.models import DocumentTemplate, TenantDocument

from .base import (
    Campo,
    Documento,
    Fonti,
    data_it,
    descrivi_persona,
    eur,
    luogo_nascita,
    nome_cognome,
    residenza,
)


def _scadenza_contratto(fonti: Fonti):
    """Scadenza naturale: decorrenza + durata, il giorno prima."""
    contratto = fonti.contract
    if not contratto or not contratto.data_decorrenza or not contratto.durata_anni:
        return None
    decorrenza = contratto.data_decorrenza
    anno = decorrenza.year + contratto.durata_anni
    try:
        fine = decorrenza.replace(year=anno)
    except ValueError:  # 29 febbraio in un anno non bisestile
        fine = decorrenza.replace(year=anno, day=28)
    return fine - datetime.timedelta(days=1)


def _durata(fonti: Fonti) -> str:
    contratto = fonti.contract
    if not contratto:
        return ""
    if contratto.durata_rinnovo_anni:
        return f"{contratto.durata_anni}+{contratto.durata_rinnovo_anni}"
    return str(contratto.durata_anni)


def _regime(fonti: Fonti) -> str:
    contratto = fonti.contract
    if not contratto:
        return ""
    if contratto.regime_fiscale.startswith("cedolare"):
        return "con opzione per il regime della Cedolare Secca"
    return "in regime IRPEF ordinario"


def _locatori(fonti: Fonti) -> str:
    """"Tizio (...), Caio (...) e Sempronio (...)"."""
    righe = [f"{descrivi_persona(o)}" for o in fonti.comproprietari]
    if not righe:
        return ""
    if len(righe) == 1:
        return righe[0]
    return ", ".join(righe[:-1]) + " e " + righe[-1]


def _subentrante(fonti: Fonti) -> str:
    tenant = fonti.tenant
    pezzi = [tenant.nome_completo]
    if nato := luogo_nascita(tenant):
        pezzi.append(f"nato/a a {nato} il {data_it(tenant.data_nascita)}")
    if tenant.codice_fiscale:
        pezzi.append(f"C.F. {tenant.codice_fiscale}")
    if dove := residenza(tenant):
        pezzi.append(f"domiciliato/a in {dove}")
    if email := _email(fonti):
        pezzi.append(f"e-mail {email}")
    return ", ".join(pezzi)


def _email(fonti: Fonti) -> str:
    tenant = fonti.tenant
    user = getattr(tenant, "user", None)
    return (getattr(user, "email", "") or "").strip() or (tenant.email_alt or "").strip()


def _firme(fonti: Fonti) -> str:
    """Una riga di firma per comproprietario, come blocco HTML."""
    return "\n".join(
        f'<div class="firma"><span class="firma-riga"></span>'
        f'<span class="firma-nome">{o.nome_completo}</span></div>'
        for o in fonti.comproprietari
    )


class AttoSubentro(Documento):
    chiave = DocumentTemplate.Codice.ATTO_SUBENTRO_LOCAZIONE
    titolo = "Atto di subentro nel contratto di locazione"
    tipo_documento = TenantDocument.Tipo.ATTO_SUBENTRO_LOCAZIONE
    prefisso_file = "atto-subentro"

    campi = (
        # ── Immobile ────────────────────────────────────────────────────
        Campo(
            "immobile_comune", "Comune dell'immobile", "property",
            lambda f: f.property.comune, campo_db="comune",
        ),
        Campo(
            "immobile_via", "Via dell'immobile", "property",
            lambda f: f.property.via, campo_db="via",
        ),
        Campo(
            "immobile_civico", "Civico dell'immobile", "property",
            lambda f: f.property.civico, campo_db="civico",
        ),
        Campo(
            "immobile", "Immobile (riga completa)", "property",
            lambda f: (
                f"{f.property.comune}, Via {f.property.via} n. {f.property.civico}"
            ),
            derivato=True,
        ),
        # ── Parte locatrice ─────────────────────────────────────────────
        Campo(
            "locatori", "Comproprietari (righe anagrafiche)", "owner",
            _locatori, derivato=True,
        ),
        Campo(
            "firme_locatori", "Spazi firma dei comproprietari", "owner",
            _firme, derivato=True,
        ),
        # ── Parte subentrante ───────────────────────────────────────────
        Campo(
            "subentrante", "Subentrante (riga anagrafica)", "tenant",
            _subentrante, derivato=True,
        ),
        Campo(
            "subentrante_nome", "Cognome e nome del subentrante", "tenant",
            lambda f: nome_cognome(f.tenant), campo_db="cognome",
        ),
        Campo(
            "subentrante_nascita", "Luogo di nascita del subentrante", "tenant",
            lambda f: luogo_nascita(f.tenant), campo_db="comune_nascita",
        ),
        Campo(
            "subentrante_data_nascita", "Data di nascita del subentrante", "tenant",
            lambda f: f.tenant.data_nascita, campo_db="data_nascita",
        ),
        Campo(
            "subentrante_cf", "Codice fiscale del subentrante", "tenant",
            lambda f: f.tenant.codice_fiscale, campo_db="codice_fiscale",
        ),
        Campo(
            "subentrante_residenza", "Residenza del subentrante", "tenant",
            lambda f: residenza(f.tenant), campo_db="residenza_via",
        ),
        Campo(
            "subentrante_email", "Email del subentrante", "tenant",
            _email, obbligatorio=False,
        ),
        # ── Contratto originario ────────────────────────────────────────
        Campo(
            "contratto_data_stipula", "Data di stipula del contratto", "contract",
            lambda f: f.contract.data_stipula, campo_db="data_stipula",
        ),
        Campo(
            "contratto_decorrenza", "Decorrenza del contratto", "contract",
            lambda f: f.contract.data_decorrenza, campo_db="data_decorrenza",
        ),
        Campo(
            "contratto_scadenza", "Scadenza naturale del contratto", "contract",
            _scadenza_contratto, derivato=True,
        ),
        Campo(
            "contratto_durata", "Durata del contratto (es. 4+2)", "contract",
            _durata, campo_db="durata_anni",
        ),
        Campo(
            "contratto_regime", "Regime fiscale", "contract",
            _regime, derivato=True,
        ),
        Campo(
            "registrazione_ufficio", "Ufficio di registrazione", "contract",
            lambda f: f.contract.ufficio_registrazione,
            campo_db="ufficio_registrazione",
        ),
        Campo(
            "registrazione_data", "Data di registrazione", "contract",
            lambda f: f.contract.data_registrazione, campo_db="data_registrazione",
        ),
        Campo(
            "registrazione_numero", "Numero di registrazione", "contract",
            lambda f: f.contract.numero_registrazione,
            campo_db="numero_registrazione",
        ),
        Campo(
            "registrazione_serie", "Serie di registrazione", "contract",
            lambda f: f.contract.serie_registrazione,
            campo_db="serie_registrazione",
        ),
        Campo(
            "registrazione_codice", "Codice identificativo del contratto", "contract",
            lambda f: f.contract.codice_identificativo,
            campo_db="codice_identificativo",
        ),
        # ── Parte uscente ───────────────────────────────────────────────
        # Finché non si sa a chi si subentra, gli altri campi dell'uscente
        # non sono "mancanti": manca il collegamento, e lo dice questa riga
        # sola invece di quattro.
        Campo(
            "", "Inquilino uscente (a chi subentra questa assegnazione)",
            "assignment", lambda f: f.uscente_assignment,
        ),
        Campo(
            "uscente", "Uscente (riga anagrafica)", "uscente",
            lambda f: descrivi_persona(f.uscente), derivato=True,
        ),
        Campo(
            "uscente_nome", "Nome e cognome dell'uscente", "uscente",
            lambda f: f.uscente.nome_completo, campo_db="cognome",
            richiede=lambda f: f.uscente is not None,
        ),
        Campo(
            "uscente_data_recesso", "Data di effetto del recesso dell'uscente",
            "assignment", lambda f: f.uscente_assignment.valid_to,
            richiede=lambda f: f.uscente_assignment is not None,
        ),
        # ── Oggetto ─────────────────────────────────────────────────────
        Campo(
            "decorrenza_subentro", "Decorrenza del subentro", "assignment",
            lambda f: f.assignment.valid_from,
        ),
        Campo(
            "stanza", "Stanza", "assignment", lambda f: f.assignment.room.nome,
        ),
        Campo(
            "canone", "Canone mensile", "assignment",
            lambda f: eur(f.assignment.canone_mensile),
        ),
        Campo(
            "oneri_accessori", "Quota mensile di oneri accessori", "contract",
            lambda f: eur(f.oneri_accessori) if f.oneri_accessori else "",
        ),
        Campo(
            "deposito", "Deposito cauzionale", "deposito",
            lambda f: eur(f.deposito) if f.deposito else "",
        ),
        Campo(
            "deposito_rate", "Numero di rate del deposito", "deposito",
            lambda f: f.rate_deposito or "",
        ),
        Campo(
            "luogo_firma", "Luogo di sottoscrizione", "property",
            lambda f: f.property.comune, campo_db="comune", derivato=True,
        ),
        Campo(
            "data_oggi", "Data di compilazione", "property",
            lambda f: f.oggi, derivato=True,
        ),
    )

    def campi_extra(self, fonti: Fonti):
        """Un campo per comproprietario: dice *quale* fratello è incompleto."""
        extra = []
        for owner in fonti.comproprietari:
            for leggi, etichetta, campo_db in (
                (nome_cognome, "Cognome e nome", "cognome"),
                (lambda o: o.data_nascita, "Data di nascita", "data_nascita"),
                (luogo_nascita, "Luogo di nascita", "comune_nascita"),
                (residenza, "Residenza", "residenza_comune"),
                (lambda o: o.codice_fiscale, "Codice fiscale", "codice_fiscale"),
            ):
                extra.append(
                    Campo(
                        chiave="",
                        etichetta=f"{etichetta} — {owner.nominativo}",
                        fonte="owner",
                        valore=lambda f, o=owner, fn=leggi: fn(o),
                        campo_db=campo_db,
                        oggetto=lambda f, o=owner: o,
                    )
                )
        return tuple(extra)
