"""
Management command per generare i RentPayment mensili.

Uso:
    uv run manage.py genera_rent_payments --anno 2026 --mese 6
    uv run manage.py genera_rent_payments --anno 2026 --mese 6 --force
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Genera i pagamenti affitto per un mese specifico."

    def add_arguments(self, parser):
        parser.add_argument(
            "--anno",
            type=int,
            required=True,
            metavar="YYYY",
            help="Anno di competenza (es. 2026).",
        )
        parser.add_argument(
            "--mese",
            type=int,
            required=True,
            metavar="MM",
            help="Mese di competenza 1-12 (es. 6 per giugno).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Sovrascrive i RentPayment esistenti (update_or_create invece di skip).",
        )

    def handle(self, *args, **options):
        anno = options["anno"]
        mese = options["mese"]
        force = options["force"]

        if not (1 <= mese <= 12):
            raise CommandError(f"Mese non valido: {mese}. Usare un valore tra 1 e 12.")
        if anno < 2020:
            raise CommandError(f"Anno non plausibile: {anno}.")

        self.stdout.write(
            f"Generazione RentPayment per {anno}/{mese:02d}"
            + (" [FORCE]" if force else "")
        )

        try:
            from billing.calc.rent import genera_pagamenti_mese

            risultato = genera_pagamenti_mese(anno, mese, force=force)
        except Exception as e:
            raise CommandError(f"Errore nella generazione: {e}") from e

        self.stdout.write("")
        self.stdout.write(f"  Creati:    {risultato['creati']}")
        self.stdout.write(f"  Aggiornati:{risultato['aggiornati']}")
        self.stdout.write(f"  Skippati:  {risultato['skippati']}")
        self.stdout.write(f"  ID creati: {risultato['payments']}")

        totale = risultato["creati"] + risultato["aggiornati"]
        if totale > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nCompletato: {totale} RentPayment generati per {anno}/{mese:02d}."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"\nNessun RentPayment generato per {anno}/{mese:02d} "
                    f"(nessun assignment attivo o tutti gia' esistenti)."
                )
            )
