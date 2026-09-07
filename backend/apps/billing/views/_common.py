"""
Helper e costanti condivisi dai moduli del package ``billing.views``.
"""

from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response


class BillingPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 200


def _is_proprietario(user) -> bool:
    """Lato gestione: superuser o membro di almeno un immobile."""
    return user.is_superuser or user.property_memberships.exists()


def _is_inquilino(user) -> bool:
    return user.groups.filter(name="inquilini").exists()


def _valida_conto_incasso(owner_account, prop) -> Response | None:
    """``None`` se il conto è in uso sull'immobile, altrimenti la Response 403.

    Il denaro può entrare solo su un conto collegato all'immobile: è il
    collegamento su cui poggia l'isolamento dei movimenti fra immobili.
    """
    from properties.models import OwnerBankAccount

    in_uso = (
        OwnerBankAccount.objects.per_property(prop)
        .filter(pk=owner_account.pk)
        .exists()
    )
    if in_uso:
        return None
    return Response(
        {"detail": "Conto non in uso su questo immobile."},
        status=status.HTTP_403_FORBIDDEN,
    )
