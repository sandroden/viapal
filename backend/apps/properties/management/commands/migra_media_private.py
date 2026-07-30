"""Sposta i file riservati da MEDIA_ROOT a MEDIA_PRIVATE_ROOT.

Da eseguire una volta in ogni ambiente (dev e prod) al deploy della feature
media-private. Idempotente: i file già spostati o mancanti vengono saltati.
In prod le due root sono bind-mount distinti: lo spostamento cross-device è
gestito da shutil.move (copia + rimozione).
"""
import os
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand

PREFISSI = ["documenti", "documenti-proprieta", "bollette", "ricevute", "spese"]


class Command(BaseCommand):
    help = (
        "Sposta i file riservati (documenti, documenti-proprieta, bollette, "
        "ricevute, spese) da MEDIA_ROOT a MEDIA_PRIVATE_ROOT. Idempotente. "
        "Con --dry-run mostra solo cosa farebbe."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Elenca gli spostamenti senza eseguirli.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        src_root = settings.MEDIA_ROOT
        dst_root = settings.MEDIA_PRIVATE_ROOT
        spostati = 0

        for prefisso in PREFISSI:
            src_dir = os.path.join(src_root, prefisso)
            if not os.path.isdir(src_dir):
                continue
            for dirpath, _dirnames, filenames in os.walk(src_dir):
                for nome in filenames:
                    src = os.path.join(dirpath, nome)
                    rel = os.path.relpath(src, src_root)
                    dst = os.path.join(dst_root, rel)
                    if os.path.exists(dst):
                        self.stdout.write(f"  esiste già, salto: {rel}")
                        continue
                    self.stdout.write(f"  {rel}")
                    if not dry_run:
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        shutil.move(src, dst)
                    spostati += 1
            if not dry_run:
                # ripulisce le directory rimaste vuote sotto MEDIA_ROOT
                # (bottom-up: rmdir fallisce senza danni su quelle non vuote)
                for dirpath, _dirnames, _filenames in os.walk(src_dir, topdown=False):
                    try:
                        os.rmdir(dirpath)
                    except OSError:
                        pass

        verbo = "da spostare" if dry_run else "spostati"
        self.stdout.write(self.style.SUCCESS(f"File {verbo}: {spostati}"))
