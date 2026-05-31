"""
Costruzione e invio degli **avvisi utenze** agli inquilini.

Architettura a canali: oggi è implementato il canale ``email``; il canale
``push`` si innesterà qui (stessa firma) quando gli inquilini avranno
installato la PWA e registrato una ``PushSubscription``.

Il testo del messaggio viene da un ``MessageTemplate`` con codice
``avviso_utenze`` (canale email): ``titolo`` → oggetto, ``corpo`` → corpo, con
placeholder ``{{variabile}}``. Se il template non esiste si usa un fallback
inline, così il flusso funziona anche prima di configurarlo in admin.

L'email viene spedita come **multipart text+html**: la versione HTML contiene
un link cliccabile alla pagina dell'inquilino nell'app e il *conteggio* (la
ripartizione luce/gas/TARI con i giorni di presenza).
"""
from decimal import Decimal
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from billing.models import Receivable
from notifications.models import MessageTemplate, Notification

TEMPLATE_CODICE = "avviso_utenze"

DEFAULT_OGGETTO = "Viapal — conguaglio utenze {{periodo}}"

# Versione testo (fallback / client senza HTML).
DEFAULT_CORPO = (
    "Ciao {{nome}},\n\n"
    "è disponibile il conteggio delle utenze per il periodo {{periodo}}.\n"
    "Il tuo importo è di {{importo}} € (luce, gas e TARI ripartiti sui giorni "
    "di effettiva presenza).\n\n"
    "Dettaglio:\n{{conteggio}}\n\n"
    "Scadenza del pagamento: {{scadenza}}.\n\n"
    "Vedi il dettaglio nell'app Viapal: {{link}}\n\n"
    "Grazie,\ni proprietari"
)

# Versione HTML: link cliccabile + tabella del conteggio.
DEFAULT_CORPO_HTML = (
    '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;'
    'color:#333;line-height:1.5">'
    "<p>Ciao {{nome}},</p>"
    "<p>è disponibile il conteggio delle utenze per il periodo "
    "<strong>{{periodo}}</strong> (luce, gas e TARI ripartiti sui giorni di "
    "effettiva presenza).</p>"
    "<p>Il tuo importo è di <strong>{{importo}} €</strong>.</p>"
    "{{conteggio_html}}"
    "<p>Scadenza del pagamento: <strong>{{scadenza}}</strong>.</p>"
    '<p style="margin-top:20px">'
    '<a href="{{link}}" style="display:inline-block;background:#9b5a3a;'
    "color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;"
    'font-weight:600">Vedi il dettaglio nell\'app Viapal →</a></p>'
    "<p style=\"color:#888;font-size:13px\">Se il pulsante non funziona, "
    'copia questo indirizzo: <br><a href="{{link}}">{{link}}</a></p>'
    "<p>Grazie,<br>i proprietari</p>"
    "</div>"
)

VOCI_LABEL = {"luce": "Luce", "gas": "Gas", "tari": "TARI", "altro": "Altro"}
VOCI_ORDINE = ["luce", "gas", "tari", "altro"]


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


def _link_inquilino(receivable) -> str:
    """URL della pagina di dettaglio conguaglio nell'app dell'inquilino."""
    base = (getattr(settings, "APP_BASE_URL", "") or "").rstrip("/")
    return f"{base}/i/utenze/{receivable.id}"


def _voci_conteggio(receivable, dettaglio: dict | None) -> list[tuple[str, str]]:
    """Lista ``(label, importo_formattato)`` della ripartizione + giorni."""
    voci: list[tuple[str, str]] = []
    dett = dettaglio or {}
    for voce in VOCI_ORDINE:
        if voce in dett and dett[voce]:
            voci.append((VOCI_LABEL[voce], f"{_eur(dett[voce])} €"))
    giorni = getattr(receivable, "giorni_presenza", None)
    if giorni:
        voci.append(("Giorni di presenza nel periodo", str(giorni)))
    return voci


def _conteggio_testo(voci: list[tuple[str, str]]) -> str:
    if not voci:
        return "  (dettaglio non disponibile)"
    return "\n".join(f"  • {label}: {valore}" for label, valore in voci)


def _conteggio_html(voci: list[tuple[str, str]]) -> str:
    if not voci:
        return ""
    righe = "".join(
        f'<tr><td style="padding:4px 12px 4px 0;color:#555">{escape(label)}</td>'
        f'<td style="padding:4px 0;text-align:right;font-weight:600">'
        f"{escape(valore)}</td></tr>"
        for label, valore in voci
    )
    return (
        '<table style="border-collapse:collapse;margin:8px 0 16px">'
        f"<tbody>{righe}</tbody></table>"
    )


