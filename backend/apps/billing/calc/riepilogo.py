"""
Email di **riepilogo addebiti** all'inquilino.

Parte a inizio mese, appena generato il canone: apre con l'affitto del mese
(il motivo per cui la mail arriva adesso), poi elenca i **pendenti** — voci
già scadute o in scadenza entro ``giorni`` (default 15) — e infine, in una
sezione separata, gli addebiti che l'inquilino ha *dichiarato* di aver pagato
e che aspettano il riscontro del bonifico.

Tre scelte che spiegano cosa NON c'è dentro:

* **niente totali, niente QR, niente IBAN.** È un promemoria: il conto
  completo e i QR per pagare stanno in ``/i/``, dove ogni voce ha il suo. Un
  totale nella mail invecchia (basta un bonifico nel frattempo) e un IBAN in
  chiaro invita a bonificare l'importo sbagliato.
* **le voci oltre la finestra non compaiono.** Chi vuole il quadro completo
  apre l'app.
* **le scadenze non si toccano.** ``invia_avvisi_utenze`` le sposta a +14gg
  perché *è* l'atto che comunica per la prima volta un addebito appena
  emesso; qui gli addebiti sono già emessi, ognuno con la sua scadenza, e la
  mail ne aggrega N: riscriverle azzererebbe i ritardi esistenti (falsando
  ``giorni_ritardo``, il semaforo e la pagina Ritardi) e permetterebbe di
  cancellare un ritardo semplicemente rimandando il sollecito.

I numeri vengono tutti da :func:`billing.calc.posizione.posizione_inquilino`,
la stessa funzione che alimenta la home dell'inquilino: la mail e la pagina
devono dire la stessa cifra.
"""
import datetime
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from billing.calc._email import (
    _applica,  # noqa: F401 — riesportato per i test e i chiamanti
    _email_inquilino,
    _eur,
    _now,
    _oggi,
    link_app,
    render_messaggio,
)
from billing.calc.posizione import posizione_inquilino
from notifications.models import Notification
from notifications.push import invia_push

TEMPLATE_CODICE = "riepilogo_addebiti"

# Finestra dei pendenti: scaduti + in scadenza entro N giorni.
GIORNI_PENDENTI = 15

DEFAULT_OGGETTO = "Viapal — riepilogo dei tuoi addebiti"

DEFAULT_CORPO = (
    "Ciao {{nome}},\n\n"
    "{{canone}}"
    "{{pendenti}}"
    "{{in_attesa}}"
    "Il conto completo e i QR per pagare ogni voce sono nell'app Viapal:\n"
    "{{link}}\n\n"
    "Grazie,\ni proprietari"
)

DEFAULT_CORPO_HTML = (
    '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;'
    'color:#333;line-height:1.5">'
    "<p>Ciao {{nome}},</p>"
    "{{canone_html}}"
    "{{pendenti_html}}"
    "{{in_attesa_html}}"
    '<p style="margin-top:20px">'
    '<a href="{{link}}" style="display:inline-block;background:#9b5a3a;'
    "color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;"
    'font-weight:600">Apri l\'app Viapal →</a></p>'
    '<p style="color:#888;font-size:13px">Nell\'app trovi il conto completo e '
    "il QR per pagare ogni voce.<br>"
    'Se il pulsante non funziona, copia questo indirizzo: '
    '<br><a href="{{link}}">{{link}}</a></p>'
    "<p>Grazie,<br>i proprietari</p>"
    "</div>"
)


# ---------------------------------------------------------------------------
# Selezione delle voci
# ---------------------------------------------------------------------------


def _mese_di(iso: str) -> str:
    """``"2026-08-01"`` → ``"2026-08"`` (gli item portano date ISO)."""
    return (iso or "")[:7]


def _data(iso: str) -> datetime.date | None:
    return datetime.date.fromisoformat(iso) if iso else None


