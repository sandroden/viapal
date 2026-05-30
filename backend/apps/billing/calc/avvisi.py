"""
Costruzione e invio degli **avvisi utenze** agli inquilini.

Architettura a canali: oggi è implementato il canale ``email``; il canale
``push`` si innesterà qui (stessa firma) quando gli inquilini avranno
installato la PWA e registrato una ``PushSubscription``.

Il testo del messaggio viene da un ``MessageTemplate`` con codice
``avviso_utenze`` (canale email): ``titolo`` → oggetto, ``corpo`` → corpo, con
placeholder ``{{variabile}}``. Se il template non esiste si usa un fallback
inline, così il flusso funziona anche prima di configurarlo in admin.
"""
from django.conf import settings
from django.core.mail import send_mail

from billing.models import Receivable
from notifications.models import MessageTemplate, Notification

TEMPLATE_CODICE = "avviso_utenze"

DEFAULT_OGGETTO = "Viapal — conguaglio utenze {{periodo}}"
DEFAULT_CORPO = (
    "Ciao {{nome}},\n\n"
    "è disponibile il conteggio delle utenze per il periodo {{periodo}}.\n"
    "Il tuo importo è di {{importo}} € (luce, gas e TARI ripartiti sui giorni "
    "di effettiva presenza).\n"
    "Scadenza del pagamento: {{scadenza}}.\n\n"
    "Trovi il dettaglio nell'app Viapal.\n\n"
    "Grazie,\ni proprietari"
)


def _email_inquilino(tenant) -> str:
    """Email dell'inquilino: prima ``user.email``, poi ``email_alt``."""
    user = getattr(tenant, "user", None)
    email = (getattr(user, "email", "") or "").strip()
    if not email:
        email = (getattr(tenant, "email_alt", "") or "").strip()
    return email


def _contesto(receivable) -> dict:
    period = receivable.utility_period
    if period:
        periodo_str = f"{period.periodo_da:%d/%m/%Y} – {period.periodo_a:%d/%m/%Y}"
    else:
        periodo_str = ""
    tenant = receivable.assignment.tenant
    return {
        "nome": tenant.nominativo,
        "periodo": periodo_str,
        "importo": f"{receivable.importo_dovuto:.2f}",
        "scadenza": receivable.scadenza.strftime("%d/%m/%Y") if receivable.scadenza else "",
    }


def _applica(template: str, contesto: dict) -> str:
    out = template
    for chiave, valore in contesto.items():
        out = out.replace("{{" + chiave + "}}", str(valore))
    return out


def _render(contesto: dict) -> tuple[str, str]:
    tpl = MessageTemplate.objects.filter(
        codice=TEMPLATE_CODICE,
        canale=MessageTemplate.CanaleComunicazione.EMAIL,
    ).first()
    oggetto_raw = tpl.titolo if tpl else DEFAULT_OGGETTO
    corpo_raw = tpl.corpo if tpl else DEFAULT_CORPO
    return _applica(oggetto_raw, contesto), _applica(corpo_raw, contesto)


def _receivables_periodo(period):
    return (
        Receivable.objects.filter(
            causale=Receivable.Causale.UTENZE, utility_period=period
        )
        .select_related("assignment__tenant__user", "utility_period")
        .order_by("assignment__tenant__nominativo")
    )


def costruisci_avvisi_utenze(period) -> list[dict]:
    """Lista degli avvisi previsti (un dict per inquilino con importo != 0).

    Usata sia per l'anteprima (dry-run) sia come base dell'invio.
    """
    avvisi = []
    for r in _receivables_periodo(period):
        if not r.importo_dovuto:
            continue
        oggetto, corpo = _render(_contesto(r))
        tenant = r.assignment.tenant
        avvisi.append(
            {
                "receivable_id": r.id,
                "tenant_id": tenant.id,
                "tenant_nominativo": tenant.nominativo,
                "email": _email_inquilino(tenant),
                "importo": r.importo_dovuto,
                "scadenza": r.scadenza,
                "oggetto": oggetto,
                "corpo": corpo,
                "canale": "email",
            }
        )
    return avvisi


def invia_avvisi_utenze(period, dry_run: bool = False) -> dict:
    """Invia (o simula con ``dry_run``) le email di avviso utenze del periodo.

    - ``dry_run=True``: nessun invio, nessuna scrittura; ogni avviso ha
      ``esito='anteprima'`` (o ``'senza_email'``). Serve a mostrare il testo
      esatto e farlo approvare prima dell'invio reale.
    - ``dry_run=False``: invia via ``send_mail`` e logga una ``Notification``
      (con ``inviata_at``) per ogni destinatario raggiunto.
    """
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "noreply@viapal.local"

    avvisi = costruisci_avvisi_utenze(period)
    inviati = 0
    errori = 0
    senza_email = []

    # mappa receivable_id -> oggetto Receivable per il logging (GenericFK)
    receivables = {r.id: r for r in _receivables_periodo(period)}

    for a in avvisi:
        if not a["email"]:
            a["esito"] = "senza_email"
            senza_email.append(a["tenant_nominativo"])
            continue
        if dry_run:
            a["esito"] = "anteprima"
            continue

        receivable = receivables.get(a["receivable_id"])
        tenant = receivable.assignment.tenant if receivable else None
        user = getattr(tenant, "user", None)
        try:
            send_mail(
                a["oggetto"], a["corpo"], from_email, [a["email"]], fail_silently=False
            )
            a["esito"] = "inviato"
            inviati += 1
            if user is not None:
                Notification.objects.create(
                    user=user,
                    canale=Notification.CanaleComunicazione.EMAIL,
                    oggetto=a["oggetto"],
                    corpo=a["corpo"],
                    inviata_at=_now(),
                    oggetto_riferimento=receivable,
                )
        except Exception as e:  # noqa: BLE001 — riportiamo l'errore all'utente
            a["esito"] = "errore"
            a["errore"] = str(e)
            errori += 1

    return {
        "period_id": period.id,
        "dry_run": dry_run,
        "from_email": from_email,
        "totale": len(avvisi),
        "inviati": inviati,
        "errori": errori,
        "senza_email": senza_email,
        "avvisi": avvisi,
    }


def _now():
    from django.utils import timezone

    return timezone.now()
