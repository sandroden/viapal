"""
Management command per calcolare (e opzionalmente persistere) il conguaglio
di un UtilityChargePeriod.

Uso:
    uv run manage.py calcola_conguaglio --period-id N
    uv run manage.py calcola_conguaglio --period-id N --persist
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Calcola la ripartizione utenze per un UtilityChargePeriod."

    def add_arguments(self, parser):
        parser.add_argument(
            "--period-id",
            type=int,
            required=True,
            metavar="N",
            help="ID del UtilityChargePeriod da calcolare.",
        )
        parser.add_argument(
            "--persist",
            action="store_true",
            default=False,
            help="Crea/aggiorna Receivable(causale=utenze) e righe nel database.",
        )

    def handle(self, *args, **options):
        period_id = options["period_id"]
        persist = options["persist"]

        self.stdout.write(
            f"Calcolo conguaglio per period_id={period_id}"
            + (" [PERSIST]" if persist else " [dry-run]")
        )

        try:
            from billing.calc.utility import calcola_conguaglio_periodo

            risultato = calcola_conguaglio_periodo(period_id, persist=persist)
        except Exception as e:
            raise CommandError(f"Errore nel calcolo: {e}") from e

        self.stdout.write("")
        self.stdout.write(
            f"Periodo: {risultato['periodo_da']} / {risultato['periodo_a']}"
        )
        self.stdout.write(
            f"Totale periodo: {risultato['totale_periodo']}€"
        )
        self.stdout.write("Totali per voce:")
        for voce, importo in risultato["totali_per_voce"].items():
            self.stdout.write(f"  {voce:10s}: {importo:>8}€")

        self.stdout.write(
            f"Giorni presenza totali: {risultato['sum_giorni_presenza']}"
        )
        self.stdout.write("")
        self.stdout.write("Quote per inquilino:")
        self.stdout.write(f"  {'Nominativo':<30} {'Giorni':>8} {'Quota':>8}")
        self.stdout.write("  " + "-" * 50)
        for q in risultato["quote"]:
            self.stdout.write(
                f"  {q['tenant_nominativo']:<30} {q['giorni_presenza']:>8} {q['quota']:>7}€"
            )
            for voce, importo in q["dettaglio"].items():
                self.stdout.write(f"    └─ {voce}: {importo}€")

        self.stdout.write("")
        diff = risultato["diff_arrotondamento"]
        if diff != 0:
            self.stdout.write(
                self.style.WARNING(f"Diff arrotondamento: {diff}€")
            )
        else:
            self.stdout.write("Diff arrotondamento: 0.00€ (perfetto)")

        if persist:
            skippati = risultato.get("skippati_per_allocation", [])
            n_persistiti = len(risultato["quote"]) - len(skippati)
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nConguaglio persistito: {n_persistiti} addebiti utenze creati/aggiornati."
                )
            )
            if skippati:
                self.stdout.write(
                    self.style.WARNING(
                        f"\n[!] {len(skippati)} addebiti NON aggiornati perché già allocati a transazioni bancarie:"
                    )
                )
                for s in skippati:
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
        else:
            self.stdout.write(
                "\n[Usare --persist per salvare nel database]"
            )
