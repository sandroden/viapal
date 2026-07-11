"""
Invito inquilino via email.

Genera per l'inquilino un link "imposta password" e invia una email che
presenta Viapal e spiega come autenticarsi. Il trigger è l'azione
``Invia email di invito`` nell'admin Django (``TenantProfileAdmin``).

Il link riusa **lo stesso meccanismo di token** del reset password di
dj-rest-auth (``/api/auth/password/reset/confirm/``): con allauth installato il
token è prodotto da ``allauth.account.forms.default_token_generator`` e l'uid da
``user_pk_to_url_str`` (base36 per PK interi). Così una sola pagina della SPA
(``/imposta-password/<uid>/<token>``) serve sia il primo set-password (invito)
sia il reset di una password dimenticata. Il token si invalida appena la
password viene impostata: l'invito è quindi monouso.

Per il testo dell'email si segue lo stesso pattern di
``billing.calc.avvisi``: ``EmailMultiAlternatives`` con versione testo dal
``MessageTemplate`` con codice ``invito_inquilino`` (canale email) — o un
fallback inline se il template non è configurato — e versione HTML sempre dal
layout di default (così il pulsante col link è garantito).
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from notifications.models import MessageTemplate, Notification

TEMPLATE_CODICE = "invito_inquilino"

DEFAULT_OGGETTO = "Benvenuto su Viapal — attiva il tuo accesso"

# Versione testo (fallback / client senza HTML).
DEFAULT_CORPO = (
    "Ciao {{nome}},\n\n"
    "ti diamo il benvenuto su Viapal, l'app con cui seguire l'affitto della "
    "tua stanza: canone e scadenze, conguagli delle utenze, pagamenti e "
    "ricevute, sempre a portata di mano.\n\n"
    "Per iniziare devi impostare la tua password. Apri questo link:\n"
    "{{link}}\n\n"
    "Poi potrai entrare da {{app_url}} usando come nome utente "
    "\"{{username}}\" (oppure questo indirizzo email) e la password che hai "
    "scelto.\n\n"
    "Il link è personale e vale una sola volta: se scade, dalla pagina di "
    "accesso puoi usare \"Password dimenticata\" per riceverne uno nuovo.\n\n"
    "A presto,\ni proprietari"
)

# Versione HTML: presentazione + pulsante col link.
DEFAULT_CORPO_HTML = (
    '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;'
    'color:#333;line-height:1.5">'
    "<p>Ciao {{nome}},</p>"
    "<p>ti diamo il benvenuto su <strong>Viapal</strong>, l'app con cui "
    "seguire l'affitto della tua stanza: canone e scadenze, conguagli delle "
    "utenze, pagamenti e ricevute, sempre a portata di mano.</p>"
    "<p>Per iniziare imposta la tua password:</p>"
    '<p style="margin:20px 0">'
    '<a href="{{link}}" style="display:inline-block;background:#9b5a3a;'
    "color:#fff;text-decoration:none;padding:12px 20px;border-radius:8px;"
    'font-weight:600">Imposta la password &rarr;</a></p>'
    "<p>Poi potrai accedere da "
    '<a href="{{app_url}}">{{app_url}}</a> usando come nome utente '
    "<strong>{{username}}</strong> (oppure questo indirizzo email) e la "
    "password che hai scelto.</p>"
    '<p style="color:#888;font-size:13px">Il link è personale e vale una sola '
    "volta. Se è scaduto, dalla pagina di accesso usa "
    "&laquo;Password dimenticata&raquo; per riceverne uno nuovo.<br>"
    'Se il pulsante non funziona, copia questo indirizzo:<br>'
    '<a href="{{link}}">{{link}}</a></p>'
    "<p>A presto,<br>i proprietari</p>"
    "</div>"
)


def _email_inquilino(tenant) -> str:
    """Email a cui inviare l'invito: prima ``user.email``, poi ``email_alt``."""
    user = getattr(tenant, "user", None)
    email = (getattr(user, "email", "") or "").strip()
    if not email:
        email = (getattr(tenant, "email_alt", "") or "").strip()
    return email


def _imposta_password_url(user) -> str:
    """Link SPA con uid+token allauth, validabile dall'endpoint confirm."""
    from allauth.account.forms import default_token_generator
    from allauth.account.utils import user_pk_to_url_str

    uid = user_pk_to_url_str(user)
    token = default_token_generator.make_token(user)
    base = (settings.APP_BASE_URL or "").rstrip("/")
    return f"{base}/imposta-password/{uid}/{token}"


def _applica(template: str, contesto: dict) -> str:
    out = template
    for chiave, valore in contesto.items():
        out = out.replace("{{" + chiave + "}}", str(valore))
    return out


