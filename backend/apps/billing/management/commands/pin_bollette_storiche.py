"""
Aggancia (pin) le bollette luce/gas ai ``UtilityChargePeriod`` storici secondo
le regole:

1. Bolletta il cui range ``[periodo_da, periodo_a]`` coincide con un solo
   periodo → pin a quel periodo.
2. Bolletta multi-bimestre (range che cavalca più periodi) → pin al primo
   periodo con ``periodo_da > bill.periodo_a`` (= ribaltamento sul periodo
   successivo). Riflette la pratica: "bolletta retroattiva si carica sul
   primo aperto dopo".

Bollette già agganciate a qualche periodo (M2M non vuota) vengono saltate.

Uso:
    uv run manage.py pin_bollette_storiche                 # dry-run
    uv run manage.py pin_bollette_storiche --persist       # esegue il pin
    uv run manage.py pin_bollette_storiche --year 2024     # filtro anno
"""
from django.core.management.base import BaseCommand


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

    def handle(self, *args, **options):
        from billing.calc.utility import VOCI_FATTURABILI
        from billing.models import UtilityBill, UtilityChargePeriod

        persist = options["persist"]
        year = options.get("year")

        bills_qs = UtilityBill.objects.filter(
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

            target = self._scegli_periodo(bill)
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
    def _scegli_periodo(bill):
        """Regola di pinning automatico:
        - Se esiste UN periodo il cui range coincide col range della bolletta
          → pin a quel periodo.
        - Se esiste UN solo periodo che CONTIENE interamente il range della
          bolletta → pin a quel periodo (caso bolletta mensile dentro un
          bimestre).
        - Altrimenti (range cavalca più periodi, multi-bimestre) → primo
          periodo con ``periodo_da > bill.periodo_a`` (ribaltamento sul
          successivo); se nessuno, l'ultimo periodo che contiene almeno un
          giorno del range della bolletta.
        """
        from billing.models import UtilityChargePeriod

        # 1. Periodo che coincide col range bolletta (esatto o contenente)
        contenente = UtilityChargePeriod.objects.filter(
            periodo_da__lte=bill.periodo_da,
            periodo_a__gte=bill.periodo_a,
        ).order_by("periodo_da")
        if contenente.exists():
            return contenente.first()

        # 2. Multi-bimestre: ribalta sul primo periodo dopo periodo_a
        successivo = (
            UtilityChargePeriod.objects.filter(periodo_da__gt=bill.periodo_a)
            .order_by("periodo_da")
            .first()
        )
        if successivo:
            return successivo

        # 3. Fallback: ultimo periodo che interseca almeno parzialmente
        ultimo_intersezione = (
            UtilityChargePeriod.objects.filter(
                periodo_da__lte=bill.periodo_a,
                periodo_a__gte=bill.periodo_da,
            )
            .order_by("-periodo_da")
            .first()
        )
        return ultimo_intersezione
