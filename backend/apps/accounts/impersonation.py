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

FUTURO multiproprieta': quando gli inquilini saranno legati a una ``Property``
(e ad alcuni proprietari), bastera' aggiungere qui il filtro che limita ogni
proprietario agli inquilini delle proprie proprieta'. Vedi il commento nel
corpo della funzione.
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

    # FUTURO multiproprieta': limitare agli inquilini delle proprieta'
    # dell'attore, es.:
    #   from properties.models import Property
    #   return Property.objects.filter(
    #       owners__user=actor_user,
    #       rooms__assignments__tenant__user=target_user,
    #   ).exists()
    return True


def check_hijack_authorization(*, hijacker, hijacked) -> bool:
    """Hook per ``HIJACK_PERMISSION_CHECK`` (django-hijack 3.x).

    django-hijack chiama questa funzione con i keyword ``hijacker``/``hijacked``
    sia in fase di acquire (UserPassesTestMixin di AcquireUserView) sia,
    indirettamente, come riferimento condiviso col nostro endpoint.
    """
    return puo_impersonare(hijacker, hijacked)
