"""Lead: una persona che cerca stanza, trovata dal bot in un gruppo Facebook.

Non è anagrafica. È lo stato di una **campagna** di ricerca inquilini: dura le
due settimane in cui le stanze sono sfitte, poi si cancella (azione "chiudi
campagna"). Il bot che li produce vive fuori da questo repo (worktree
``viapal-bot/bot``); qui arrivano già classificati, via bulk-upsert.

Il modello ha due metà con proprietari diversi, ed è l'invariante da non
rompere:

* i campi **del bot** (testo, autore, permalink, analisi, messaggi proposti)
  vengono riscritti a ogni upsert dello stesso post;
* i campi **di lavorazione** (stato, preso_da, note, foto) sono degli umani e
  l'upsert non li tocca mai — altrimenti il secondo passaggio dello scraper
  sullo stesso post azzererebbe il flag di chi ha già scritto alla persona.

La separazione è realizzata da due serializer distinti (``serializers.py``):
quello del bot non sa nemmeno nominare i campi umani, e viceversa.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from properties.models import TimestampedModel

# Un francobollo da 128px in WebP sta in pochi KB; il tetto è largo dieci
# volte tanto e serve solo a impedire che il campo diventi un deposito di file.
FOTO_MAX_CARATTERI = 100_000
FOTO_PREFISSI = (
    "data:image/webp;base64,",
    "data:image/jpeg;base64,",
    "data:image/png;base64,",
)


def valida_fotina(valore):
    """La fotina è un data URI, non un file e non un link a un CDN altrui.

    Il ridimensionamento avviene nel browser, ma un PATCH arriva anche da
    curl: senza questo controllo il campo sarebbe un TextField illimitato
    scrivibile da chiunque abbia accesso all'immobile.
    """
    if not valore:
        return
    if not valore.startswith(FOTO_PREFISSI):
        raise ValidationError(
            "La foto dev'essere un'immagine incollata (data URI webp, jpeg o png)."
        )
    if len(valore) > FOTO_MAX_CARATTERI:
        raise ValidationError("La foto è troppo grande: serve un francobollo, non un file.")


class Lead(TimestampedModel):
    """Un post "cerco stanza" giudicato compatibile con le stanze libere."""

    class Stato(models.TextChoices):
        NUOVO = "nuovo", "Da contattare"
        CONTATTATO = "contattato", "Contattato"
        RISPOSTO = "risposto", "Ha risposto"
        SCARTATO = "scartato", "Scartato"

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="leads",
        verbose_name="immobile",
    )

    # --- identità -------------------------------------------------------
    post_id = models.CharField(
        max_length=64,
        verbose_name="id del post",
        help_text="Id Facebook del post: chiave naturale dell'upsert.",
    )
    group_id = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="id del gruppo",
        help_text=(
            "Gruppo in cui il post è stato trovato. Lo sa lo scraper (è il "
            "gruppo che sta scorrendo), non si ricava dal permalink: quello "
            "a volte manca. Serve quando i gruppi monitorati saranno più d'uno."
        ),
    )
    group_label = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="nome del gruppo",
    )

    # --- campi del bot --------------------------------------------------
    author_name = models.CharField(max_length=200, blank=True, verbose_name="autore")
    author_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="profilo dell'autore",
        help_text="Usato anche dal bot per non ricontattare chi ripubblica.",
    )
    permalink = models.URLField(max_length=500, blank=True, verbose_name="link al post")
    link_messenger = models.URLField(
        max_length=500, blank=True, verbose_name="link a Messenger"
    )
    testo = models.TextField(blank=True, verbose_name="testo del post")
    analisi = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="analisi",
        help_text=(
            "Esito del classificatore: zona, budget_max, disponibile_da, "
            "stanze_compatibili (id di configurazione del bot, non Room), motivo."
        ),
    )
    commento_proposto = models.TextField(
        blank=True,
        verbose_name="commento pubblico proposto",
        help_text="Testo da incollare sotto il post.",
    )
    privato_proposto = models.TextField(
        blank=True,
        verbose_name="messaggio privato proposto",
        help_text="Testo da incollare su Messenger.",
    )
    seen_at = models.DateTimeField(
        verbose_name="visto il",
        help_text="Quando il bot ha incontrato il post.",
    )

    # --- lavorazione (solo umani) ---------------------------------------
    stato = models.CharField(
        max_length=12,
        choices=Stato.choices,
        default=Stato.NUOVO,
        verbose_name="stato",
    )
    preso_da = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads_presi",
        verbose_name="preso in carico da",
        help_text="Chi se ne occupa: evita che in due si scriva alla stessa persona.",
    )
    preso_at = models.DateTimeField(null=True, blank=True, verbose_name="preso in carico il")
    contattato_at = models.DateTimeField(null=True, blank=True, verbose_name="contattato il")
    note = models.TextField(blank=True, verbose_name="note")
    foto = models.TextField(
        blank=True,
        validators=[valida_fotina],
        verbose_name="fotina",
        help_text=(
            "Ritaglio del profilo, incollato a mano per riconoscere la persona "
            "in mezzo agli annunci. Sta nella tabella e non su disco di "
            "proposito: la chiusura campagna cancella i lead in blocco, e un "
            "file su storage sopravviverebbe alla cancellazione promessa."
        ),
    )

    class Meta:
        verbose_name = "lead"
        verbose_name_plural = "lead"
        ordering = ["-seen_at"]
        constraints = [
            # Unico per immobile, non globalmente: due immobili che pescano
            # dallo stesso gruppo devono poter lavorare lo stesso post, ognuno
            # con la propria presa in carico.
            models.UniqueConstraint(
                fields=["property", "post_id"],
                name="lead_post_id_unique_per_property",
            ),
        ]
        indexes = [
            models.Index(fields=["property", "stato"]),
            models.Index(fields=["author_url"]),
        ]

    def __str__(self):
        return f"{self.author_name or 'anonimo'} — {self.get_stato_display()}"
