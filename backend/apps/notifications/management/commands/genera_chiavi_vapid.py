"""Genera una coppia di chiavi VAPID per le notifiche Web Push.

La chiave pubblica va sia nel backend (VAPID_PUBLIC_KEY, esposta al frontend
per pushManager.subscribe) sia la privata (VAPID_PRIVATE_KEY) che firma il
JWT verso il push service. Formato: base64url senza padding, quello atteso
da pywebpush e dal browser.

Uso:
  ENV=dev uv run manage.py genera_chiavi_vapid
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class Command(BaseCommand):
    help = "Genera una coppia di chiavi VAPID (base64url) per il Web Push."

    def handle(self, *args, **opts):
        key = ec.generate_private_key(ec.SECP256R1())
        private = _b64url(
            key.private_numbers().private_value.to_bytes(32, "big")
        )
        public = _b64url(
            key.public_key().public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            )
        )
        self.stdout.write("Aggiungi all'ambiente (o a local.py in prod):\n")
        self.stdout.write(f"VAPID_PRIVATE_KEY={private}")
        self.stdout.write(f"VAPID_PUBLIC_KEY={public}")
