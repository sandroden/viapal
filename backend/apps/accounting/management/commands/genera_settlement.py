"""
Comando per generare/rigenerare un OwnerSettlement.

Usi tipici:
    uv run manage.py genera_settlement --anno 2024
    uv run manage.py genera_settlement --anno 2024 --reset
    uv run manage.py genera_settlement --periodo-da 2024-01-01 --periodo-a 2024-06-30
    uv run manage.py genera_settlement --anno 2024 --dry-run
"""
import datetime

from django.core.management.base import BaseCommand, CommandError

from accounting.services.settlement import SettlementGiaEsistente, genera_settlement


class Command(BaseCommand):
    help = "Genera/rigenera un OwnerSettlement aggregando Receivable pagati e Expense del periodo."

    def add_arguments(self, parser):
        gruppo = parser.add_mutually_exclusive_group(required=True)
        gruppo.add_argument(
            "--anno",
            type=int,
            help="Anno da chiudere (1 gennaio - 31 dicembre).",
        )
        gruppo.add_argument(
            "--periodo-da",
            type=datetime.date.fromisoformat,
            help="Inizio periodo (YYYY-MM-DD). Richiede --periodo-a.",
        )
        parser.add_argument(
            "--periodo-a",
            type=datetime.date.fromisoformat,
            help="Fine periodo (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--descrizione",
            type=str,
            default=None,
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Cancella le voci esistenti del settlement e ricrea (idempotente).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Esegue tutto in transazione e fa rollback alla fine.",
        )

    def handle(self, *args, **opts):
        if opts["anno"]:
            periodo_da = datetime.date(opts["anno"], 1, 1)
            periodo_a = datetime.date(opts["anno"], 12, 31)
        else:
            periodo_da = opts["periodo_da"]
            periodo_a = opts["periodo_a"]
            if not periodo_a:
                raise CommandError("Con --periodo-da serve anche --periodo-a.")

        try:
            settlement = genera_settlement(
                periodo_da,
                periodo_a,
                descrizione=opts["descrizione"],
                reset=opts["reset"],
                dry_run=opts["dry_run"],
            )
        except SettlementGiaEsistente as exc:
            raise CommandError(str(exc)) from exc

        prefisso = "[DRY-RUN] " if opts["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefisso}Settlement {settlement.pk} ({periodo_da} → {periodo_a}) generato."
        ))
        for owner_id, saldo in settlement.snapshot.items():
            self.stdout.write(f"  owner {owner_id}: {saldo}")