def _render(contesto: dict, property=None) -> tuple[str, str, str]:
    """``(oggetto, corpo_testo, corpo_html)``: testo dal MessageTemplate
    dell'immobile o dal fallback; HTML sempre dal layout di default."""
    tpl = MessageTemplate.objects.filter(
        property=property,
        codice=TEMPLATE_CODICE,
        canale=MessageTemplate.CanaleComunicazione.EMAIL,
    ).first()
    oggetto = _applica(tpl.titolo if tpl else DEFAULT_OGGETTO, contesto)
    corpo_txt = _applica(tpl.corpo if tpl else DEFAULT_CORPO, contesto)
    corpo_html = _applica(DEFAULT_CORPO_HTML, contesto)
    return oggetto, corpo_txt, corpo_html


def _assicura_email_login(user, email: str) -> None:
    """Per consentire il login via email, l'indirizzo deve stare su
    ``user.email``. Se è vuoto e l'invito parte da ``email_alt``, lo copiamo —
    solo se nessun altro utente usa già quell'indirizzo (vincolo
    ``ACCOUNT_UNIQUE_EMAIL``)."""
    if (user.email or "").strip():
        return
    User = get_user_model()
    if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
        return
    user.email = email
    user.save(update_fields=["email"])


def invia_invito_inquilino(tenant, request=None) -> dict:
    """Invia l'email di invito all'inquilino. Idempotente sul gruppo.

    Ritorna ``{"esito": "inviato"|"errore", "email": str, "errore": str|None}``.
    """
    user = tenant.user
    email = _email_inquilino(tenant)
    if not email:
        return {
            "esito": "errore",
            "email": "",
            "errore": "Nessuna email impostata (né user.email né email alternativa).",
        }

    # Ruolo inquilino (idempotente) e, se serve, email per il login via email.
    gruppo, _ = Group.objects.get_or_create(name=settings.ROLE_INQUILINI)
    user.groups.add(gruppo)
    _assicura_email_login(user, email)

    contesto = {
        "nome": tenant.nominativo or user.get_full_name() or user.username,
        "username": user.username,
        "link": _imposta_password_url(user),
        "app_url": (settings.APP_BASE_URL or "").rstrip("/"),
    }
    oggetto, corpo, corpo_html = _render(contesto, property=tenant.property)

    try:
        msg = EmailMultiAlternatives(
            oggetto, corpo, settings.DEFAULT_FROM_EMAIL, [email]
        )
        msg.attach_alternative(corpo_html, "text/html")
        msg.send(fail_silently=False)
    except Exception as e:  # noqa: BLE001 — l'esito torna all'azione admin
        return {"esito": "errore", "email": email, "errore": str(e)}

    Notification.objects.create(
        user=user,
        canale=Notification.CanaleComunicazione.EMAIL,
        oggetto=oggetto,
        corpo=corpo,
        inviata_at=timezone.now(),
        oggetto_riferimento=tenant,
    )
    return {"esito": "inviato", "email": email, "errore": None}


# ---------------------------------------------------------------------------
# Invito membro (co-proprietario / gestore) — multiproprietà
# ---------------------------------------------------------------------------

MEMBRO_OGGETTO = "Viapal — sei stato invitato a gestire {{immobile}}"

MEMBRO_CORPO = (
    "Ciao {{nome}},\n\n"
    "{{invitante}} ti ha invitato su Viapal come {{ruolo}} di "
    "{{immobile}}.\n\n"
    "Per iniziare imposta la tua password aprendo questo link:\n"
    "{{link}}\n\n"
    "Poi potrai entrare da {{app_url}} usando come nome utente "
    "\"{{username}}\" (oppure questo indirizzo email) e la password che hai "
    "scelto.\n\n"
    "Il link è personale e vale una sola volta: se scade, dalla pagina di "
    "accesso puoi usare \"Password dimenticata\" per riceverne uno nuovo.\n\n"
    "A presto,\nViapal"
)

MEMBRO_CORPO_HTML = (
    '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;'
    'color:#333;line-height:1.5">'
    "<p>Ciao {{nome}},</p>"
    "<p><strong>{{invitante}}</strong> ti ha invitato su "
    "<strong>Viapal</strong> come {{ruolo}} di <strong>{{immobile}}</strong>.</p>"
    "<p>Per iniziare imposta la tua password:</p>"
    '<p style="margin:20px 0">'
    '<a href="{{link}}" style="display:inline-block;background:#9b5a3a;'
    "color:#fff;text-decoration:none;padding:12px 20px;border-radius:8px;"
    'font-weight:600">Imposta la password &rarr;</a></p>'
    "<p>Poi potrai accedere da "
    '<a href="{{app_url}}">{{app_url}}</a> usando come nome utente '
    "<strong>{{username}}</strong> (oppure questo indirizzo email) e la "
    "password che hai scelto.</p>"
    '<p style="color:#888;font-size:13px">Il link è personale e vale una sola '
    "volta. Se è scaduto, dalla pagina di accesso usa "
    "&laquo;Password dimenticata&raquo; per riceverne uno nuovo.</p>"
    "<p>A presto,<br>Viapal</p>"
    "</div>"
)


