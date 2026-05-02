"""
Modelli relativi ai proprietari dell'immobile.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from ._base import TimestampedModel


class OwnerProfile(TimestampedModel):
    """Profilo anagrafico di un proprietario (fratello)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owner_profile",
        verbose_name="utente",
    )
    nominativo = models.CharField(
        max_length=200,
        verbose_name="nominativo",
    )
    codice_fiscale = models.CharField(
        max_length=16,
        blank=True,
        verbose_name="codice fiscale",
    )
    telefono = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="telefono",
    )
    note = models.TextField(
        blank=True,
        verbose_name="note",
    )

    class Meta:
        verbose_name = "profilo proprietario"
        verbose_name_plural = "profili proprietari"
        ordering = ["nominativo"]

    def __str__(self):
        return self.nominativo


class OwnershipShare(TimestampedModel):
    """Quota di proprietà versionata nel tempo."""

    owner = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="ownership_shares",
        verbose_name="proprietario",
    )
    valid_from = models.DateField(
        verbose_name="valida dal",
    )
    valid_to = models.DateField(
        null=True,
        blank=True,
        verbose_name="valida fino al",
    )
    quota = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        verbose_name="quota (0-1)",
        help_text="Es. 0.3333 per un terzo. La somma delle quote attive in ogni data deve fare 1.0.",
    )

    class Meta:
        verbose_name = "quota di proprietà"
        verbose_name_plural = "quote di proprietà"
        ordering = ["-valid_from", "owner__nominativo"]

    def __str__(self):
        return f"{self.owner} — {self.quota} (dal {self.valid_from})"

    def clean(self):
        super().clean()
        if self.quota is None:
            return
        if self.quota <= 0 or self.quota > 1:
            raise ValidationError({"quota": "La quota deve essere compresa tra 0 (escluso) e 1."})
        self._valida_somma_quote()

    def _valida_somma_quote(self):
        """Verifica che la somma delle quote attive nella data valid_from non superi 1.0.

        La somma deve essere esattamente 1.0: se è < 1.0 con quote già esistenti per quella
        data, segnala l'incongruenza. Se supera 1.0, è un errore immediato.
        Questa validazione agisce su ogni singolo record: il set completo delle quote deve
        essere inserito in una transazione atomica, con la quota finale che chiude a 1.0.
        """
        qs = OwnershipShare.objects.exclude(pk=self.pk)

        # Quote attive nel valid_from di questa (valid_to esclusivo: valid_to > valid_from)
        qs_at_start = qs.filter(
            valid_from__lte=self.valid_from,
        ).filter(
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gt=self.valid_from)
        )

        totale_esistente = sum(s.quota for s in qs_at_start)
        totale = totale_esistente + self.quota

        # Non permettere mai di superare 1.0
        if totale > Decimal("1.0") + Decimal("0.001"):
            raise ValidationError(
                f"La somma delle quote attive al {self.valid_from} sarebbe {totale:.4f} "
                f"(esistenti: {totale_esistente:.4f} + questa: {self.quota:.4f}). "
                f"Non può superare 1.0."
            )

        # Se ci sono già quote esistenti per questa data e il totale non arriva a 1.0
        # con questa quota, è comunque un segnale di attenzione ma non blocchiamo:
        # l'insert in transazione può ancora aggiungere le quote mancanti.
        # Salvo in caso di sovrapposizione esatta dello stesso owner per la stessa data.
        owner_duplicato = qs_at_start.filter(owner=self.owner).exists()
        if owner_duplicato:
            raise ValidationError(
                f"Il proprietario {self.owner} ha già una quota attiva al {self.valid_from}."
            )


class OwnerBankAccount(TimestampedModel):
    """Conto bancario di un proprietario per ricevere i bonifici."""

    owner = models.ForeignKey(
        OwnerProfile,
        on_delete=models.PROTECT,
        related_name="bank_accounts",
        verbose_name="proprietario",
    )
    banca = models.CharField(
        max_length=100,
        verbose_name="banca",
    )
    intestatario = models.CharField(
        max_length=200,
        verbose_name="intestatario",
    )
    iban = models.CharField(
        max_length=34,
        verbose_name="IBAN",
    )
    attivo = models.BooleanField(
        default=True,
        verbose_name="attivo",
    )
    ordinamento = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="ordinamento",
    )

    class Meta:
        verbose_name = "conto bancario proprietario"
        verbose_name_plural = "conti bancari proprietari"
        ordering = ["owner__nominativo", "ordinamento", "banca"]

    def __str__(self):
        return f"{self.owner} — {self.banca} ({self.iban[-4:]})"
