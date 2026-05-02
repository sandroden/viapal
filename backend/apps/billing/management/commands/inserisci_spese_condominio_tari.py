"""
Inserisce le spese condominiali (rate MAV/bonifici) e la TARI annuale come
Expense anticipate da Bruna. Aggiorna anche AnnualUtilityCost con gli importi
TARI reali (per il calcolo conguagli utenze).

Dati forniti da Sandro 2026-05-02.

Uso:
    uv run manage.py inserisci_spese_condominio_tari [--dry-run]
"""
import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import AnnualUtilityCost, Expense, ExpenseCategory
from properties.models import OwnerProfile

# (esercizio, data ISO, importo, descrizione)
RATE_CONDOMINIO = [
    # Esercizio 2022/2023
    ("2022/2023", "2023-01-11", 1698, "1ª rata MAV"),
    ("2022/2023", "2023-02-10", 1197, "2ª rata MAV"),
    ("2022/2023", "2023-03-14", 1246, "3ª rata MAV"),
    ("2022/2023", "2023-05-07", 1209, "4ª rata MAV"),
    ("2022/2023", "2023-12-22", 1210, "5ª rata MAV"),
    # Esercizio 2023/2024
    ("2023/2024", "2023-12-22", 1209, "1ª rata MAV"),
    ("2023/2024", "2024-02-28", 436, "2ª rata MAV"),
    ("2023/2024", "2024-06-28", 2112, "3ª e 4ª rata (bonifico)"),
    ("2023/2024", "2024-08-02", 1056, "5ª rata MAV"),
    ("2023/2024", "2024-11-04", 1056, "1ª rata 24/25 MAV"),
    # Esercizio 2024/2025
    ("2024/2025", "2025-05-21", 4356, "2ª e 3ª rata + conguaglio (bonifico)"),
    ("2024/2025", "2025-06-17", 1250, "4ª rata (bonifico)"),
    ("2024/2025", "2025-07-31", 1250, "5ª rata MAV"),
    ("2024/2025", "2025-11-04", 1250, "1ª rata 25/26 (bonifico)"),
    # NB: rata "ascensori" non va inserita: e' gia' compresa nelle rate del
    # condominio. Rileva solo per la suddivisione fra proprietari/inquilini.
    # Esercizio 2025/2026 (in corso)
    ("2025/2026", "2025-11-04", 1250, "1ª rata (bonifico)"),
    ("2025/2026", "2026-02-01", 1250, "2ª rata (bonifico)"),
    ("2025/2026", "2026-02-27", 971, "3ª rata (bonifico)"),
    ("2025/2026", "2026-03-23", 1041, "4ª rata (bonifico)"),
]

# (anno fiscale, importo annuale)
TARI_ANNI = [
    (2023, 461),
    (2024, 507),
    (2025, 535),
]


class Command(BaseCommand):
    help = "Inserisce spese condominiali e TARI come Expense anticipate da Bruna."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        bruna = OwnerProfile.objects.filter(nominativo__icontains="Bruna").first()
        if not bruna:
            self.stderr.write(self.style.ERROR("OwnerProfile Bruna non trovato."))
            return

        cat_cond, _ = ExpenseCategory.objects.get_or_create(
            codice="condominio",
            defaults={
                "nome": "Spese condominiali",
                "ripartibile_inquilini": False,
            },
        )
        cat_tari, _ = ExpenseCategory.objects.get_or_create(
            codice="tari",
            defaults={"nome": "TARI", "ripartibile_inquilini": True},
        )

        creati = 0
        aggiornati = 0

        for esercizio, data_iso, importo, sublabel in RATE_CONDOMINIO:
            data = datetime.date.fromisoformat(data_iso)
            descrizione = f"Condominio {esercizio} — {sublabel}"
            obj, was_created = Expense.objects.update_or_create(
                data=data,
                descrizione=descrizione,
                defaults={
                    "category": cat_cond,
                    "importo": Decimal(str(importo)),
                    "anticipata_da_owner": bruna,
                    "ripartibile_su_inquilini": False,
                    "note": "Inserito automaticamente (rata condominio MAV/bonifico).",
                },
            )
            self.stdout.write(
                f"  [{'+' if was_created else '~'}] {data} | {importo:>5}€ | {descrizione}"
            )
            creati += 1 if was_created else 0
            aggiornati += 0 if was_created else 1

        self.stdout.write("")
        for anno, importo in TARI_ANNI:
            data = datetime.date(anno, 10, 16)  # F24 saldo TARI (Sandro)
            descrizione = f"TARI {anno} (F24)"
            obj, was_created = Expense.objects.update_or_create(
                data=data,
                descrizione=descrizione,
                defaults={
                    "category": cat_tari,
                    "importo": Decimal(str(importo)),
                    "anticipata_da_owner": bruna,
                    "ripartibile_su_inquilini": True,
                    "note": "TARI annuale pagata via F24, anticipata da Bruna.",
                },
            )
            self.stdout.write(
                f"  [{'+' if was_created else '~'}] {data} | {importo:>5}€ | {descrizione}"
            )
            creati += 1 if was_created else 0
            aggiornati += 0 if was_created else 1

            # AnnualUtilityCost: importo reale (sostituisce la stima 510)
            auc, auc_created = AnnualUtilityCost.objects.update_or_create(
                voce="tari",
                anno=anno,
                defaults={
                    "importo_annuale": Decimal(str(importo)),
                    "valid_from": datetime.date(anno, 1, 1),
                    "valid_to": datetime.date(anno, 12, 31),
                    "note": "Aggiornato con importo reale F24.",
                },
            )
            self.stdout.write(
                f"     AnnualUtilityCost tari {anno} = {importo}€ "
                f"({'created' if auc_created else 'updated'})"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Creati={creati}, aggiornati={aggiornati}."
            )
        )
        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN: rollback."))
            transaction.set_rollback(True)
