"""Copia in ``backend/media-demo/`` le foto che l'ambiente demo tiene vere.

Sono le sole immagini che ``anonimizza_demo`` non sostituisce con segnaposto:
foto della galleria pubblica, foto delle stanze e dell'immobile (hero,
planimetria, mappa). Vanno lette dallo storage di dev, che grazie al
``FallbackStorage`` di ``local.py`` le prende dal proxy S3 di produzione se
mancano in locale.

Si esegue in dev, con il db demo (``settings/dev.py`` legge VIAPAL_DB_NAME)::

    ENV=dev VIAPAL_DB_NAME=viapal_demo uv run python manage.py copia_media_demo

La destinazione e' sempre ``BASE_DIR/media-demo`` (mai lo storage in uso);
rifiuta di girare se il db non e' ``viapal_demo``. Idempotente: salta i file
gia' presenti (``--force`` li riscrive).
"""
from __future__ import annotations

from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from properties.anonimizza_demo import CAMPI_FOTO


class Command(BaseCommand):
    help = __doc__

    def create_parser(self, prog_name, subcommand, **kwargs):
        from argparse import RawDescriptionHelpFormatter
        kwargs.setdefault("formatter_class", RawDescriptionHelpFormatter)
        return super().create_parser(prog_name, subcommand, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="Riscrive anche i file gia' presenti in media-demo.")

    def handle(self, *args, **opts):
        nome_db = settings.DATABASES["default"]["NAME"]
        if nome_db != "viapal_demo":
            raise CommandError(
                f"Rifiuto: il db deve essere viapal_demo (attuale: {nome_db}). "
                "Usa ENV=dev VIAPAL_DB_NAME=viapal_demo.")
        dest = (Path(settings.BASE_DIR) / "media-demo").resolve()
        dest.mkdir(parents=True, exist_ok=True)
        copiati = saltati = 0
        mancanti = []
        for label, nome_campo in sorted(CAMPI_FOTO):
            model = apps.get_model(label)
            campo = model._meta.get_field(nome_campo)
            qs = model.objects.exclude(**{nome_campo: ""}).exclude(**{nome_campo + "__isnull": True})
            for nome in qs.values_list(nome_campo, flat=True):
                target = (dest / nome).resolve()
                if dest not in target.parents:
                    raise CommandError(f"Percorso fuori da media-demo: {nome}")
                if target.exists() and target.stat().st_size and not opts["force"]:
                    saltati += 1
                    continue
                try:
                    with campo.storage.open(nome, "rb") as src:
                        dati = src.read()
                except Exception as exc:  # noqa: BLE001 - si riporta e si prosegue
                    mancanti.append((label, nome, f"{type(exc).__name__}: {exc}"))
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(dati)
                copiati += 1
                self.stdout.write(f"  {nome} ({len(dati) // 1024} kB)")
        self.stdout.write(self.style.SUCCESS(
            f"Copiati {copiati}, gia' presenti {saltati}, mancanti {len(mancanti)} "
            f"in {dest}"))
        for label, nome, err in mancanti:
            self.stdout.write(self.style.ERROR(f"  MANCA {label}: {nome} ({err})"))
        if mancanti:
            raise CommandError("Alcuni file non sono stati trovati.")
