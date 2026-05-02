"""
Modelli relativi all'immobile: stanze, contratto, assegnazioni.
"""
from django.core.exceptions import ValidationError
from django.db import models

from ._base import TimestampedModel
from .owner import OwnerProfile
from .tenant import TenantProfile


class Room(TimestampedModel):
    """Stanza affittabile dell'appartamento."""

    nome = models.CharField(
        max_length=100,
        verbose_name="nome",
    )
    superficie_mq = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="superficie (mq)",
    )
    foto = models.ImageField(
        upload_to="rooms/",
        null=True,
        blank=True,
        verbose_name="foto",
    )
    ordinamento = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="ordinamento",
    )

    class Meta:
        verbose_name = "stanza"
        verbose_name_plural = "stanze"
        ordering = ["ordinamento", "nome"]

    def __str__(self):
        return self.nome


class Contract(TimestampedModel):
    """Il contratto unico di locazione (un solo record attivo)."""

    class RegimeFiscale(models.TextChoices):
        CEDOLARE_10 = "cedolare_10", "Cedolare secca 10%"
        CEDOLARE_21 = "cedolare_21", "Cedolare secca 21%"
        IRPEF = "irpef", "IRPEF ordinario"

    data_stipula = models.DateField(
        verbose_name="data stipula",
    )
    data_decorrenza = models.DateField(
        verbose_name="data decorrenza",
    )
    durata_anni = models.PositiveSmallIntegerField(
        verbose_name="durata (anni)",
    )
    asseverato = models.BooleanField(
        default=False,
        verbose_name="asseverato",
    )
    regime_fiscale = models.CharField(
        max_length=20,
        choices=RegimeFiscale.choices,
        default=RegimeFiscale.CEDOLARE_10,
        verbose_name="regime fiscale",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "contratto"
        verbose_name_plural = "contratti"
        ordering = ["-data_decorrenza"]

    def __str__(self):
        return f"Contratto dal {self.data_decorrenza} ({self.get_regime_fiscale_display()})"


class RoomAssignment(TimestampedModel):
    """Periodo di occupazione di una stanza da parte di un inquilino."""

    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="assignments",
        verbose_name="stanza",
    )
    tenant = models.ForeignKey(
        TenantProfile,
        on_delete=models.PROTECT,
        related_name="assignments",
        verbose_name="inquilino",
    )
    valid_from = models.DateField(
        verbose_name="inizio occupazione",
    )
    valid_to = models.DateField(
        null=True,
        blank=True,
        verbose_name="fine occupazione",
    )
    canone_mensile = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="canone mensile",
    )
    deposito_versato = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="deposito versato",
    )
    deposito_restituito = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="deposito restituito",
    )
    data_restituzione_deposito = models.DateField(
        null=True,
        blank=True,
        verbose_name="data restituzione deposito",
    )
    data_atto_cessione = models.DateField(
        null=True,
        blank=True,
        verbose_name="data atto cessione",
        help_text="Valorizzato se l'occupazione è iniziata con una cessione registrata.",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "assegnazione stanza"
        verbose_name_plural = "assegnazioni stanze"
        ordering = ["-valid_from", "room__nome"]
        constraints = [
            # Non è possibile avere two assignments sovrapposti per la stessa stanza.
            # Il vincolo viene anche verificato in clean() per messaggi d'errore chiari.
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=models.F("valid_from")),
                name="room_assignment_valid_to_after_valid_from",
            )
        ]

    def __str__(self):
        to = f" → {self.valid_to}" if self.valid_to else " → in corso"
        return f"{self.room} / {self.tenant} ({self.valid_from}{to})"

    def clean(self):
        super().clean()
        if self.valid_to and self.valid_to <= self.valid_from:
            raise ValidationError(
                {"valid_to": "La data di fine occupazione deve essere successiva alla data di inizio."}
            )
        self._valida_no_overlap()

    def _valida_no_overlap(self):
        """Verifica che non ci siano assegnazioni sovrapposte per la stessa stanza."""
        if not self.room_id or not self.valid_from:
            return

        qs = RoomAssignment.objects.filter(room=self.room_id).exclude(pk=self.pk)

        # Un'assegnazione esistente si sovrappone se:
        # inizia prima della fine di questa E finisce dopo l'inizio di questa
        for assignment in qs:
            a_from = assignment.valid_from
            a_to = assignment.valid_to  # None = ancora aperta

            # questa inizia prima della fine dell'esistente?
            this_to = self.valid_to

            # overlap: not (this_to <= a_from or a_to <= this_from)
            # ovvero: this_from < a_to AND a_from < this_to
            # con None = infinito
            this_ends_after_a_starts = True  # this_from < a_to (a_to None = inf)
            if a_to is not None and self.valid_from >= a_to:
                this_ends_after_a_starts = False

            a_starts_before_this_ends = True  # a_from < this_to (this_to None = inf)
            if this_to is not None and a_from >= this_to:
                a_starts_before_this_ends = False

            if this_ends_after_a_starts and a_starts_before_this_ends:
                raise ValidationError(
                    f"Sovrapposizione con l'assegnazione esistente: {assignment} "
                    f"(dal {a_from} al {a_to or 'in corso'})."
                )
