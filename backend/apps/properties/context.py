"""
Risoluzione della property "attiva" di una richiesta API.

Il client dichiara l'immobile su cui sta operando con l'header
``X-Property-Id`` (aggiunto una volta sola dall'interceptor axios).
In sua assenza — client non ancora multi-property — si usa l'unico
immobile a cui l'utente ha accesso (o il primo, in ordine di nome).

La membership dell'utente è SEMPRE verificata lato server: il valore
dell'header non è mai fidato.
"""
from __future__ import annotations

from rest_framework.exceptions import NotFound, PermissionDenied

from .models import Property

HEADER_PROPERTY = "X-Property-Id"


def resolve_property_cli(value: str | int | None) -> Property:
    """Risolve la property per i management command.

    ``value`` è l'opzione ``--property`` (id o nome, opzionale). Senza
    valore: se nel sistema c'è una sola property la usa, altrimenti
    esige l'opzione (niente più fallback silenziosi su ``first()``).
    """
    if value:
        qs = Property.objects.all()
        prop = qs.filter(pk=value).first() if str(value).isdigit() else None
        if prop is None:
            prop = qs.filter(nome__iexact=str(value)).first()
        if prop is None:
            raise ValueError(f"Immobile {value!r} non trovato.")
        return prop
    props = list(Property.objects.all()[:2])
    if len(props) == 1:
        return props[0]
    if not props:
        raise ValueError("Nessun immobile nel sistema.")
    raise ValueError(
        "Più immobili nel sistema: specificare --property <id o nome>."
    )


def properties_accessibili(user):
    """Queryset delle property a cui l'utente ha accesso (membership),
    ordinate per nome. I superuser accedono a tutte."""
    if not user or not user.is_authenticated:
        return Property.objects.none()
    if user.is_superuser:
        return Property.objects.all().order_by("nome")
    return Property.objects.filter(memberships__user=user).order_by("nome")


def get_request_property(request) -> Property:
    """La property attiva della richiesta, con membership verificata.

    - header presente: la property deve esistere ED essere accessibile
      all'utente (403 in caso contrario, per non rivelare l'esistenza);
    - header assente: fallback sulla prima property accessibile (il caso
      "utente con un solo immobile" resta trasparente);
    - nessuna property accessibile: 404.
    """
    accessibili = properties_accessibili(request.user)
    raw = request.headers.get(HEADER_PROPERTY)
    if raw:
        try:
            pk = int(raw)
        except (TypeError, ValueError):
            raise NotFound("Header X-Property-Id non valido.")
        prop = accessibili.filter(pk=pk).first()
        if prop is None:
            raise PermissionDenied("Nessun accesso a questo immobile.")
        return prop
    prop = accessibili.first()
    if prop is None:
        raise NotFound("Nessun immobile accessibile per questo utente.")
    return prop
