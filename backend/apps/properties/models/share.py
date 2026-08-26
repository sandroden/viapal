"""
Link di lettura: un pacchetto di documenti aperto da un token, senza account.

Serve a mandare a un inquilino in arrivo le carte da leggere prima della
firma. Chi apre il link non ha un utente e non ne avrà uno finché non
subentra: l'autorizzazione è il token e nient'altro.

Due invarianti tengono in piedi la cosa:

* nel pacchetto entra **solo** ciò che è ``PropertyDocument.esponibile``, e
  il controllo si ripete al momento di servire il file — togliere la spunta
  è una revoca a grana fine sui link già mandati;
* il pacchetto **referenzia** i documenti, non li copia: la stessa copia
  oscurata si riusa per ogni destinatario. Rovescio della medaglia,
  sostituire il file cambia anche i link già mandati (voluto: se correggi
  un'omissione la correggi ovunque).

Il testo dei chiarimenti è markdown reso e sanitizzato **qui**, non nel
browser: la pagina pubblica riceve HTML già passato dal sanitizzatore.
"""
import secrets

import markdown
import nh3
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from ._base import TimestampedModel

#: Allowlist stretta per il markdown dei chiarimenti: formattazione di testo
#: e tabelline, nient'altro. Niente ``img`` (nessun caricamento da terzi),
#: niente ``a`` con schemi esotici, niente attributi di stile.
TAG_AMMESSI = frozenset(
    {
        "p", "br", "hr", "strong", "em", "code", "pre", "blockquote",
        "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6",
        "table", "thead", "tbody", "tr", "th", "td", "a",
    }
)
ATTRIBUTI_AMMESSI = {"a": {"href", "title"}}
SCHEMI_AMMESSI = frozenset({"http", "https", "mailto"})


def rendi_markdown(testo):
    """Markdown → HTML sanitizzato. Unico renderer del progetto per i testi
    scritti a mano che finiscono in una pagina pubblica."""
    if not testo:
        return ""
    html = markdown.markdown(testo, extensions=["extra", "sane_lists", "nl2br"])
    return nh3.clean(
        html,
        tags=set(TAG_AMMESSI),
        attributes={k: set(v) for k, v in ATTRIBUTI_AMMESSI.items()},
        url_schemes=set(SCHEMI_AMMESSI),
        link_rel="noopener noreferrer nofollow",
    )


def genera_token():
    """Token del link. Funzione a livello di modulo, non una lambda né una
    chiamata diretta: ``default=secrets.token_urlsafe(32)`` sarebbe valutato
    una volta sola alla definizione della classe (stesso token per tutte le
    righe) e una lambda non è serializzabile nelle migration."""
    return secrets.token_urlsafe(32)


class DocumentShare(TimestampedModel):
    """Un pacchetto di lettura, indirizzato a una persona, aperto da un token."""

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="link_documenti",
        verbose_name="immobile",
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        default=genera_token,
        editable=False,
        verbose_name="token",
    )
    destinatario = models.CharField(
        max_length=120,
        verbose_name="destinatario",
        help_text="A chi è indirizzato il link, es. «Simona Bagnato».",
    )
    tenant = models.ForeignKey(
        "properties.TenantProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="link_documenti",
        verbose_name="inquilino",
        help_text="Facoltativo: se il destinatario è già in anagrafica.",
    )
    introduzione = models.TextField(
        blank=True,
        verbose_name="introduzione",
        help_text="Due righe in cima alla pagina, prima delle voci.",
    )
    attivo = models.BooleanField(
        default=True,
        verbose_name="attivo",
        help_text="Tolto, il link smette di funzionare (revoca).",
    )
    visite = models.PositiveIntegerField(default=0, verbose_name="aperture")
    ultima_visita = models.DateTimeField(
        null=True, blank=True, verbose_name="ultima apertura"
    )
    creato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="link_documenti_creati",
        verbose_name="creato da",
    )

    class Meta:
        verbose_name = "link di lettura"
        verbose_name_plural = "link di lettura"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Link per {self.destinatario}"

    def clean(self):
        super().clean()
        if self.tenant_id and self.property_id:
            if self.tenant.property_id != self.property_id:
                raise ValidationError(
                    {"tenant": "L'inquilino è di un altro immobile."}
                )

    def voci_servibili(self):
        """Le voci che il link mostra davvero.

        Una voce il cui documento non è più ``esponibile`` sparisce: il
        controllo sta qui e non solo al momento di comporre, così togliere la
        spunta revoca il file anche nei link già mandati.
        """
        return [
            voce
            for voce in self.voci.select_related("documento").all()
            if voce.documento_id is None or voce.documento.esponibile
        ]


class ShareItem(TimestampedModel):
    """Una voce del pacchetto: o un documento esponibile, o un testo scritto
    a mano. Mai entrambi, mai nessuno dei due."""

    share = models.ForeignKey(
        DocumentShare,
        on_delete=models.CASCADE,
        related_name="voci",
        verbose_name="link",
    )
    ordine = models.PositiveIntegerField(default=0, verbose_name="ordine")
    titolo = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="titolo",
        help_text="Vuoto: si usa il titolo del documento.",
    )
    documento = models.ForeignKey(
        "properties.PropertyDocument",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="voci_link",
        verbose_name="documento",
    )
    corpo_md = models.TextField(
        blank=True,
        verbose_name="testo (markdown)",
        help_text="Chiarimento scritto a mano: quota condominio, utenze, scadenze.",
    )
    corpo_html = models.TextField(blank=True, editable=False)

    class Meta:
        verbose_name = "voce del link"
        verbose_name_plural = "voci del link"
        ordering = ["ordine", "id"]

    def __str__(self):
        return self.titolo or (str(self.documento) if self.documento_id else "Testo")

    @property
    def tipo(self):
        return "documento" if self.documento_id else "testo"

    @classmethod
    def valida_voce(cls, documento, corpo_md, share):
        """Messaggio d'errore se la voce è malformata, o None.

        Condivisa fra ``clean()`` e il serializer, come le altre validazioni
        di questa app.
        """
        ha_doc = documento is not None
        ha_testo = bool((corpo_md or "").strip())
        if ha_doc and ha_testo:
            return (
                "Una voce è un documento oppure un testo, non tutti e due: "
                "per accompagnare un allegato aggiungi una voce di testo a parte."
            )
        if not ha_doc and not ha_testo:
            return "Scegli un documento oppure scrivi un testo."
        if ha_doc:
            if share is not None and documento.property_id != share.property_id:
                return "Il documento è di un altro immobile."
            if not documento.esponibile:
                return (
                    "Quel documento non è esponibile in un link: usane una "
                    "copia per la lettura, o spuntalo come esponibile."
                )
        return None

    def clean(self):
        super().clean()
        errore = self.valida_voce(
            self.documento if self.documento_id else None,
            self.corpo_md,
            self.share if self.share_id else None,
        )
        if errore:
            raise ValidationError({"documento": errore})

    def save(self, *args, **kwargs):
        # L'HTML si rigenera a ogni salvataggio: il markdown è la fonte,
        # corpo_html è cache sanitizzata e non si edita a mano.
        self.corpo_html = rendi_markdown(self.corpo_md)
        super().save(*args, **kwargs)