def _partiziona(aperti: list[dict], oggi: datetime.date, giorni: int):
    """``(canone_del_mese, pendenti)`` a partire dagli addebiti aperti.

    Il canone del mese è la voce ``rent`` con competenza nel mese di ``oggi``
    (gli aggiustamenti pro-rata inclusi: un moncone d'uscita è comunque il
    canone di quel mese). Se ce ne fosse più d'uno — ciclo di fatturazione
    "dal giorno di ingresso", a cavallo di due mesi — si prende quello con
    competenza più recente e gli altri restano tra i pendenti.
    """
    mese = f"{oggi.year:04d}-{oggi.month:02d}"
    limite = oggi + datetime.timedelta(days=giorni)

    candidati = [
        x for x in aperti
        if x["tipo"] == "rent" and _mese_di(x["competenza"]) == mese
    ]
    canone = max(candidati, key=lambda x: x["competenza"]) if candidati else None

    pendenti = [
        x for x in aperti
        if x is not canone and (_data(x["scadenza"]) or oggi) <= limite
    ]
    return canone, pendenti


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _scadenza_label(item: dict, oggi: datetime.date) -> str:
    """"scaduta il 15/07/2025" / "in scadenza il 05/08/2025".

    L'anno c'è sempre: gli arretrati di un inquilino uscito possono risalire
    a mesi lontani e un ``gg/mm`` nudo sarebbe ambiguo.
    """
    scadenza = _data(item["scadenza"])
    if scadenza is None:
        return "senza scadenza"
    verbo = "scaduta il" if scadenza < oggi else "in scadenza il"
    return f"{verbo} {scadenza:%d/%m/%Y}"


def _riga_testo(item: dict, oggi: datetime.date) -> str:
    return (
        f"  • {item['descrizione']} · {_scadenza_label(item, oggi)} · "
        f"{_eur(item['residuo'])} €"
    )


def _riga_html(item: dict, oggi: datetime.date) -> str:
    return (
        f'<tr><td style="padding:4px 12px 4px 0">{escape(item["descrizione"])}</td>'
        f'<td style="padding:4px 12px 4px 0;color:#888;white-space:nowrap">'
        f"{escape(_scadenza_label(item, oggi))}</td>"
        f'<td style="padding:4px 0;text-align:right;font-weight:600;'
        f'white-space:nowrap">{_eur(item["residuo"])} €</td></tr>'
    )


def _tabella_html(items: list[dict], oggi: datetime.date) -> str:
    righe = "".join(_riga_html(x, oggi) for x in items)
    return (
        '<table style="border-collapse:collapse;margin:8px 0 16px;width:100%">'
        f"<tbody>{righe}</tbody></table>"
    )


def _blocchi(canone, pendenti, in_attesa, oggi) -> dict:
    """I quattro blocchi di contenuto, in versione testo e HTML."""
    contesto = {
        "canone": "",
        "canone_html": "",
        "pendenti": "",
        "pendenti_html": "",
        "in_attesa": "",
        "in_attesa_html": "",
    }

    if canone is not None:
        contesto["canone"] = (
            f"{canone['descrizione']}: {_eur(canone['residuo'])} € "
            f"({_scadenza_label(canone, oggi)}).\n\n"
        )
        contesto["canone_html"] = (
            '<p style="font-size:17px;margin:0 0 14px">'
            f"<strong>{escape(canone['descrizione'])}</strong>: "
            f"<strong>{_eur(canone['residuo'])} €</strong> "
            f'<span style="color:#888;font-size:14px">'
            f"({escape(_scadenza_label(canone, oggi))})</span></p>"
        )

    if pendenti:
        righe = "\n".join(_riga_testo(x, oggi) for x in pendenti)
        contesto["pendenti"] = f"Da saldare:\n{righe}\n\n"
        contesto["pendenti_html"] = (
            '<p style="margin:16px 0 4px;font-weight:600">Da saldare</p>'
            + _tabella_html(pendenti, oggi)
        )

    if in_attesa:
        righe = "\n".join(_riga_testo(x, oggi) for x in in_attesa)
        contesto["in_attesa"] = (
            "In attesa di conferma (ci hai detto di aver pagato, le "
            "confermiamo appena troviamo il bonifico):\n"
            f"{righe}\n\n"
        )
        contesto["in_attesa_html"] = (
            '<p style="margin:16px 0 4px;font-weight:600">In attesa di conferma</p>'
            '<p style="margin:0 0 4px;color:#888;font-size:13px">Ci hai detto di '
            "aver pagato: le confermiamo appena troviamo il bonifico.</p>"
            + _tabella_html(in_attesa, oggi)
        )

    return contesto


