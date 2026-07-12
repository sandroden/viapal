"""
Membership: chi può accedere e gestire una Property, e con quale ruolo.

Separa il diritto di accesso/gestione dalla titolarità economica
(``OwnershipShare``): un ``gestore`` amministra un immobile senza avere
quota di proprietà e senza partecipare ai riparti pro-quota e ai saldi
fra proprietari (es. Sandro sull'appartamento della moglie).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from ._base import TimestampedModel
from .property import Property


class PropertyMembership(TimestampedModel):
    """Accesso di un utente a un immobile con un ruolo."""

    class Ruolo(models.TextChoices):
        PROPRIETARIO = "proprietario", "Proprietario"
        GESTORE = "gestore", "Gestore"
        SOLA_LETTURA = "sola_lettura", "Sola lettura"

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="immobile",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="property_memberships",
        verbose_name="utente",
    )
    ruolo = models.CharField(
        max_length=20,
        choices=Ruolo.choices,
        default=Ruolo.PROPRIETARIO,
        verbose_name="ruolo",
        help_text=(
            "Proprietario: gestione piena e partecipazione economica. "
            "Gestore: gestione piena ma nessuna quota né partecipazione "
            "ai riparti. Sola lettura: consultazione (es. commercialista)."
        ),
    )
    invitato_da = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memberships_invitate",
        verbose_name="invitato da",
    )

    class Meta:
        verbose_name = "membro immobile"
        verbose_name_plural = "membri immobili"
        ordering = ["property__nome", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "user"],
                name="property_membership_unique",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.property} ({self.get_ruolo_display()})"

    def clean(self):
        super().clean()
        # Un utente-inquilino non può essere anche membro lato gestione
        # della stessa property in cui affitta: ruoli confusi.
        if (
            self.user_id
            and self.property_id
            and hasattr(self.user, "tenant_profile")
            and self.user.tenant_profile.property_id == self.property_id
        ):
            raise ValidationError(
                "L'utente è inquilino di questo immobile: non può esserne "
                "anche membro di gestione."
            )


def user_property_ids(user) -> list[int]:
    """ID delle property a cui l'utente ha accesso (qualsiasi ruolo).

    I superuser hanno accesso a tutte le property (strumento di
    manutenzione, coerente con l'admin Django).
    """
    if not user or not user.is_authenticated:
        return []
    if user.is_superuser:
        return list(Property.objects.values_list("id", flat=True))
    return list(user.property_memberships.values_list("property_id", flat=True))
