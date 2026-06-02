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
import io
from datetime import timedelta
from decimal import Decimal
from email.message import MIMEPart
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from billing._dates import format_mese_anno
from billing._payments import conto_per_receivable, iban_valido
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
    "{{bonifico}}\n\n"
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
    "{{bonifico_html}}"
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


# ── Bonifico: QR EPC (GiroCode) + IBAN/causale, come la pagina inquilino ──


def _competenza_base(r):
    """Mese di competenza coerente con la causale mostrata in app."""
    if r.causale == Receivable.Causale.UTENZE and r.utility_period_id:
        return r.utility_period.periodo_da
    return r.competenza_da


def _dati_bonifico(receivable) -> dict | None:
    """Beneficiario/IBAN/causale/importo per il bonifico, o ``None``.

    Riusa lo stesso resolver della pagina inquilino (``conto_per_receivable``)
    e valida l'IBAN: niente QR su conti placeholder.
    """
    conto = conto_per_receivable(receivable)
    if not conto or not iban_valido(conto.iban):
        return None
    nominativo = (
        receivable.assignment.tenant.nominativo if receivable.assignment_id else ""
    )
    descrizione = f"Utenze {format_mese_anno(_competenza_base(receivable))}"
    causale = f"{descrizione} - {nominativo}".strip(" -")[:140]
    return {
        "beneficiario": conto.intestatario,
        "iban": conto.iban,
        "banca": conto.banca,
        "causale": causale,
        "importo": float(receivable.importo_dovuto or 0),
    }


def _cid_bonifico(receivable) -> str:
    return f"qr{receivable.id}"


def _epc_payload(b: dict) -> str:
    """Stringa EPC069-12 (GiroCode), identica a quella generata nell'app."""
    imp = f"EUR{Decimal(str(b['importo'])):.2f}" if b["importo"] and b["importo"] > 0 else ""
    return "\n".join(
        [
            "BCD",
            "002",
            "1",
            "SCT",
            "",  # BIC (opzionale in v002)
            (b["beneficiario"] or "")[:70],
            (b["iban"] or "").replace(" ", "").upper(),
            imp,
            "",  # Purpose
            "",  # Remittance strutturata
            (b["causale"] or "")[:140],
            "",  # Info beneficiario→ordinante
        ]
    )


def _qr_png(payload: str, scale: int = 4) -> bytes:
    """PNG del QR a partire dal payload EPC (segno, pure-python)."""
    import segno

    buf = io.BytesIO()
    segno.make(payload, error="m").save(buf, kind="png", scale=scale, border=2)
    return buf.getvalue()


def _bonifico_testo(b: dict) -> str:
    return (
        "Per pagare con bonifico:\n"
        f"  Beneficiario: {b['beneficiario']}\n"
        f"  IBAN: {b['iban']}\n"
        f"  Causale: {b['causale']}\n"
        f"  Importo: {_eur(b['importo'])} €\n"
        "Oppure inquadra il QR nella versione HTML di questa email."
    )


def _bonifico_html(b: dict, cid: str) -> str:
    return (
        '<div style="margin:18px 0;padding:16px;border:1px solid #e0d8cf;'
        'border-radius:12px;background:#fbf7f0">'
        '<div style="font-weight:600;margin-bottom:10px;color:#3a2f24">'
        "Paga con bonifico</div>"
        f'<img src="cid:{cid}" alt="QR bonifico" width="180" height="180" '
        'style="display:block;background:#fff;padding:6px;border-radius:8px;'
        'margin-bottom:12px" />'
        '<table style="border-collapse:collapse;font-size:14px">'
        '<tr><td style="color:#888;padding:2px 14px 2px 0">Beneficiario</td>'
        f'<td style="font-weight:500">{escape(b["beneficiario"])}</td></tr>'
        '<tr><td style="color:#888;padding:2px 14px 2px 0">IBAN</td>'
        f'<td style="font-family:monospace">{escape(b["iban"])}</td></tr>'
        '<tr><td style="color:#888;padding:2px 14px 2px 0">Causale</td>'
        f'<td>{escape(b["causale"])}</td></tr>'
        '<tr><td style="color:#888;padding:2px 14px 2px 0">Importo</td>'
        f'<td style="font-weight:600">{_eur(b["importo"])} €</td></tr>'
        "</table>"
        '<div style="color:#999;font-size:12px;margin-top:10px">Inquadra il QR '
        "con l'app della tua banca: importo e causale si precompilano.</div>"
        "</div>"
    )