# ---------------------------------------------------------------------------
# Costruzione e invio
# ---------------------------------------------------------------------------


def _ultimi_invii(property) -> dict[int, datetime.datetime]:
    """``tenant_id -> data dell'ultimo riepilogo email effettivamente partito``.

    Il filtro su ``codice`` è indispensabile: l'invito inquilino
    (``accounts/inviti.py``) scrive una ``Notification`` con la stessa
    GenericFK su ``TenantProfile``, e senza distinguerle "già inviato"
    scatterebbe per la mail sbagliata. Il filtro su ``inviata_at`` esclude i
    tentativi falliti, che non sono un invio.
    """
    from django.db.models import Max

    righe = (
        Notification.objects.filter(
            codice=TEMPLATE_CODICE,
            canale=Notification.CanaleComunicazione.EMAIL,
            inviata_at__isnull=False,
            user__tenant_profile__property=property,
        )
        .values("user__tenant_profile")
        .annotate(ultimo=Max("inviata_at"))
    )
    return {r["user__tenant_profile"]: r["ultimo"] for r in righe}


def costruisci_riepiloghi(
    property,
    oggi: datetime.date | None = None,
    giorni: int = GIORNI_PENDENTI,
    tenant_ids=None,
) -> list[dict]:
    """Un dict per inquilino da riepilogare (anteprima e base dell'invio).

    Entrano in lista gli inquilini con il canone del mese **o** almeno un
    pendente. Chi ha solo voci *dichiarate* compare con
    ``notificare=False`` ed ``esito="niente_da_sollecitare"``: non c'è nulla
    da sollecitare, ma vederlo in anteprima evita il dubbio "e questo perché
    non c'è?". Chi non ha né l'uno né gli altri resta fuori.

    Gli inquilini **usciti** con arretrati ricevono (badge ``uscito``): è la
    popolazione da sollecitare, al contrario degli avvisi utenze.
    """
    from properties.models import TenantProfile

    oggi = oggi or _oggi()
    ultimi = _ultimi_invii(property)

    tenants = TenantProfile.objects.filter(property=property).select_related("user")
    if tenant_ids:
        tenants = tenants.filter(id__in=[int(x) for x in tenant_ids])

    riepiloghi = []
    for tenant in tenants.order_by("nominativo"):
        posizione = posizione_inquilino(tenant, oggi, property=property)
        canone, pendenti = _partiziona(posizione["aperti"], oggi, giorni)
        in_attesa = posizione["in_attesa"]
        if canone is None and not pendenti and not in_attesa:
            continue

        contesto = _blocchi(canone, pendenti, in_attesa, oggi)
        contesto["nome"] = tenant.nominativo
        contesto["link"] = link_app("/i/")
        oggetto, corpo, corpo_html = render_messaggio(
            TEMPLATE_CODICE,
            DEFAULT_OGGETTO,
            DEFAULT_CORPO,
            DEFAULT_CORPO_HTML,
            contesto,
            property=property,
        )
        da_sollecitare = canone is not None or bool(pendenti)
        riepiloghi.append(
            {
                "tenant_id": tenant.id,
                "tenant_nominativo": tenant.nominativo,
                "email": _email_inquilino(tenant),
                "uscito": posizione["assignment_attivo"] is None,
                "notificare": da_sollecitare,
                "canone": canone,
                "pendenti": pendenti,
                "in_attesa": in_attesa,
                "oggetto": oggetto,
                "corpo": corpo,
                "corpo_html": corpo_html,
                "canale": "email",
                "ultimo_invio_at": ultimi.get(tenant.id),
            }
        )
    return riepiloghi