def invia_invito_membro(
    property,
    email: str,
    ruolo: str,
    *,
    nominativo: str = "",
    invitato_da=None,
) -> dict:
    """Invita una persona come membro (proprietario/gestore/sola_lettura).

    - Se esiste già un utente con quell'email: aggiunge solo la membership e
      manda una notifica (senza link password: ha già le credenziali).
    - Altrimenti crea l'utente (username = email), la membership e manda
      l'email con il link imposta-password.
    - Per il ruolo 'proprietario' crea anche l'OwnerProfile se manca
      (necessario per quote e incassi).

    Tutto-o-niente: se l'invio email fallisce, utente e membership creati
    in questa chiamata vengono annullati (si può ritentare).

    Ritorna ``{"esito", "email", "user_id", "creato", "errore"}``.
    """
    from django.db import transaction

    from properties.models import PropertyMembership

    User = get_user_model()
    email = (email or "").strip().lower()
    if not email:
        return {"esito": "errore", "email": "", "user_id": None,
                "creato": False, "errore": "Email obbligatoria."}

    with transaction.atomic():
        return _crea_e_invia_membro(
            property, email, ruolo,
            nominativo=nominativo, invitato_da=invitato_da,
        )


class _InvioFallito(Exception):
    pass


def _crea_e_invia_membro(property, email, ruolo, *, nominativo, invitato_da):
    from django.db import transaction

    from properties.models import PropertyMembership

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    creato = False
    if user is None:
        username = email
        if User.objects.filter(username=username).exists():
            return {"esito": "errore", "email": email, "user_id": None,
                    "creato": False,
                    "errore": "Esiste già un utente con questo username."}
        user = User.objects.create_user(
            username=username, email=email,
        )
        user.set_unusable_password()
        if nominativo:
            parti = nominativo.split(" ", 1)
            user.first_name = parti[0]
            user.last_name = parti[1] if len(parti) > 1 else ""
        user.save()
        creato = True

    if hasattr(user, "tenant_profile") and user.tenant_profile.property_id == property.pk:
        return {"esito": "errore", "email": email, "user_id": user.pk,
                "creato": creato,
                "errore": "L'utente è inquilino di questo immobile."}

    gruppo, _ = Group.objects.get_or_create(name=settings.ROLE_PROPRIETARI)
    user.groups.add(gruppo)

    membership, m_creata = PropertyMembership.objects.get_or_create(
        property=property,
        user=user,
        defaults={"ruolo": ruolo, "invitato_da": invitato_da},
    )
    if not m_creata:
        return {"esito": "errore", "email": email, "user_id": user.pk,
                "creato": False,
                "errore": "L'utente è già membro di questo immobile."}

    if ruolo == PropertyMembership.Ruolo.PROPRIETARIO:
        from properties.models import OwnerProfile

        OwnerProfile.objects.get_or_create(
            user=user,
            defaults={"nominativo": nominativo or user.get_full_name() or email},
        )

    ruolo_label = dict(PropertyMembership.Ruolo.choices).get(ruolo, ruolo)
    invitante = ""
    if invitato_da is not None:
        invitante = invitato_da.get_full_name() or invitato_da.username
    contesto = {
        "nome": nominativo or user.get_full_name() or user.username,
        "username": user.username,
        "immobile": property.nome,
        "ruolo": ruolo_label.lower(),
        "invitante": invitante or "Un proprietario",
        "link": _imposta_password_url(user),
        "app_url": (settings.APP_BASE_URL or "").rstrip("/"),
    }
    oggetto = _applica(MEMBRO_OGGETTO, contesto)
    corpo = _applica(MEMBRO_CORPO, contesto)
    corpo_html = _applica(MEMBRO_CORPO_HTML, contesto)
    if not creato:
        # Utente esistente: niente link password, solo avviso.
        corpo = corpo.replace(contesto["link"], contesto["app_url"])
        corpo_html = corpo_html.replace(contesto["link"], contesto["app_url"])

    try:
        msg = EmailMultiAlternatives(
            oggetto, corpo, settings.DEFAULT_FROM_EMAIL, [email]
        )
        msg.attach_alternative(corpo_html, "text/html")
        msg.send(fail_silently=False)
    except Exception as e:  # noqa: BLE001 — l'esito torna alla view
        # Annulla utente/membership creati in questa transazione: il
        # chiamante può ritentare l'invito da capo.
        transaction.set_rollback(True)
        return {"esito": "errore", "email": email, "user_id": None,
                "creato": False, "errore": str(e)}

    Notification.objects.create(
        user=user,
        canale=Notification.CanaleComunicazione.EMAIL,
        oggetto=oggetto,
        corpo=corpo,
        inviata_at=timezone.now(),
        oggetto_riferimento=membership,
    )
    return {"esito": "inviato", "email": email, "user_id": user.pk,
            "creato": creato, "errore": None}
