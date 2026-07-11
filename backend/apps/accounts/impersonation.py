"""Impersonation inquilini ("vedi come lui").

Gate di autorizzazione **centralizzato**: ``puo_impersonare`` e' l'unico punto
che decide se un utente puo' impersonarne un altro. Tutto il resto (endpoint
DRF, hook di django-hijack) delega qui.

Regole attuali:
- l'attore deve essere un *proprietario*: nel gruppo ``proprietari`` **oppure**
  superuser. Coerente con ``get_role`` e ``IsProprietario``, che trattano il
  superuser come proprietario (in locale Sandro opera con l'account ``admin``,
  superuser senza gruppo).
- il target deve essere *solo inquilino*: nel gruppo ``inquilini``, mai
  superuser ne' proprietario.

Multiproprieta': l'attore (non superuser) puo' impersonare solo gli
inquilini degli immobili di cui e' membro (``PropertyMembership``).
"""
from django.conf import settings


def _in_group(user, group_name: str) -> bool:
    return bool(user) and user.is_authenticated and \
        user.groups.filter(name=group_name).exists()


def puo_impersonare(actor_user, target_user) -> bool:
    """Ritorna True se ``actor_user`` puo' impersonare ``target_user``."""
    if not actor_user or not actor_user.is_authenticated:
        return False
    if not target_user or actor_user.pk == target_user.pk:
        return False

    # L'attore deve essere un proprietario: gruppo 'proprietari' o superuser
    # (come in get_role / IsProprietario).
    if not (actor_user.is_superuser or _in_group(actor_user, settings.ROLE_PROPRIETARI)):
        return False

    # Il target non puo' mai essere superuser o proprietario.
    if target_user.is_superuser:
        return False
    if _in_group(target_user, settings.ROLE_PROPRIETARI):
        return False

    # Il target deve essere un inquilino.
    if not _in_group(target_user, settings.ROLE_INQUILINI):
        return False

    # Un membro puo' impersonare solo inquilini dei propri immobili, e solo
    # con ruolo operativo (proprietario/gestore, non sola_lettura).
    # I superuser non hanno restrizioni (strumento di manutenzione).
    if actor_user.is_superuser:
        return True
    from properties.models import Property, PropertyMembership

    ruoli_operativi = [
        PropertyMembership.Ruolo.PROPRIETARIO,
        PropertyMembership.Ruolo.GESTORE,
    ]
    return Property.objects.filter(
        memberships__user=actor_user,
        memberships__ruolo__in=ruoli_operativi,
        tenants__user=target_user,
    ).exists()


def check_hijack_authorization(*, hijacker, hijacked) -> bool:
    """Hook per ``HIJACK_PERMISSION_CHECK`` (django-hijack 3.x).

    django-hijack chiama questa funzione con i keyword ``hijacker``/``hijacked``
    sia in fase di acquire (UserPassesTestMixin di AcquireUserView) sia,
    indirettamente, come riferimento condiviso col nostro endpoint.
    """
    return puo_impersonare(hijacker, hijacked)