def invia_riepiloghi(
    property,
    dry_run: bool = True,
    escludi_ids=None,
    oggi: datetime.date | None = None,
    giorni: int = GIORNI_PENDENTI,
    tenant_ids=None,
) -> dict:
    """Invia (o simula con ``dry_run``, che è il default) i riepiloghi.

    ``escludi_ids`` sono **tenant_id** deselezionati a mano dal proprietario
    → ``esito="escluso"``. L'esito per destinatario finisce nel dict, la
    forma del ritorno è la stessa di ``invia_avvisi_utenze`` così il
    frontend può riusare lo stesso componente.
    """
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "noreply@viapal.local"
    escludi_set = {int(x) for x in (escludi_ids or [])}
    oggi = oggi or _oggi()

    riepiloghi = costruisci_riepiloghi(
        property, oggi=oggi, giorni=giorni, tenant_ids=tenant_ids
    )
    tenants = {
        t.id: t
        for t in _tenant_map(property, [r["tenant_id"] for r in riepiloghi])
    }

    inviati = 0
    errori = 0
    push_inviate = 0
    senza_email = []
    non_inviati = []
    esclusi = []

    for r in riepiloghi:
        if not r["notificare"]:
            r["esito"] = "niente_da_sollecitare"
            non_inviati.append(r["tenant_nominativo"])
            continue
        if r["tenant_id"] in escludi_set:
            r["esito"] = "escluso"
            esclusi.append(r["tenant_nominativo"])
            continue
        if not r["email"]:
            r["esito"] = "senza_email"
            senza_email.append(r["tenant_nominativo"])
            continue
        if dry_run:
            r["esito"] = "anteprima"
            continue

        tenant = tenants.get(r["tenant_id"])
        user = getattr(tenant, "user", None)
        # Push best-effort in aggiunta all'email: senza subscription o senza
        # chiavi VAPID è un no-op e non tocca l'esito dell'email.
        r["push"] = invia_push(
            user,
            titolo=r["oggetto"],
            corpo="Tocca per vedere gli addebiti e pagare dall'app.",
            url="/i/",
            oggetto_riferimento=tenant,
            codice=TEMPLATE_CODICE,
        )
        push_inviate += r["push"]["inviate"]

        try:
            msg = EmailMultiAlternatives(
                r["oggetto"], r["corpo"], from_email, [r["email"]]
            )
            msg.attach_alternative(r["corpo_html"], "text/html")
            msg.send(fail_silently=False)
        except Exception as e:  # noqa: BLE001 — l'esito torna all'utente
            r["esito"] = "errore"
            r["errore"] = str(e)
            errori += 1
            if user is not None:
                _logga(r, user, tenant, errore=str(e))
            continue

        r["esito"] = "inviato"
        inviati += 1
        if user is not None:
            _logga(r, user, tenant)

    return {
        "property_id": property.id,
        "dry_run": dry_run,
        "from_email": from_email,
        "giorni": giorni,
        "totale": len(riepiloghi),
        "inviati": inviati,
        "errori": errori,
        "push_inviate": push_inviate,
        "senza_email": senza_email,
        "non_inviati": non_inviati,
        "esclusi": esclusi,
        "riepiloghi": riepiloghi,
    }


def _tenant_map(property, ids):
    from properties.models import TenantProfile

    return TenantProfile.objects.filter(property=property, id__in=ids).select_related(
        "user"
    )


def _logga(riepilogo: dict, user, tenant, errore: str = "") -> None:
    """Riga di registro, sia per gli invii riusciti sia per i falliti."""
    Notification.objects.create(
        user=user,
        canale=Notification.CanaleComunicazione.EMAIL,
        codice=TEMPLATE_CODICE,
        destinatario=riepilogo["email"],
        oggetto=riepilogo["oggetto"],
        corpo=riepilogo["corpo"],
        corpo_html=riepilogo["corpo_html"],
        errore=errore,
        inviata_at=None if errore else _now(),
        oggetto_riferimento=tenant,
    )
