"""Inoltro email dei commenti sugli addebiti (ReceivableComment).

Quando un inquilino lascia un commento su un addebito (es. per spiegare
perché ha versato meno del dovuto), il commento resta visibile nel
dettaglio dell'addebito e viene inoltrato via email ai membri
proprietari/gestori dell'immobile. L'invio è best-effort: un errore SMTP
non fa fallire il salvataggio del commento.
"""
from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from notifications.models import Notification
from properties.models.membership import PropertyMembership


def _nome_autore(user) -> str:
    """Nome leggibile dell'autore: nominativo del profilo se c'è."""
    if user is None:
        return "?"
    tenant = getattr(user, "tenant_profile", None)
    if tenant and tenant.nominativo:
        return tenant.nominativo
    owner = getattr(user, "owner_profile", None)
    if owner and owner.nominativo:
        return owner.nominativo
    return user.get_full_name() or user.username


def _destinatari_proprieta(receivable) -> list:
    """Utenti proprietari/gestori (con email) della property dell'addebito."""
    prop = receivable.assignment.room.property
    memberships = prop.memberships.filter(
        ruolo__in=[
            PropertyMembership.Ruolo.PROPRIETARIO,
            PropertyMembership.Ruolo.GESTORE,
        ]
    ).select_related("user")
    return [m.user for m in memberships if m.user.email]


def invia_email_commento(comment) -> dict:
    """Inoltra il commento di un inquilino ai proprietari/gestori.

    Ritorna ``{"inviate": n, "errori": [msg, ...]}``.
    """
    from billing.dashboard_views import _descrizione_receivable

    r = comment.receivable
    autore = _nome_autore(comment.autore)
    descrizione = _descrizione_receivable(r)
    residuo = (r.importo_dovuto or 0) - (r.importo_pagato or 0)

    oggetto = f"Nota di {autore} su {descrizione}"[:200]
    corpo = (
        f"{autore} ha lasciato una nota su un addebito:\n\n"
        f"  {descrizione} — scadenza {r.scadenza}\n"
        f"  Dovuto {r.importo_dovuto} € · pagato {r.importo_pagato or 0} € · "
        f"residuo {residuo} €\n\n"
        f"«{comment.testo}»\n\n"
        f"La nota resta visibile nel dettaglio dell'addebito.\n"
        f"{settings.APP_BASE_URL}/admin/billing/receivable/{r.id}/change/\n"
    )

    inviate = 0
    errori: list[str] = []
    for user in _destinatari_proprieta(r):
        try:
            msg = EmailMultiAlternatives(
                oggetto, corpo, settings.DEFAULT_FROM_EMAIL, [user.email]
            )
            msg.send(fail_silently=False)
            Notification.objects.create(
                user=user,
                canale=Notification.CanaleComunicazione.EMAIL,
                oggetto=oggetto,
                corpo=corpo,
                inviata_at=timezone.now(),
                oggetto_riferimento=r,
            )
            inviate += 1
        except Exception as exc:  # pragma: no cover - dipende dall'SMTP
            errori.append(f"{user.email}: {exc}")
    return {"inviate": inviate, "errori": errori}
