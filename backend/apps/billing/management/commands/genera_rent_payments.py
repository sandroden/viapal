"""
Management command per generare i Receivable affitto mensili.

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
            help="Sovrascrive i Receivable affitto esistenti (update_or_create invece di skip).",
        )
        parser.add_argument(
            "--property",
            type=str,
            default=None,
            help="Immobile (id o nome). Facoltativo: senza, genera per tutti gli immobili.",
        )

    def handle(self, *args, **options):
        anno = options["anno"]
        mese = options["mese"]
        force = options["force"]

        prop = None
        if options.get("property"):
            from properties.context import resolve_property_cli

            try:
                prop = resolve_property_cli(options["property"])
            except ValueError as e:
                raise CommandError(str(e)) from e

        if not (1 <= mese <= 12):
            raise CommandError(f"Mese non valido: {mese}. Usare un valore tra 1 e 12.")
        if anno < 2020:
            raise CommandError(f"Anno non plausibile: {anno}.")

        self.stdout.write(
            f"Generazione Receivable affitto per {anno}/{mese:02d}"
            + (" [FORCE]" if force else "")
            + (f" [immobile: {prop.nome}]" if prop else "")
        )

        try:
            from billing.calc.rent import genera_pagamenti_mese

            risultato = genera_pagamenti_mese(anno, mese, force=force, property=prop)
        except Exception as e:
            raise CommandError(f"Errore nella generazione: {e}") from e

        self.stdout.write("")
        self.stdout.write(f"  Creati:    {risultato['creati']}")
        self.stdout.write(f"  Aggiornati:{risultato['aggiornati']}")
        self.stdout.write(f"  Skippati:  {risultato['skippati']}")
        self.stdout.write(f"  ID creati: {risultato['payments']}")

        skippati_alloc = risultato.get("skippati_per_allocation", [])
        if skippati_alloc:
            self.stdout.write(
                self.style.WARNING(
                    f"\n[!] {len(skippati_alloc)} Receivable NON sovrascritti perché già allocati a transazioni bancarie:"
                )
            )
            for s in skippati_alloc:
                self.stdout.write(
                    self.style.WARNING(
                        f"    - {s['tenant_nominativo']}: "
                        f"esistente {s['importo_esistente']}€, calcolato {s['importo_calcolato']}€ "
                        f"(receivable_id={s['receivable_id']})"
                    )
                )
            self.stdout.write(
                self.style.WARNING(
                    "    Per correggere usa una rettifica manuale (Receivable extra) "
                    "anziché rilanciare il calcolo."
                )
            )

        totale = risultato["creati"] + risultato["aggiornati"]
        if totale > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nCompletato: {totale} Receivable affitto generati per {anno}/{mese:02d}."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"\nNessun Receivable affitto generato per {anno}/{mese:02d} "
                    f"(nessun assignment attivo o tutti gia' esistenti)."
                )
            )
