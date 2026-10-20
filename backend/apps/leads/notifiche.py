"""Avviso push quando il bot deposita contatti nuovi.

La pagina aperta si aggiorna da sola (polling sul riepilogo); questo copre il
caso in cui la pagina è chiusa, che durante una campagna è quasi sempre: chi
scrive per primo a chi cerca stanza ha un vantaggio, e il giro del bot non
avvisa nessuno se non su Telegram.

Nel corpo **solo i numeri**, mai nomi: di ogni push resta una riga nel
registro delle notifiche, e "Chiudi la campagna" cancella i lead ma non quel
registro. I nomi di chi cerca stanza devono andarsene con la campagna.
"""
import logging

from django.contrib.auth import get_user_model

from notifications.push import invia_push
from properties.models import PropertyMembership

logger = logging.getLogger(__name__)

CODICE_NUOVI_LEAD = "nuovi_lead"

# Chi lavora i contatti. "Sola lettura" non li lavora, e non va svegliato.
RUOLI_DESTINATARI = (
    PropertyMembership.Ruolo.PROPRIETARIO,
    PropertyMembership.Ruolo.GESTORE,
)


def destinatari_nuovi_lead(prop, escludi=None) -> list:
    """I membri dell'immobile che lavorano i contatti, tranne ``escludi``
    (l'utente del bot, che è membro come gli altri)."""
    qs = (
        get_user_model()
        .objects.filter(
            property_memberships__property=prop,
            property_memberships__ruolo__in=RUOLI_DESTINATARI,
            is_active=True,
        )
        .distinct()
        .order_by("id")
    )
    if escludi is not None:
        qs = qs.exclude(pk=escludi.pk)
    return list(qs)


def notifica_nuovi_lead(prop, creati: int, escludi=None) -> dict:
    """Un push per giro del bot, non uno per contatto. Best-effort: non
    solleva mai, il deposito del bot non deve fallire per una notifica."""
    esito = {"destinatari": 0, "inviate": 0}
    if creati <= 0:
        return esito
    try:
        contatti = "1 contatto nuovo" if creati == 1 else f"{creati} contatti nuovi"
        titolo = f"Cerca inquilini: {contatti}"
        for user in destinatari_nuovi_lead(prop, escludi=escludi):
            esito["destinatari"] += 1
            esito["inviate"] += invia_push(
                user,
                titolo=titolo,
                corpo=f"{prop.nome}: tocca per vedere chi cerca stanza.",
                url="/p/cerca-inquilini",
                codice=CODICE_NUOVI_LEAD,
            )["inviate"]
    except Exception as e:  # noqa: BLE001 — canale accessorio, mai bloccante
        logger.warning("Avviso nuovi lead fallito per %s: %s", prop, e)
    return esito