def _contesto(receivable, dettaglio: dict | None) -> dict:
    period = receivable.utility_period
    if period:
        periodo_str = f"{period.periodo_da:%d/%m/%Y} – {period.periodo_a:%d/%m/%Y}"
    else:
        periodo_str = ""
    tenant = receivable.assignment.tenant
    voci = _voci_conteggio(receivable, dettaglio)
    bonifico = _dati_bonifico(receivable)
    return {
        "nome": tenant.nominativo,
        "periodo": periodo_str,
        "importo": _eur(receivable.importo_dovuto),
        "scadenza": receivable.scadenza.strftime("%d/%m/%Y") if receivable.scadenza else "",
        "conteggio": _conteggio_testo(voci),
        "conteggio_html": _conteggio_html(voci),
        "bonifico": _bonifico_testo(bonifico) if bonifico else "",
        "bonifico_html": _bonifico_html(bonifico, _cid_bonifico(receivable)) if bonifico else "",
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
    oggi = _oggi()
    avvisi = []
    for r in _receivables_periodo(period):
        if not r.importo_dovuto:
            continue
        oggetto, corpo, corpo_html = _render(
            _contesto(r, dettagli.get(r.assignment_id))
        )
        tenant = r.assignment.tenant
        # Inquilino già uscito: l'occupazione è terminata prima di oggi.
        # L'addebito (conguaglio finale) resta, ma NON gli si manda l'avviso:
        # non vive più qui. Lo si segnala in anteprima.
        valid_to = r.assignment.valid_to
        uscito = bool(valid_to and valid_to < oggi)
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
                "uscito": uscito,
                "notificare": not uscito,
                "valid_to": valid_to,
                # Dati bonifico per l'anteprima FE (QR ricostruito client-side)
                # e per allegare il QR all'email reale.
                "bonifico": _dati_bonifico(r),
                "qr_cid": _cid_bonifico(r),
            }
        )
    return avvisi


def invia_avvisi_utenze(period, dry_run: bool = False, escludi_ids=None) -> dict:
    """Invia (o simula con ``dry_run``) le email di avviso utenze del periodo.

    - ``dry_run=True``: nessun invio, nessuna scrittura; ogni avviso ha
      ``esito='anteprima'`` (o ``'senza_email'``). Serve a mostrare il testo
      esatto e farlo approvare prima dell'invio reale.
    - ``dry_run=False``: invia via SMTP (multipart text+html) e logga una
      ``Notification`` (con ``inviata_at``) per ogni destinatario raggiunto;
      al termine valorizza ``period.avvisi_inviati_at``.

    ``escludi_ids``: insieme di ``receivable_id`` che il proprietario ha
    deselezionato a mano (es. chi ha già saldato) → ``esito='escluso'``, non
    si invia.
    """
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "noreply@viapal.local"
    escludi_set = {int(x) for x in (escludi_ids or [])}

    avvisi = costruisci_avvisi_utenze(period)
    inviati = 0
    errori = 0
    senza_email = []
    non_inviati = []
    esclusi = []
    # La scadenza del pagamento è 2 settimane dall'avviso (non esplicitata
    # nella mail): la fissiamo al momento dell'invio reale, sui Receivable
    # effettivamente notificati.
    nuova_scadenza = _oggi() + timedelta(days=14)

    # mappa receivable_id -> oggetto Receivable per il logging (GenericFK)
    receivables = {r.id: r for r in _receivables_periodo(period)}

    for a in avvisi:
        if not a.get("notificare", True):
            # Inquilino uscito: non si invia (né in dry-run né reale).
            a["esito"] = "non_inviato"
            non_inviati.append(a["tenant_nominativo"])
            continue
        if a["receivable_id"] in escludi_set:
            # Escluso a mano dal proprietario.
            a["esito"] = "escluso"
            esclusi.append(a["tenant_nominativo"])
            continue
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
            # QR bonifico inline (cid). Django 6 usa l'API moderna email:
            # un MIMEPart con Content-ID, referenziato da <img src="cid:…">.
            if a.get("bonifico"):
                qr = MIMEPart()
                qr.set_content(
                    _qr_png(_epc_payload(a["bonifico"])),
                    maintype="image",
                    subtype="png",
                    disposition="inline",
                    cid=f"<{a['qr_cid']}>",
                    filename="bonifico.png",
                )
                msg.attach(qr)
            msg.send(fail_silently=False)
            a["esito"] = "inviato"
            inviati += 1
            if receivable is not None and receivable.scadenza != nuova_scadenza:
                receivable.scadenza = nuova_scadenza
                receivable.save(update_fields=["scadenza"])
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
        "non_inviati": non_inviati,
        "esclusi": esclusi,
        "avvisi_inviati_at": period.avvisi_inviati_at,
        "avvisi": avvisi,
    }


def _now():
    from django.utils import timezone

    return timezone.now()


def _oggi():
    """Data odierna nel fuso locale (non UTC): coerente con scadenze e
    confronto 'inquilino uscito'. ``timezone.now().date()`` darebbe la data
    UTC, sfasata di un giorno nelle ore notturne."""
    from django.utils import timezone

    return timezone.localdate()
