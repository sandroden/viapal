"""Invio di notifiche **Web Push** (VAPID) agli utenti.

Canale parallelo all'email: il messaggio viene recapitato dal push service
del browser (FCM/autopush/APNs) al service worker della PWA, che mostra la
notifica di sistema. Qui non c'è nessuna connessione persistente: l'invio è
una POST HTTPS cifrata per ogni :class:`PushSubscription` dell'utente.

Comportamento:
- senza chiavi VAPID configurate il canale è disattivato (no-op);
- le subscription morte (push service risponde 404/410: permesso revocato,
  browser disinstallato) vengono eliminate;
- di **ogni** tentativo resta una :class:`Notification` (canale push), come
  già avviene per le email: recapitata (``inviata_at``) o fallita
  (``errore``). Il caso che più serve leggere nel registro è proprio quello
  muto — "ho dichiarato il pagamento e non è arrivato niente" — e finché si
  loggavano solo i successi quel caso non lasciava traccia da nessuna parte.
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
    codice: str = "",
) -> dict:
    """Invia una notifica push a tutti i device registrati dell'utente.

    ``url`` è il path della PWA aperto al click sulla notifica (gestito dal
    service worker). ``codice`` identifica il tipo di comunicazione nel
    registro (es. ``avviso_utenze``). Restituisce
    ``{"inviate", "rimosse", "errori"}``; non solleva mai: il push è un canale
    best-effort, gli errori vengono loggati.
    """
    esito = {"inviate": 0, "rimosse": 0, "errori": 0}
    # Canale spento a livello di installazione (niente chiavi) o nessun
    # utente: non è un tentativo di comunicazione, non si registra nulla.
    if user is None or not push_configurato():
        return esito

    def registra(*, destinatario: str = "", errore: str = "") -> None:
        """Riga di registro del tentativo. Non solleva: il push è accessorio."""
        if not salva_notification:
            return
        try:
            Notification.objects.create(
                user=user,
                canale=Notification.CanaleComunicazione.PUSH,
                codice=codice,
                destinatario=destinatario,
                oggetto=titolo,
                corpo=corpo,
                # Convenzione del modello: le due condizioni si escludono.
                errore=errore,
                inviata_at=None if errore else timezone.now(),
                oggetto_riferimento=oggetto_riferimento,
            )
        except Exception as e:  # noqa: BLE001 — il registro non blocca l'invio
            logger.warning("Registro push non scritto per %s: %s", user, e)

    subscriptions = list(
        PushSubscription.objects.filter(user=user).order_by("id")
    )
    if not subscriptions:
        # Il silenzio più frequente e meno diagnosticabile: la persona non ha
        # mai attivato le notifiche, o la sua sottoscrizione è stata presa da
        # un altro utente sullo stesso browser (upsert per endpoint).
        registra(errore="Nessun dispositivo registrato: notifiche non attive.")
        return esito

    from pywebpush import WebPushException, webpush

    # Etichetta del primo device **raggiunto**: nel registro sta al posto
    # dell'indirizzo email (un push non ha destinatario leggibile).
    destinatario = ""
    fallimenti: list[str] = []
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
            etichetta = sub.device_label or sub.endpoint
            if status in (404, 410):
                # Subscription morta: il device non esiste più per il push
                # service. La togliamo, al prossimo giro non si ritenta.
                sub.delete()
                esito["rimosse"] += 1
                fallimenti.append(f"{etichetta}: dispositivo scollegato (HTTP {status}).")
            else:
                logger.warning(
                    "Push fallita per %s (endpoint %.40s…): %s",
                    user, sub.endpoint, e,
                )
                esito["errori"] += 1
                fallimenti.append(f"{etichetta}: {e}")
        except Exception as e:  # noqa: BLE001 — best-effort, mai bloccare
            logger.warning("Push fallita per %s: %s", user, e)
            esito["errori"] += 1
            fallimenti.append(f"{sub.device_label or sub.endpoint}: {e}")
        else:
            esito["inviate"] += 1
            if not destinatario:
                destinatario = (sub.device_label or sub.endpoint)[:254]
            sub.ultima_attivita = timezone.now()
            sub.save(update_fields=["ultima_attivita"])

    if esito["inviate"]:
        # Recapitata almeno una volta: è partita. I device che hanno fallito
        # restano nel log applicativo — il registro dice "comunicato", e
        # dirlo fallito perché un secondo telefono non risponde sarebbe falso.
        altri = esito["inviate"] - 1
        riga = f"{destinatario} (+{altri})" if altri else destinatario
        # `destinatario` è un CharField(254): il suffisso non deve sforare.
        registra(destinatario=riga[:254])
    else:
        registra(errore="\n".join(fallimenti))
    return esito
