"""
Aggancia (pin) le bollette luce/gas ai ``UtilityChargePeriod`` storici secondo
le regole:

bolletta → periodo **aperto** che la contiene interamente. Le bollette già
agganciate e quelle che nessun periodo aperto contiene vengono saltate e
segnalate.

Per i periodi **già emessi** con la M2M vuota serve invece
``pin_bollette_periodi_emessi``: lì il pinning va verificato importo per
importo, perché in modalità pinning ogni bolletta agganciata vale per intero.

Uso:
    uv run manage.py pin_bollette_storiche                 # dry-run
    uv run manage.py pin_bollette_storiche --persist       # esegue il pin
    uv run manage.py pin_bollette_storiche --year 2024     # filtro anno
"""
from django.core.management.base import BaseCommand, CommandError

from properties.context import resolve_property_cli


class Command(BaseCommand):
    help = "Aggancia bollette luce/gas ai UtilityChargePeriod 'naturali'."

    def add_arguments(self, parser):
        parser.add_argument(
            "--persist",
            action="store_true",
            default=False,
            help="Applica davvero gli agganci (default: dry-run).",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=None,
            help="Filtra solo bollette con periodo_da in quell'anno.",
        )
        parser.add_argument(
            "--property",
            type=str,
            default=None,
            help="Immobile (id, nome o slug). Obbligatorio se ci sono più immobili.",
        )

    def handle(self, *args, **options):
        from billing.calc.utility import VOCI_FATTURABILI
        from billing.models import UtilityBill

        persist = options["persist"]
        year = options.get("year")
        try:
            prop = resolve_property_cli(options.get("property"))
        except ValueError as e:
            raise CommandError(str(e)) from e

        bills_qs = UtilityBill.objects.filter(
            immobile=prop,
            prodotto__in=VOCI_FATTURABILI,
        ).order_by("data_emissione")
        if year:
            bills_qs = bills_qs.filter(periodo_da__year=year)

        # Già pinnate altrove
        gia_pinned_ids = set(
            UtilityBill.objects.filter(periods__isnull=False)
            .values_list("pk", flat=True)
            .distinct()
        )

        pinned_count = skip_count = orphan_count = 0
        riepilogo: list[str] = []

        for bill in bills_qs:
            if bill.pk in gia_pinned_ids:
                skip_count += 1
                continue

            target = self._scegli_periodo(bill, prop)
            if target is None:
                orphan_count += 1
                riepilogo.append(
                    f"  [{bill.pk}] {bill.prodotto} {bill.periodo_da}->{bill.periodo_a} "
                    f"(em.{bill.data_emissione}) {bill.importo_totale}€ — NESSUN periodo target"
                )
                continue

            riepilogo.append(
                f"  [{bill.pk}] {bill.prodotto} {bill.periodo_da}->{bill.periodo_a} "
                f"(em.{bill.data_emissione}) {bill.importo_totale}€ → "
                f"periodo [{target.pk}] {target.periodo_da}->{target.periodo_a}"
            )
            if persist:
                target.utility_bills.add(bill)
            pinned_count += 1

        prefix = "" if persist else "[DRY-RUN] "
        self.stdout.write(f"{prefix}Bollette analizzate: {bills_qs.count()}")
        self.stdout.write(f"{prefix}  pin: {pinned_count}")
        self.stdout.write(f"{prefix}  skip (già pinnate): {skip_count}")
        self.stdout.write(f"{prefix}  orfane (no target): {orphan_count}")
        self.stdout.write("")
        for r in riepilogo:
            self.stdout.write(r)

    @staticmethod
    def _scegli_periodo(bill, prop):
        """Il periodo APERTO che contiene interamente il range della bolletta.

        Due limiti deliberati, imparati dal conguaglio gonfiato di luglio 2026:

        - **mai un periodo ``inviato``**: quello che è stato emesso è
          congelato, aggiungergli bollette ne falserebbe la ricostruzione (in
          modalità pinning ogni bolletta vale per intero). Per riempire la
          M2M dei periodi già emessi c'è ``pin_bollette_periodi_emessi``, che
          verifica di non cambiare gli importi.
        - **niente ribaltamento sul periodo successivo**: la regola v1 "la
          bolletta multi-periodo si carica sul primo aperto dopo" precede
          l'attribuzione day-based, che ripartisce sui mesi coperti. Una
          bolletta che nessun periodo aperto contiene resta orfana e viene
          segnalata, non spostata altrove.
        """
        from billing.models import UtilityChargePeriod

        return (
            UtilityChargePeriod.objects.filter(
                property=prop,
                periodo_da__lte=bill.periodo_da,
                periodo_a__gte=bill.periodo_a,
            )
            .exclude(stato=UtilityChargePeriod.StatoPeriodo.INVIATO)
            .order_by("periodo_da")
            .first()
        )
