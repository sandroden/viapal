"""Avvisi ai proprietari su quanto fanno gli inquilini dall'app.

Oggi un evento solo: l'inquilino dichiara di aver pagato. È l'unico momento
in cui la proprietà *deve* fare qualcosa — confermare l'incasso — e finora
nulla glielo diceva: la dichiarazione cambiava lo stato in silenzio e la si
scopriva entrando nei ritardi.

Canale push soltanto (best-effort): un'email per ogni dichiarazione sarebbe
rumore, e chi non ha attivato le notifiche continua a vedere lo stato in
pagina come prima.
"""
import logging

from django.contrib.auth import get_user_model

from billing._payments import conto_per_receivable
from notifications.push import invia_push
from properties.models import Property, PropertyMembership

logger = logging.getLogger(__name__)

CODICE_DICHIARAZIONE = "dichiarazione_pagamento"


def _property_di(receivable) -> Property | None:
    """L'immobile dell'addebito, risalendo assignment → room → property."""
    assignment = receivable.assignment
    room = getattr(assignment, "room", None) if assignment else None
    return getattr(room, "property", None) if room else None


def destinatari_dichiarazione(receivable, escludi=None) -> list:
    """Chi va avvisato della dichiarazione di ``receivable``.

    Segue ``Property.notifica_dichiarazioni``. L'opzione "solo il
    destinatario" è un restringimento a *un* membro fra i proprietari: se il
    conto non è risolvibile, o il suo intestatario non è un proprietario di
    questo immobile, si torna a tutti — meglio un avviso di troppo che una
    dichiarazione che non vede nessuno.
    """
    prop = _property_di(receivable)
    if prop is None:
        return []

    User = get_user_model()
    tutti = list(
        User.objects.filter(
            property_memberships__property=prop,
            property_memberships__ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
        )
        .distinct()
        .order_by("id")
    )

    if prop.notifica_dichiarazioni == Property.NotificaDichiarazioni.DESTINATARIO:
        conto = conto_per_receivable(receivable)
        incassante = getattr(getattr(conto, "owner", None), "user", None)
        if incassante in tutti:
            tutti = [incassante]
        else:
            logger.info(
                "Dichiarazione su %s: destinatario del bonifico non "
                "risolvibile fra i proprietari di %s, avviso tutti.",
                receivable.pk, prop,
            )

    # Chi ha premuto il bottone non si avvisa da solo: un proprietario può
    # dichiarare al posto dell'inquilino (vedi ``dichiara_pagato``).
    if escludi is not None:
        tutti = [u for u in tutti if u.pk != escludi.pk]
    return tutti


def notifica_dichiarazione_pagamento(receivable, autore=None) -> dict:
    """Avvisa i proprietari che un inquilino dichiara di aver pagato.

    Best-effort in ogni senso: non solleva mai (la dichiarazione dell'inquilino
    non deve fallire perché una push non parte) e su chi non ha sottoscritto
    non fa nulla.
    """
    esito = {"destinatari": 0, "inviate": 0}
    try:
        assignment = receivable.assignment
        tenant = getattr(assignment, "tenant", None) if assignment else None
        nominativo = getattr(tenant, "nominativo", None) or "Un inquilino"

        for user in destinatari_dichiarazione(receivable, escludi=autore):
            esito["destinatari"] += 1
            esito["inviate"] += invia_push(
                user,
                titolo=f"{nominativo} dichiara di aver pagato",
                corpo=(
                    f"{receivable}: {receivable.importo_dovuto:.2f} €. "
                    "Tocca per confermare l'incasso."
                ),
                url="/p/ritardi",
                oggetto_riferimento=receivable,
                codice=CODICE_DICHIARAZIONE,
            )["inviate"]
    except Exception as e:  # noqa: BLE001 — canale accessorio, mai bloccante
        logger.warning("Avviso dichiarazione fallito per %s: %s", receivable.pk, e)
    return esito
