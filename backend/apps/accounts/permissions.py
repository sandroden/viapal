"""
Permission classes per il controllo accessi.

Due livelli:
- gruppi Django 'proprietari'/'inquilini' → selettore d'area UI (/p/ vs /i/);
- ``PropertyMembership`` → autorizzazione vera, per-immobile (multiproprietà).

Le classi property-aware risolvono l'immobile della richiesta con
``properties.context.get_request_property`` (header X-Property-Id validato,
o unico immobile accessibile) e decidono in base al ruolo di membership.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


def _is_in_group(user, group_name: str) -> bool:
    """Verifica se l'utente (autenticato) appartiene al gruppo dato."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=group_name).exists()


def _property_id_of(obj):
    """Risale all'id della Property di un oggetto di dominio, se esiste."""
    direct = getattr(obj, "property_id", None)
    if direct:
        return direct
    immobile = getattr(obj, "immobile_id", None)
    if immobile:
        return immobile
    assignment = getattr(obj, "assignment", None)
    if assignment is not None:
        return assignment.room.property_id
    room = getattr(obj, "room", None)
    if room is not None:
        return room.property_id
    tenant = getattr(obj, "tenant", None)
    if tenant is not None:
        return tenant.property_id
    return None


class IsProprietario(BasePermission):
    """Consente l'accesso solo ai membri del gruppo 'proprietari'.

    Gate d'area legacy: per gli endpoint di dominio usare le classi
    property-aware qui sotto.
    """

    message = "Accesso riservato ai proprietari."

    def has_permission(self, request, view):
        return _is_in_group(request.user, "proprietari")


class IsInquilino(BasePermission):
    """Consente l'accesso solo ai membri del gruppo 'inquilini'."""

    message = "Accesso riservato agli inquilini."

    def has_permission(self, request, view):
        return _is_in_group(request.user, "inquilini")


class IsProprietarioOrReadOnly(BasePermission):
    """
    Lettura per tutti gli utenti autenticati.
    Scrittura (POST/PUT/PATCH/DELETE) solo per i proprietari.
    """

    message = "Scrittura riservata ai proprietari."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return _is_in_group(request.user, "proprietari")


class IsPropertyMember(BasePermission):
    """Membro dell'immobile attivo della richiesta, qualsiasi ruolo.

    Il ruolo 'sola_lettura' è limitato ai metodi safe. La risoluzione
    dell'immobile (header X-Property-Id o unico accessibile) valida già
    la membership: qui aggiungiamo solo il vincolo sul ruolo.
    """

    message = "Accesso riservato ai membri dell'immobile."

    def has_permission(self, request, view):
        from rest_framework.exceptions import NotFound

        from properties.context import get_request_property, ruolo_su_property
        from properties.models import PropertyMembership

        user = request.user
        if not user or not user.is_authenticated:
            return False
        try:
            prop = get_request_property(request)
        except NotFound:
            # Nessun immobile accessibile (es. inquilino): permesso negato,
            # non "risorsa inesistente".
            return False
        ruolo = ruolo_su_property(user, prop)
        if ruolo is None:
            return False
        if (
            ruolo == PropertyMembership.Ruolo.SOLA_LETTURA
            and request.method not in SAFE_METHODS
        ):
            return False
        return True


class IsPropertyProprietario(BasePermission):
    """Solo ruolo 'proprietario' sull'immobile attivo (gestione membri,
    quote, cancellazione immobile)."""

    message = "Operazione riservata ai proprietari dell'immobile."

    def has_permission(self, request, view):
        from rest_framework.exceptions import NotFound

        from properties.context import get_request_property, ruolo_su_property
        from properties.models import PropertyMembership

        user = request.user
        if not user or not user.is_authenticated:
            return False
        try:
            prop = get_request_property(request)
        except NotFound:
            return False
        return ruolo_su_property(user, prop) == PropertyMembership.Ruolo.PROPRIETARIO


class IsInquilinoSelf(BasePermission):
    """
    Object-level permission: l'inquilino può vedere solo oggetti che gli
    appartengono; lato gestione, un utente vede solo gli oggetti degli
    immobili di cui è membro.
    """

    message = "Puoi accedere solo ai tuoi dati."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        # Membri dell'immobile dell'oggetto: accesso pieno.
        prop_id = _property_id_of(obj)
        if prop_id and user.property_memberships.filter(property_id=prop_id).exists():
            return True
        # Per gli inquilini: verifica che l'oggetto appartenga a loro.
        tenant_user = self._get_tenant_user(obj)
        if tenant_user is None:
            return False
        return tenant_user == user

    def _get_tenant_user(self, obj):
        """Naviga la gerarchia per trovare l'utente dell'inquilino."""
        # Oggetti con .tenant (RoomAssignment, TenantDocument, etc.)
        if hasattr(obj, "tenant"):
            return getattr(obj.tenant, "user", None)
        # Oggetti con .assignment.tenant (Receivable)
        if hasattr(obj, "assignment") and hasattr(obj.assignment, "tenant"):
            return getattr(obj.assignment.tenant, "user", None)
        # Notifiche: .user diretto
        if hasattr(obj, "user"):
            return obj.user
        return None
