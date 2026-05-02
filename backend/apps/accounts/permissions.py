"""
Permission classes per il controllo accessi basato su gruppi.

Gruppi applicativi: 'proprietari', 'inquilini'.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


def _is_in_group(user, group_name: str) -> bool:
    """Verifica se l'utente (autenticato) appartiene al gruppo dato."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=group_name).exists()


class IsProprietario(BasePermission):
    """Consente l'accesso solo ai membri del gruppo 'proprietari'."""

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


class IsInquilinoSelf(BasePermission):
    """
    Object-level permission: l'inquilino può vedere solo oggetti che gli appartengono.

    Si aspetta che l'oggetto abbia un attributo 'tenant' di tipo TenantProfile
    con 'tenant.user'. I proprietari vedono tutto.
    """

    message = "Puoi accedere solo ai tuoi dati."

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if _is_in_group(request.user, "proprietari"):
            return True
        # Per gli inquilini: verifica che l'oggetto appartenga a loro
        tenant_user = self._get_tenant_user(obj)
        if tenant_user is None:
            return False
        return tenant_user == request.user

    def _get_tenant_user(self, obj):
        """Naviga la gerarchia per trovare l'utente dell'inquilino."""
        # Oggetti con .tenant (RoomAssignment, RentPayment.assignment.tenant, etc.)
        if hasattr(obj, "tenant"):
            return getattr(obj.tenant, "user", None)
        # Oggetti con .assignment.tenant (RentPayment, UtilityCharge, ExtraCharge)
        if hasattr(obj, "assignment") and hasattr(obj.assignment, "tenant"):
            return getattr(obj.assignment.tenant, "user", None)
        # Notifiche: .user diretto
        if hasattr(obj, "user"):
            return obj.user
        return None
