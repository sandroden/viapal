"""
Helper condivisi per le email verso gli inquilini (avvisi utenze, riepilogo
addebiti).

Solo funzioni *dict-driven*: qui dentro non si conosce ``Receivable`` né
``UtilityChargePeriod``. Il contenuto specifico di ogni comunicazione sta nel
suo modulo (``calc/avvisi.py``, ``calc/riepilogo.py``), che passa un contesto
già pronto.

Nota: ``accounts/inviti.py`` implementa lo stesso pattern
(``_applica`` + fallback su ``MessageTemplate``) per le email di invito. Non è
stato accorpato qui di proposito: è un flusso di onboarding, non di
comunicazione contabile, e unificarlo significherebbe toccare l'invito senza
un motivo funzionale.
"""
from decimal import Decimal

from django.conf import settings

from notifications.models import MessageTemplate


def _eur(valore) -> str:
    """Formatta un importo come stringa italiana (es. ``12,34``)."""
    return f"{Decimal(valore):.2f}".replace(".", ",")


def _email_inquilino(tenant) -> str:
    """Email dell'inquilino: prima ``user.email``, poi ``email_alt``."""
    user = getattr(tenant, "user", None)
    email = (getattr(user, "email", "") or "").strip()
    if not email:
        email = (getattr(tenant, "email_alt", "") or "").strip()
    return email


def link_app(path: str = "/i/") -> str:
    """URL assoluto di una pagina della PWA (``APP_BASE_URL`` + path)."""
    base = (getattr(settings, "APP_BASE_URL", "") or "").rstrip("/")
    return f"{base}{path}"


def _applica(template: str, contesto: dict) -> str:
    """Sostituisce i placeholder ``{{chiave}}`` con i valori del contesto."""
    out = template
    for chiave, valore in contesto.items():
        out = out.replace("{{" + chiave + "}}", str(valore))
    return out


def render_messaggio(
    codice: str,
    default_oggetto: str,
    default_corpo: str,
    default_html: str,
    contesto: dict,
    property=None,
) -> tuple[str, str, str]:
    """Restituisce ``(oggetto, corpo_testo, corpo_html)``.

    Oggetto e testo vengono dal ``MessageTemplate`` dell'immobile con quel
    ``codice`` (canale email) se configurato, altrimenti dai default passati.
    La versione HTML usa **sempre** il layout di default: è quella che
    garantisce link e impaginazione, e non è editabile in admin.
    """
    tpl = MessageTemplate.objects.filter(
        property=property,
        codice=codice,
        canale=MessageTemplate.CanaleComunicazione.EMAIL,
    ).first()
    oggetto = _applica(tpl.titolo if tpl else default_oggetto, contesto)
    corpo_txt = _applica(tpl.corpo if tpl else default_corpo, contesto)
    corpo_html = _applica(default_html, contesto)
    return oggetto, corpo_txt, corpo_html


def _now():
    from django.utils import timezone

    return timezone.now()


def _oggi():
    """Data odierna nel fuso locale (non UTC): coerente con scadenze e
    confronto 'inquilino uscito'. ``timezone.now().date()`` darebbe la data
    UTC, sfasata di un giorno nelle ore notturne."""
    from django.utils import timezone

    return timezone.localdate()
