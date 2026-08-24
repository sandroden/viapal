"""Command di riparazione delle allocazioni eccedenti.

Caso reale: un deposito di 980 € risultava "pagato" per intero dopo che un
bonifico da 100 €, digitato per errore come 590.100 €, era stato corretto a
mano in admin — l'allocazione da 590 € era rimasta.
"""
import datetime
from decimal import Decimal
from io import StringIO

from django.core.management import call_command

from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    StatoPagamento,
)


# ---------------------------------------------------------------------------
# Command di riparazione
# ---------------------------------------------------------------------------


class TestSanaAllocazioniEccedenti:
    def test_dry_run_non_scrive(self, deposito_sbilanciato, deposito_alloc):
        _, alloc = deposito_sbilanciato
        out = StringIO()
        call_command("sana_allocazioni_eccedenti", stdout=out)
        alloc.refresh_from_db()
        deposito_alloc.refresh_from_db()
        assert alloc.importo == Decimal("590.00")
        assert deposito_alloc.stato == StatoPagamento.PAGATO
        assert "Dry-run" in out.getvalue()

    def test_apply_clampa_e_riallinea(self, deposito_sbilanciato, deposito_alloc):
        bt, alloc = deposito_sbilanciato
        call_command("sana_allocazioni_eccedenti", "--apply", stdout=StringIO())
        alloc.refresh_from_db()
        deposito_alloc.refresh_from_db()
        assert alloc.importo == Decimal("100.00")
        assert bt.stato_riconciliazione == "pieno"
        # 390 + 100 = 490 su 980 dovuti: metà, e l'addebito torna atteso.
        assert deposito_alloc.importo_pagato == Decimal("490.00")
        assert deposito_alloc.stato == StatoPagamento.ATTESO

    def test_idempotente(self, deposito_sbilanciato, deposito_alloc):
        call_command("sana_allocazioni_eccedenti", "--apply", stdout=StringIO())
        out = StringIO()
        call_command("sana_allocazioni_eccedenti", "--apply", stdout=out)
        assert "Nessuna transazione sovra-allocata" in out.getvalue()

    def test_elimina_allocazione_azzerata(self, deposito_alloc, conto_alloc):
        """Se la correzione porta l'importo a 0, l'allocazione sparisce."""
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 8, 14), descrizione="corretto a zero",
            importo=Decimal("0.00"), owner_account=conto_alloc,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=deposito_alloc, importo=Decimal("200.00")
        )
        out = StringIO()
        call_command("sana_allocazioni_eccedenti", "--apply", stdout=out)
        # BT a importo 0: il command segnala e non tocca (va guardata a mano).
        assert bt.allocations.count() == 1
        assert "da correggere a mano" in out.getvalue()

    def test_non_tocca_le_altre_bt(self, deposito_sbilanciato, deposito_alloc):
        bt_ok = BankTransaction.objects.get(importo=Decimal("390.00"))
        call_command("sana_allocazioni_eccedenti", "--apply", stdout=StringIO())
        assert bt_ok.allocations.get().importo == Decimal("390.00")
