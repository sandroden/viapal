"""
Modelli relativi all'immobile: stanze, contratto, assegnazioni.
"""
from django.core.exceptions import ValidationError
from django.db import models

from ._base import TimestampedModel
from .owner import OwnerBankAccount, OwnerProfile
from .tenant import TenantProfile


class Property(TimestampedModel):
    """Immobile/abitazione che raggruppa le stanze.

    In ottica multi-immobile: ogni stanza appartiene a una Property, che porta
    il conto di domiciliazione su cui confluiscono le utenze dell'abitazione.
    """

    nome = models.CharField(
        max_length=120,
        verbose_name="nome",
    )
    indirizzo = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="indirizzo",
    )
    bank_account_utenze = models.ForeignKey(
        OwnerBankAccount,
        on_delete=models.PROTECT,
        related_name="properties_utenze",
        null=True,
        blank=True,
        verbose_name="conto domiciliazione utenze",
        help_text="Conto su cui gli inquilini versano le utenze/conguagli di questo immobile.",
    )
    owner_anticipa_cessioni = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="properties_anticipo_cessioni",
        null=True,
        blank=True,
        verbose_name="anticipa i costi di cessione",
        help_text=(
            "Proprietario che, per convenzione, anticipa il 50% dei costi "
            "di registrazione/cessione contratto di questo immobile."
        ),
    )

    class Meta:
        verbose_name = "immobile"
        verbose_name_plural = "immobili"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Room(TimestampedModel):
    """Stanza affittabile dell'appartamento."""

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="rooms",
        verbose_name="immobile",
    )
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
    """Contratto di locazione di un immobile.

    Storicamente "il contratto unico": oggi ogni immobile ha i propri
    contratti (di norma uno attivo per volta).
    """

    class RegimeFiscale(models.TextChoices):
        CEDOLARE_10 = "cedolare_10", "Cedolare secca 10%"
        CEDOLARE_21 = "cedolare_21", "Cedolare secca 21%"
        IRPEF = "irpef", "IRPEF ordinario"

    property = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="contracts",
        verbose_name="immobile",
    )
    nome = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="nome",
        help_text="Nome identificativo (es. 'Contratto 2023', 'Contratto 2025').",
    )
    data_stipula = models.DateField(
        verbose_name="data stipula",
    )
    data_decorrenza = models.DateField(
        verbose_name="data decorrenza",
    )
    termine = models.DateField(
        null=True,
        blank=True,
        verbose_name="termine",
        help_text=(
            "Data effettiva di chiusura del contratto (uscita anticipata). "
            "Diversa dalla scadenza naturale = data_decorrenza + durata_anni."
        ),
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
    default_pagatore_bollette = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="contratti_pagatore_bollette",
        null=True,
        blank=True,
        verbose_name="paga le bollette utenze",
        help_text=(
            "Proprietario che, per convenzione, anticipa il pagamento "
            "delle bollette luce/gas verso i fornitori."
        ),
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
        if self.nome:
            return self.nome
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
    bank_account_affitto = models.ForeignKey(
        OwnerBankAccount,
        on_delete=models.PROTECT,
        related_name="assignments_affitto",
        null=True,
        blank=True,
        verbose_name="conto incasso affitto",
        help_text=(
            "Override: conto su cui versare l'affitto di questa assegnazione. "
            "Se vuoto, si usa il conto della proprietà."
        ),
    )
    costo_cessione = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="costo cessione (totale)",
        help_text=(
            "Costo TOTALE della registrazione/cessione del contratto. Se "
            "valorizzato, alla data di inizio occupazione genera: il 50% come "
            "addebito all'inquilino entrante (Receivable 'registrazione') e il "
            "50% come spesa proprietari ripartita pro-quota. Lasciare vuoto "
            "per il contratto collettivo (nessun addebito)."
        ),
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
        self._valida_stessa_property()
        self._valida_no_overlap()

    def _valida_stessa_property(self):
        """La stanza e l'inquilino devono appartenere allo stesso immobile."""
        if not self.room_id or not self.tenant_id:
            return
        room_property_id = self.room.property_id
        tenant_property_id = self.tenant.property_id
        if (
            room_property_id
            and tenant_property_id
            and room_property_id != tenant_property_id
        ):
            raise ValidationError(
                "La stanza e l'inquilino appartengono a immobili diversi."
            )

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