def _contesto(receivable, dettaglio: dict | None) -> dict:
    period = receivable.utility_period
    if period:
        periodo_str = f"{period.periodo_da:%d/%m/%Y} – {period.periodo_a:%d/%m/%Y}"
    else:
        periodo_str = ""
    tenant = receivable.assignment.tenant
    voci = _voci_conteggio(receivable, dettaglio)
    return {
        "nome": tenant.nominativo,
        "periodo": periodo_str,
        "importo": _eur(receivable.importo_dovuto),
        "scadenza": receivable.scadenza.strftime("%d/%m/%Y") if receivable.scadenza else "",
        "conteggio": _conteggio_testo(voci),
        "conteggio_html": _conteggio_html(voci),
        "link": _link_inquilino(receivable),
    }


def _applica(template: str, contesto: dict) -> str:
    out = template
    for chiave, valore in contesto.items():
        out = out.replace("{{" + chiave + "}}", str(valore))
    return out


def _render(contesto: dict) -> tuple[str, str, str]:
    """Restituisce ``(oggetto, corpo_testo, corpo_html)``.

    Il testo viene dal ``MessageTemplate`` (se configurato) o dal fallback; la
    versione HTML usa sempre il layout di default così il link e la tabella
    del conteggio sono garantiti.
    """
    tpl = MessageTemplate.objects.filter(
        codice=TEMPLATE_CODICE,
        canale=MessageTemplate.CanaleComunicazione.EMAIL,
    ).first()
    oggetto_raw = tpl.titolo if tpl else DEFAULT_OGGETTO
    corpo_raw = tpl.corpo if tpl else DEFAULT_CORPO
    oggetto = _applica(oggetto_raw, contesto)
    corpo_txt = _applica(corpo_raw, contesto)
    corpo_html = _applica(DEFAULT_CORPO_HTML, contesto)
    return oggetto, corpo_txt, corpo_html


def _receivables_periodo(period):
    return (
        Receivable.objects.filter(
            causale=Receivable.Causale.UTENZE, utility_period=period
        )
        .select_related("assignment__tenant__user", "utility_period")
        .order_by("assignment__tenant__nominativo")
    )


def _dettagli_per_assignment(period) -> dict:
    """Mappa ``assignment_id -> dettaglio`` (luce/gas/TARI) ricalcolata.

    Il dettaglio per-voce non è persistito sul ``Receivable``: lo ricaviamo da
    una simulazione (``persist=False``) per arricchire l'avviso. È solo
    informativo: l'importo mostrato resta quello del ``Receivable``.
    """
    from billing.calc.utility import calcola_conguaglio_periodo

    try:
        risultato = calcola_conguaglio_periodo(period.id, persist=False)
    except Exception:  # noqa: BLE001 — il dettaglio è opzionale
        return {}
    return {
        q["assignment_id"]: q.get("dettaglio", {})
        for q in risultato.get("quote", [])
    }


def costruisci_avvisi_utenze(period) -> list[dict]:
    """Lista degli avvisi previsti (un dict per inquilino con importo != 0).

    Usata sia per l'anteprima (dry-run) sia come base dell'invio.
    """
    dettagli = _dettagli_per_assignment(period)
    avvisi = []
    for r in _receivables_periodo(period):
        if not r.importo_dovuto:
            continue
        oggetto, corpo, corpo_html = _render(
            _contesto(r, dettagli.get(r.assignment_id))
        )
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
                "corpo_html": corpo_html,
                "canale": "email",
            }
        )
    return avvisi


def invia_avvisi_utenze(period, dry_run: bool = False) -> dict:
    """Invia (o simula con ``dry_run``) le email di avviso utenze del periodo.

    - ``dry_run=True``: nessun invio, nessuna scrittura; ogni avviso ha
      ``esito='anteprima'`` (o ``'senza_email'``). Serve a mostrare il testo
      esatto e farlo approvare prima dell'invio reale.
    - ``dry_run=False``: invia via SMTP (multipart text+html) e logga una
      ``Notification`` (con ``inviata_at``) per ogni destinatario raggiunto;
      al termine valorizza ``period.avvisi_inviati_at``.
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
            msg = EmailMultiAlternatives(
                a["oggetto"], a["corpo"], from_email, [a["email"]]
            )
            msg.attach_alternative(a["corpo_html"], "text/html")
            msg.send(fail_silently=False)
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

    if not dry_run and inviati:
        period.avvisi_inviati_at = _now()
        period.save(update_fields=["avvisi_inviati_at"])

    return {
        "period_id": period.id,
        "dry_run": dry_run,
        "from_email": from_email,
        "totale": len(avvisi),
        "inviati": inviati,
        "errori": errori,
        "senza_email": senza_email,
        "avvisi_inviati_at": period.avvisi_inviati_at,
        "avvisi": avvisi,
    }


def _now():
    from django.utils import timezone

    return timezone.now()
