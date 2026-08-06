"""Storage dei media privati.

I file riservati (documenti identità, documenti immobile, bollette,
ricevute, spese) vivono in ``MEDIA_PRIVATE_ROOT`` e sono serviti SOLO dalla
vista autenticata ``/media-private/`` (``core.media_private``), mai come
statici.
"""
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage, storages


class MediaPrivateStorage(FileSystemStorage):
    """FileSystemStorage su MEDIA_PRIVATE_ROOT / MEDIA_PRIVATE_URL.

    location e base_url sono risolti dai settings a ogni accesso (property,
    non cached_property): così ``override_settings(MEDIA_PRIVATE_ROOT=...)``
    nei test funziona.
    """

    @property
    def base_location(self):
        return settings.MEDIA_PRIVATE_ROOT

    @property
    def location(self):
        return os.path.abspath(settings.MEDIA_PRIVATE_ROOT)

    @property
    def base_url(self):
        return settings.MEDIA_PRIVATE_URL


def media_private_storage():
    """Callable per ``FileField(storage=...)``: nelle migrazioni viene
    serializzato per riferimento, senza congelare location/URL.

    Risolve l'alias ``STORAGES["private"]`` (default: MediaPrivateStorage),
    che in dev può essere un ``jmb.core`` FallbackStorage con i media di
    produzione come fallback read-only (vedi local.py.example)."""
    return storages["private"]
