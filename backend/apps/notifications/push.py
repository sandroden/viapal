"""Invio di notifiche **Web Push** (VAPID) agli utenti.

Canale parallelo all'email: il messaggio viene recapitato dal push service
del browser (FCM/autopush/APNs) al service worker della PWA, che mostra la
notifica di sistema. Qui non c'è nessuna connessione persistente: l'invio è
una POST HTTPS cifrata per ogni :class:`PushSubscription` dell'utente.

Comportamento:
- senza chiavi VAPID configurate il canale è disattivato (no-op);
- le subscription morte (push service risponde 404/410: permesso revocato,
  browser disinstallato) vengono eliminate;
- per ogni invio andato a buon fine si logga una :class:`Notification`
  (canale push), come già avviene per le email.
"""
import json
import logging

from django.conf import settings
from django.utils import timezone

from notifications.models import Notification, PushSubscription

logger = logging.getLogger(__name__)


def push_configurato() -> bool:
    """True se le chiavi VAPID sono presenti (canale push attivo)."""
    return bool(settings.VAPID_PRIVATE_KEY and settings.VAPID_PUBLIC_KEY)


def invia_push(
    user,
    titolo: str,
    corpo: str,
    url: str = "/",
    oggetto_riferimento=None,
    salva_notification: bool = True,
) -> dict:
    """Invia una notifica push a tutti i device registrati dell'utente.

    ``url`` è il path della PWA aperto al click sulla notifica (gestito dal
    service worker). Restituisce ``{"inviate", "rimosse", "errori"}``; non
    solleva mai: il push è un canale best-effort, gli errori vengono loggati.
    """
    esito = {"inviate": 0, "rimosse": 0, "errori": 0}
    if user is None or not push_configurato():
        return esito
    subscriptions = list(
        PushSubscription.objects.filter(user=user).order_by("id")
    )
    if not subscriptions:
        return esito

    from pywebpush import WebPushException, webpush

    payload = json.dumps({"title": titolo, "body": corpo, "url": url})
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_CLAIMS_SUB},
                ttl=24 * 3600,
            )
        except WebPushException as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                # Subscription morta: il device non esiste più per il push
                # service. La togliamo, al prossimo giro non si ritenta.
                sub.delete()
                esito["rimosse"] += 1
            else:
                logger.warning(
                    "Push fallita per %s (endpoint %.40s…): %s",
                    user, sub.endpoint, e,
                )
                esito["errori"] += 1
        except Exception as e:  # noqa: BLE001 — best-effort, mai bloccare
            logger.warning("Push fallita per %s: %s", user, e)
            esito["errori"] += 1
        else:
            esito["inviate"] += 1
            sub.ultima_attivita = timezone.now()
            sub.save(update_fields=["ultima_attivita"])

    if salva_notification and esito["inviate"]:
        Notification.objects.create(
            user=user,
            canale=Notification.CanaleComunicazione.PUSH,
            oggetto=titolo,
            corpo=corpo,
            inviata_at=timezone.now(),
            oggetto_riferimento=oggetto_riferimento,
        )
    return esito
