"""Endpoint DRF (JSON) per l'impersonation inquilini.

Wrappano django-hijack: le sue view native (``AcquireUserView`` /
``ReleaseUserView``) rispondono con un redirect HTML 302, inadatto a una SPA.
Qui riusiamo la stessa logica core (signal, backend di sessione, rotazione
chiave) ma restituiamo JSON.

Il vero gate di sicurezza e' ``puo_impersonare`` (vedi ``impersonation.py``):
- l'acquire richiede ``IsProprietario`` *e* supera ``puo_impersonare``;
- lo stop e' permesso a chiunque abbia una sessione impersonata
  (``request.user.is_hijacked``), perche' durante l'impersonation
  ``request.user`` e' l'inquilino.
"""
from django.contrib.auth import get_user_model, login
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from hijack import signals
from hijack.views import get_used_backend, keep_session_age

from .impersonation import puo_impersonare
from .permissions import IsProprietario


def _do_acquire(request, hijacked):
    """Replica AcquireUserView.post senza il redirect HTML."""
    hijacker = request.user
    hijack_history = request.session.get("hijack_history", [])
    hijack_history.append(hijacker._meta.pk.value_to_string(hijacker))

    backend = get_used_backend(request)
    backend = f"{backend.__module__}.{backend.__class__.__name__}"

    with signals.no_update_last_login(), keep_session_age(request.session):
        login(request, hijacked, backend=backend)

    request.session["hijack_history"] = hijack_history
    signals.hijack_started.send(
        sender=None, request=request, hijacker=hijacker, hijacked=hijacked,
    )


def _do_release(request):
    """Replica ReleaseUserView.post senza il redirect HTML."""
    hijack_history = request.session.get("hijack_history", [])
    hijacked = request.user
    user_pk = hijack_history.pop()
    hijacker = get_object_or_404(get_user_model(), pk=user_pk)

    backend = get_used_backend(request)
    backend = f"{backend.__module__}.{backend.__class__.__name__}"

    with signals.no_update_last_login(), keep_session_age(request.session):
        login(request, hijacker, backend=backend)

    request.session["hijack_history"] = hijack_history
    signals.hijack_ended.send(
        sender=None, request=request, hijacker=hijacker, hijacked=hijacked,
    )


@api_view(["POST"])
@permission_classes([IsProprietario])
def impersonate_view(request, tenant_id):
    """Inizia a impersonare l'inquilino col TenantProfile id dato."""
    from properties.models import TenantProfile

    target = get_object_or_404(
        TenantProfile.objects.select_related("user"), pk=tenant_id,
    )
    target_user = target.user
    if target_user is None or not puo_impersonare(request.user, target_user):
        return Response(
            {"detail": "Impersonation non consentita per questo inquilino."},
            status=status.HTTP_403_FORBIDDEN,
        )

    _do_acquire(request, target_user)
    return Response({"ok": True, "role": "inquilino", "redirect": "/i/"})


@api_view(["POST"])
def stop_impersonation_view(request):
    """Termina l'impersonation e ripristina il proprietario."""
    if not getattr(request.user, "is_hijacked", False):
        return Response(
            {"detail": "Nessuna impersonation attiva."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    _do_release(request)
    return Response({"ok": True, "role": "proprietario", "redirect": "/p/"})
