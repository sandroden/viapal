"""Salda i Receivable scoperti di un inquilino con i resti dei suoi bonifici.

Logica
------

Un Receivable in stato ``atteso`` / ``dichiarato`` / ``in_ritardo`` ha
``importo_pagato`` minore di ``importo_dovuto`` (o nullo). Spesso lo stesso
inquilino ha versato più del necessario su altri bonifici (es. 630 € per un
affitto di 600 €): il delta è un *resto* della ``BankTransaction``, denaro
mai imputato a nulla.

Lo *sbilancio reale* (cfr. ``_sbilancio_progressivo`` in
``dashboard_views.py``) tiene già conto di questi resti: quando vale zero
significa che ogni euro versato è stato dovuto, ma le imputazioni per
riga non lo rispecchiano. Questo command sana le imputazioni:

  - prende i Receivable scoperti dell'inquilino (escluso DEPOSITO), in
    ordine di scadenza;
  - prende i bonifici dell'inquilino con resto > 0, in ordine di data;
  - alloca FIFO i resti sugli scoperti fino a esaurimento di uno dei due
    flussi; se sul (BT, Receivable) esiste già un'allocation, la *aumenta*
    invece di crearne un'altra (la coppia è unica).

I segnali su ``BankTransactionAllocation`` aggiornano automaticamente
stato/importo_pagato/data_pagamento del Receivable a valle.

Default è dry-run; servono ``--apply`` per scrivere. Uso tipico alla
chiusura di un rapporto::

    uv run manage.py salda_con_resti --tenant 46              # dry-run
    uv run manage.py salda_con_resti --tenant 46 --apply
"""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    Receivable,
)
from billing.models.payments import StatoPagamento
from properties.models import TenantProfile


STATI_SCOPERTI = (
    StatoPagamento.ATTESO,
    StatoPagamento.DICHIARATO,
    StatoPagamento.IN_RITARDO,
)


class Command(BaseCommand):
    help = (
        "Salda i Receivable scoperti di un inquilino allocando i resti dei "
        "suoi bonifici (FIFO). Default dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            type=int,
            required=True,
            help="ID del TenantProfile su cui operare.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Scrive nel DB. Senza questo flag è dry-run.",
        )

    def handle(self, *args, **opts):
        tenant_id = opts["tenant"]
        apply_ = opts["apply"]

        try:
            tenant = TenantProfile.objects.get(pk=tenant_id)
        except TenantProfile.DoesNotExist as e:
            raise CommandError(f"TenantProfile id={tenant_id} non trovato.") from e

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Tenant: {tenant.nominativo} (id={tenant.id})"
            )
        )
        self.stdout.write(f"Modalità: {'APPLY' if apply_ else 'DRY-RUN'}")

        # Receivable scoperti (escluso DEPOSITO), in ordine di scadenza
        scoperti = list(
            Receivable.objects.filter(
                assignment__tenant=tenant,
                stato__in=STATI_SCOPERTI,
                importo_dovuto__gt=0,
            )
            .exclude(causale=Receivable.Causale.DEPOSITO)
            .order_by("scadenza", "id")
        )
        scoperti_info: list[tuple[Receivable, Decimal]] = []
        for r in scoperti:
            allocato = (
                r.allocations.aggregate(t=Sum("importo"))["t"] or Decimal("0")
            )
            residuo = r.importo_dovuto - allocato
            if residuo > 0:
                scoperti_info.append((r, residuo))

        if not scoperti_info:
            self.stdout.write(self.style.SUCCESS("Nessun Receivable scoperto."))
            return

        # Bonifici del tenant: BT con almeno un'allocation su un suo
        # Receivable non-DEPOSITO. Sono "suoi" anche se hanno resti perché
        # almeno una quota è già stata imputata a un suo addebito.
        bt_ids = list(
            BankTransactionAllocation.objects.filter(
                receivable__assignment__tenant=tenant,
            )
            .exclude(receivable__causale=Receivable.Causale.DEPOSITO)
            .values_list("bank_transaction_id", flat=True)
            .distinct()
        )
        bt_con_resto: list[tuple[BankTransaction, Decimal]] = []
        for bt in BankTransaction.objects.filter(id__in=bt_ids).order_by(
            "data", "id"
        ):
            # Considero solo entrate: i resti su uscite (es. restituzione
            # deposito) non sono "soldi liberi" da imputare ad addebiti.
            if bt.importo <= 0:
                continue
            resto = bt.residuo
            if resto > 0:
                bt_con_resto.append((bt, resto))

        if not bt_con_resto:
            self.stdout.write(self.style.WARNING("Nessun resto disponibile."))
            return

        tot_scoperti = sum((r for _, r in scoperti_info), Decimal("0"))
        tot_resti = sum((r for _, r in bt_con_resto), Decimal("0"))
        self.stdout.write(
            f"Scoperto totale: {tot_scoperti}  Resti disponibili: {tot_resti}"
        )
        self.stdout.write("")

        # FIFO match
        piani: list[tuple[BankTransaction, Receivable, Decimal]] = []
        bt_idx = 0
        for r, residuo in scoperti_info:
            mancante = residuo
            while mancante > 0 and bt_idx < len(bt_con_resto):
                bt, resto_bt = bt_con_resto[bt_idx]
                quota = min(mancante, resto_bt)
                piani.append((bt, r, quota))
                mancante -= quota
                resto_bt -= quota
                if resto_bt > 0:
                    bt_con_resto[bt_idx] = (bt, resto_bt)
                else:
                    bt_idx += 1
            if mancante > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Receivable {r.id} ({r.causale} {r.scadenza}) "
                        f"resta scoperto per {mancante} (resti esauriti)."
                    )
                )

        if not piani:
            self.stdout.write(self.style.WARNING("Nessuna allocation da creare."))
            return

        for bt, r, quota in piani:
            self.stdout.write(
                f"  BT {bt.data} {bt.importo:>8}€  →  "
                f"Rec {r.id} {r.causale} {r.scadenza} {r.importo_dovuto}€  "
                f"quota {quota}€"
            )

        if not apply_:
            self.stdout.write("")
            self.stdout.write(
                self.style.NOTICE("DRY-RUN: nessuna modifica. Usa --apply.")
            )
            return

        with transaction.atomic():
            for bt, r, quota in piani:
                alloc, created = BankTransactionAllocation.objects.get_or_create(
                    bank_transaction=bt,
                    receivable=r,
                    defaults={"importo": quota},
                )
                if not created:
                    alloc.importo = (alloc.importo or Decimal("0")) + quota
                    alloc.save(update_fields=["importo", "updated_at"])

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Create/aggiornate {len(piani)} allocations."))
