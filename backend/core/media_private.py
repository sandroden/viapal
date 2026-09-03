"""Serving autenticato dei media privati: ``/media-private/<path>``.

L'autorizzazione non si basa sul parsing del path ma sul record che
possiede il file: il path viene cercato per match esatto nel FileField del
modello corrispondente al primo segmento. Se nessun record lo referenzia,
404. Prefissi sconosciuti: 404 (fail-safe).

Matrice di accesso (oltre al superuser, che passa sempre via
``user_property_ids``):

- ``documenti/`` (TenantDocument): l'inquilino stesso; i membri della
  proprietà dell'inquilino.
- ``documenti-proprieta/`` (PropertyDocument): i membri della proprietà;
  se ``visibile_inquilini``, anche gli inquilini della proprietà — ma se il
  documento è collegato a un contratto, solo quelli la cui assegnazione sta
  sotto quel contratto, e mai le copie oscurate (``copia_di``). Chi
  apre un link di lettura non passa di qui: ha una vista sua
  (``PublicShareFileView``), autorizzata dal token.
- ``bollette/`` (UtilityBill): membri e inquilini dell'immobile (le
  bollette sono mostrate agli inquilini in /i/utenze).
- ``ricevute/`` (Receivable.ricevuta): l'inquilino dell'assegnazione;
  i membri della proprietà.
- ``spese/`` (Expense.allegato): solo i membri della proprietà.
"""
import logging
import posixpath

from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404

from core.storages import media_private_storage

logger = logging.getLogger("viapal.media_private")


def _tenant_property_id(user):
    """Property dell'inquilino collegato all'utente, o None."""
    profilo = getattr(user, "tenant_profile", None)
    return profilo.property_id if profilo else None


def _autorizza_documento_inquilino(user, path, property_ids):
    from properties.models import TenantDocument

    doc = TenantDocument.objects.select_related("tenant").filter(file=path).first()
    if doc is None:
        raise Http404
    return doc.tenant.user_id == user.id or doc.tenant.property_id in property_ids


def _autorizza_documento_proprieta(user, path, property_ids):
    from properties.models import PropertyDocument, RoomAssignment

    doc = PropertyDocument.objects.filter(file=path).first()
    if doc is None:
        raise Http404
    if doc.property_id in property_ids:
        return True
    if not doc.visibile_inquilini:
        return False
    # Una copia oscurata non è per chi ha già l'originale: fuori dalla
    # lista API e fuori anche di qui, che è la porta che conta con l'URL in
    # mano. Ai membri resta accessibile (è un documento dell'immobile).
    if doc.copia_di_id:
        return False
    profilo = getattr(user, "tenant_profile", None)
    if profilo is None or profilo.property_id != doc.property_id:
        return False
    if doc.contract_id is None:
        return True
    # Carta di un contratto: la vede solo chi ci sta dentro. Il filtro sta
    # anche nella lista API, ma qui è quello che conta — con l'URL in mano
    # si scaricherebbe comunque.
    # Una rinuncia non è "starci dentro": chi non è mai entrato non vede le
    # carte del contratto.
    return RoomAssignment.objects.filter(
        tenant=profilo, contract_id=doc.contract_id, rinunciata=False
    ).exists()


def _autorizza_bolletta(user, path, property_ids):
    from billing.models import UtilityBill

    bolletta = UtilityBill.objects.filter(file_pdf=path).first()
    if bolletta is None:
        raise Http404
    return (
        bolletta.immobile_id in property_ids
        or _tenant_property_id(user) == bolletta.immobile_id
    )


def _autorizza_ricevuta(user, path, property_ids):
    from billing.models import Receivable

    receivable = (
        Receivable.objects.select_related("assignment__tenant")
        .filter(ricevuta=path)
        .first()
    )
    if receivable is None:
        raise Http404
    tenant = receivable.assignment.tenant
    return tenant.user_id == user.id or tenant.property_id in property_ids


def _autorizza_spesa(user, path, property_ids):
    from billing.models import Expense

    spesa = Expense.objects.filter(allegato=path).first()
    if spesa is None:
        raise Http404
    return spesa.property_id in property_ids


_RESOLVERS = {
    "documenti": _autorizza_documento_inquilino,
    "documenti-proprieta": _autorizza_documento_proprieta,
    "bollette": _autorizza_bolletta,
    "ricevute": _autorizza_ricevuta,
    "spese": _autorizza_spesa,
}


def media_private_view(request, path):
    from properties.models import user_property_ids

    if not request.user.is_authenticated:
        raise PermissionDenied("Autenticazione richiesta.")

    path = posixpath.normpath(path).lstrip("/")
    resolver = _RESOLVERS.get(path.split("/", 1)[0])
    if resolver is None:
        raise Http404

    property_ids = set(user_property_ids(request.user))
    if not resolver(request.user, path, property_ids):
        logger.warning("negato user=%s path=%s", request.user, path)
        raise PermissionDenied("Non hai accesso a questo file.")

    storage = media_private_storage()
    if not storage.exists(path):
        raise Http404

    logger.info("download user=%s path=%s", request.user, path)
    return FileResponse(storage.open(path, "rb"), filename=posixpath.basename(path))
