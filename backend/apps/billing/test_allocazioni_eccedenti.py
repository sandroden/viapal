"""Guardia contro le allocazioni eccedenti: stato del modello e validazione admin.

L'invariante (somma allocata ≤ importo del movimento) era verificata solo alla
creazione: correggere l'importo di una BT già riconciliata la rompeva in
silenzio. Qui si verifica che l'anomalia sia rilevata e che l'admin non
permetta più di crearla, senza rompere le partite compensate legittime.
"""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    Receivable,
    StatoPagamento,
)


# ---------------------------------------------------------------------------
# Correzione del movimento: l'addebito lo segue
# ---------------------------------------------------------------------------


class TestCorrezioneBankTransaction:
    """Chi ha incassato e quando derivano dalla BT: correggerla riallinea.

    Senza il signal, cambiare il conto di un bonifico già riconciliato
    lasciava sull'addebito il proprietario sbagliato, in silenzio.
    """

    @pytest.fixture
    def conto_altro_owner(self, db, immobile):
        from django.contrib.auth.models import User

        from properties.models import OwnerBankAccount, OwnerProfile

        u = User.objects.create_user("prop_due", email="p2@v.it", password="pwd")
        owner = OwnerProfile.objects.create(user=u, nominativo="Owner Due")
        acct = OwnerBankAccount.objects.create(
            owner=owner, banca="Banca Due", intestatario="Owner Due",
            iban="IT00X0000000000000000000002",
        )
        acct.properties.add(immobile)
        return acct

    def _bt_pagante(self, deposito_alloc, conto_alloc):
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 9, 10), descrizione="versamento deposito",
            importo=Decimal("980.00"), owner_account=conto_alloc,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=deposito_alloc, importo=Decimal("980.00")
        )
        deposito_alloc.refresh_from_db()
        assert deposito_alloc.stato == StatoPagamento.PAGATO
        assert deposito_alloc.incassato_da_owner == conto_alloc.owner
        return bt

    def test_cambio_conto_sposta_incassante(
        self, deposito_alloc, conto_alloc, conto_altro_owner
    ):
        bt = self._bt_pagante(deposito_alloc, conto_alloc)

        bt.owner_account = conto_altro_owner
        bt.save(update_fields=["owner_account"])

        deposito_alloc.refresh_from_db()
        assert deposito_alloc.incassato_da_owner == conto_altro_owner.owner

    def test_cambio_data_sposta_data_pagamento(self, deposito_alloc, conto_alloc):
        bt = self._bt_pagante(deposito_alloc, conto_alloc)

        bt.data = datetime.date(2026, 9, 12)
        bt.save(update_fields=["data"])

        deposito_alloc.refresh_from_db()
        assert deposito_alloc.data_pagamento == datetime.date(2026, 9, 12)


# ---------------------------------------------------------------------------
# Modello: rilevazione dell'anomalia
# ---------------------------------------------------------------------------


class TestStatoRiconciliazione:
    def test_sovra_allocata(self, deposito_sbilanciato):
        bt, _ = deposito_sbilanciato
        assert bt.stato_riconciliazione == "sovra"
        assert bt.is_sovra_allocato is True

    def test_pieno_resta_pieno(self, deposito_alloc, conto_alloc):
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 8, 10), descrizione="ok",
            importo=Decimal("390.00"), owner_account=conto_alloc,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=deposito_alloc, importo=Decimal("390.00")
        )
        assert bt.stato_riconciliazione == "pieno"
        assert bt.is_sovra_allocato is False

    def test_compensazione_legittima_non_e_anomalia(self, assignment_alloc, conto_alloc):
        """Restituzione deposito_alloc con trattenuta utenze: BT −984 ↔ alloc −1060
        (restituzione) + alloc +76 (utenze previsionali). Somma −984: piena."""
        restituzione = Receivable.objects.create(
            assignment=assignment_alloc,
            causale=Receivable.Causale.DEPOSITO,
            descrizione="Restituzione deposito_alloc",
            competenza_da=datetime.date(2026, 9, 5),
            scadenza=datetime.date(2026, 9, 5),
            importo_dovuto=Decimal("-1060.00"),
        )
        utenze = Receivable.objects.create(
            assignment=assignment_alloc,
            causale=Receivable.Causale.UTENZE,
            competenza_da=datetime.date(2026, 8, 1),
            scadenza=datetime.date(2026, 9, 5),
            importo_dovuto=Decimal("76.00"),
        )
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 9, 10),
            descrizione="Restituzione deposito_alloc al netto delle utenze",
            importo=Decimal("-984.00"),
            owner_account=conto_alloc,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=restituzione, importo=Decimal("-1060.00")
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=utenze, importo=Decimal("76.00")
        )
        assert bt.stato_riconciliazione == "pieno"
        assert bt.is_sovra_allocato is False


# ---------------------------------------------------------------------------
# Admin: la validazione che impedisce di ricrearlo
# ---------------------------------------------------------------------------


def _payload_bt(bt, alloc, importo, importo_alloc=None):
    """POST della change_form BT con il suo inline allocazioni."""
    return {
        "data": bt.data.isoformat(),
        "descrizione": bt.descrizione,
        "importo": str(importo),
        "owner_account": str(bt.owner_account_id),
        "note": "",
        "allocations-TOTAL_FORMS": "1",
        "allocations-INITIAL_FORMS": "1",
        "allocations-MIN_NUM_FORMS": "0",
        "allocations-MAX_NUM_FORMS": "1000",
        "allocations-0-id": str(alloc.pk),
        "allocations-0-bank_transaction": str(bt.pk),
        "allocations-0-receivable": str(alloc.receivable_id),
        "allocations-0-importo": str(
            alloc.importo if importo_alloc is None else importo_alloc
        ),
        "_continue": "Salva e continua",
    }


class TestAdminValidazione:
    def test_riduzione_importo_con_allocazioni_intatte_e_rifiutata(
        self, client_admin, deposito_alloc, conto_alloc
    ):
        """Il caso all'origine del bug: correggo 590.100 → 100 lasciando
        l'allocazione da 590. L'admin deve fermarmi."""
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 8, 14), descrizione="Bonifico deposito_alloc",
            importo=Decimal("590100.00"), owner_account=conto_alloc,
        )
        alloc = BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=deposito_alloc, importo=Decimal("590.00")
        )
        url = reverse("admin:billing_banktransaction_change", args=[bt.pk])
        resp = client_admin.post(url, _payload_bt(bt, alloc, "100.00"))

        assert resp.status_code == 200  # form ripresentato con errori
        # L'apostrofo esce HTML-escapato nel template admin.
        assert "superano" in resp.content.decode()
        bt.refresh_from_db()
        assert bt.importo == Decimal("590100.00")  # nulla salvato

    def test_correzione_coerente_passa(self, client_admin, deposito_alloc, conto_alloc):
        """Stessa correzione, ma sistemando anche l'allocazione: si salva."""
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 8, 14), descrizione="Bonifico deposito_alloc",
            importo=Decimal("590100.00"), owner_account=conto_alloc,
        )
        alloc = BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=deposito_alloc, importo=Decimal("590.00")
        )
        url = reverse("admin:billing_banktransaction_change", args=[bt.pk])
        resp = client_admin.post(
            url, _payload_bt(bt, alloc, "100.00", importo_alloc="100.00")
        )

        assert resp.status_code in (200, 302)
        bt.refresh_from_db()
        alloc.refresh_from_db()
        deposito_alloc.refresh_from_db()
        assert bt.importo == Decimal("100.00")
        assert alloc.importo == Decimal("100.00")
        assert deposito_alloc.importo_pagato == Decimal("100.00")

    def test_compensazione_legittima_accettata(self, client_admin, assignment_alloc, conto_alloc):
        """La partita compensata (−1060 + 76 su BT −984) resta salvabile."""
        restituzione = Receivable.objects.create(
            assignment=assignment_alloc,
            causale=Receivable.Causale.DEPOSITO,
            descrizione="Restituzione deposito_alloc",
            competenza_da=datetime.date(2026, 9, 5),
            scadenza=datetime.date(2026, 9, 5),
            importo_dovuto=Decimal("-1060.00"),
        )
        utenze = Receivable.objects.create(
            assignment=assignment_alloc,
            causale=Receivable.Causale.UTENZE,
            competenza_da=datetime.date(2026, 8, 1),
            scadenza=datetime.date(2026, 9, 5),
            importo_dovuto=Decimal("76.00"),
        )
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 9, 10), descrizione="Restituzione netta",
            importo=Decimal("-984.00"), owner_account=conto_alloc,
        )
        url = reverse("admin:billing_banktransaction_change", args=[bt.pk])
        payload = {
            "data": bt.data.isoformat(),
            "descrizione": bt.descrizione,
            "importo": "-984.00",
            "owner_account": str(conto_alloc.pk),
            "note": "",
            "allocations-TOTAL_FORMS": "2",
            "allocations-INITIAL_FORMS": "0",
            "allocations-MIN_NUM_FORMS": "0",
            "allocations-MAX_NUM_FORMS": "1000",
            "allocations-0-id": "",
            "allocations-0-bank_transaction": str(bt.pk),
            "allocations-0-receivable": str(restituzione.pk),
            "allocations-0-importo": "-1060.00",
            "allocations-1-id": "",
            "allocations-1-bank_transaction": str(bt.pk),
            "allocations-1-receivable": str(utenze.pk),
            "allocations-1-importo": "76.00",
            "_continue": "Salva e continua",
        }
        resp = client_admin.post(url, payload)

        assert resp.status_code in (200, 302)
        assert bt.allocations.count() == 2
        assert bt.stato_riconciliazione == "pieno"


# ---------------------------------------------------------------------------
# Il flusso normale non deve essere toccato: un bonifico, più addebiti
# ---------------------------------------------------------------------------


@pytest.fixture
def affitto_e_extra(db, assignment_alloc):
    """Due addebiti dello stesso inquilino: 400 + 50 = 450."""
    affitto = Receivable.objects.create(
        assignment=assignment_alloc,
        causale=Receivable.Causale.AFFITTO,
        competenza_da=datetime.date(2026, 9, 1),
        competenza_a=datetime.date(2026, 9, 30),
        scadenza=datetime.date(2026, 9, 5),
        importo_dovuto=Decimal("400.00"),
    )
    extra = Receivable.objects.create(
        assignment=assignment_alloc,
        causale=Receivable.Causale.EXTRA,
        descrizione="Pulizie",
        competenza_da=datetime.date(2026, 9, 1),
        scadenza=datetime.date(2026, 9, 5),
        importo_dovuto=Decimal("50.00"),
    )
    return affitto, extra


@pytest.fixture
def client_membro(db, immobile, conto_alloc):
    """Client API del proprietario, membro dell'immobile di test."""
    from properties.models import PropertyMembership
    from rest_framework.test import APIClient

    PropertyMembership.objects.create(
        property=immobile,
        user=conto_alloc.owner.user,
        ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
    )
    client = APIClient(enforce_csrf_checks=False)
    client.force_login(conto_alloc.owner.user)
    return client


class TestBonificoUnicoSuPiuAddebiti:
    """Il caso quotidiano: incasso unico da 450 € che salda affitto + extra.

    La guardia vieta di allocare *più* dell'importo del movimento, non di
    spezzarlo su più addebiti: questi test lo tengono fermo.
    """

    def test_split_da_admin(self, client_admin, affitto_e_extra, conto_alloc):
        affitto, extra = affitto_e_extra
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 9, 3),
            descrizione="Bonifico affitto + pulizie",
            importo=Decimal("450.00"),
            owner_account=conto_alloc,
        )
        url = reverse("admin:billing_banktransaction_change", args=[bt.pk])
        payload = {
            "data": bt.data.isoformat(),
            "descrizione": bt.descrizione,
            "importo": "450.00",
            "owner_account": str(conto_alloc.pk),
            "note": "",
            "allocations-TOTAL_FORMS": "2",
            "allocations-INITIAL_FORMS": "0",
            "allocations-MIN_NUM_FORMS": "0",
            "allocations-MAX_NUM_FORMS": "1000",
            "allocations-0-id": "",
            "allocations-0-bank_transaction": str(bt.pk),
            "allocations-0-receivable": str(affitto.pk),
            "allocations-0-importo": "400.00",
            "allocations-1-id": "",
            "allocations-1-bank_transaction": str(bt.pk),
            "allocations-1-receivable": str(extra.pk),
            "allocations-1-importo": "50.00",
            "_continue": "Salva e continua",
        }
        resp = client_admin.post(url, payload)

        assert resp.status_code in (200, 302)
        assert bt.allocations.count() == 2
        assert bt.stato_riconciliazione == "pieno"
        affitto.refresh_from_db()
        extra.refresh_from_db()
        assert affitto.stato == StatoPagamento.PAGATO
        assert extra.stato == StatoPagamento.PAGATO

    def test_split_dalla_pagina_di_riconciliazione(
        self, client_membro, affitto_e_extra, conto_alloc
    ):
        """Stessa cosa dal frontend (POST /api/v1/reconciliations/)."""
        affitto, extra = affitto_e_extra
        bt = BankTransaction.objects.create(
            data=datetime.date(2026, 9, 3),
            descrizione="Bonifico affitto + pulizie",
            importo=Decimal("450.00"),
            owner_account=conto_alloc,
        )
        resp = client_membro.post(
            "/api/v1/reconciliations/",
            {
                "replace_for_transactions": [bt.pk],
                "items": [
                    {"bank_transaction": bt.pk, "receivable": affitto.pk,
                     "importo": "400.00"},
                    {"bank_transaction": bt.pk, "receivable": extra.pk,
                     "importo": "50.00"},
                ],
            },
            format="json",
        )

        assert resp.status_code == 200, resp.content
        assert bt.allocations.count() == 2
        assert bt.stato_riconciliazione == "pieno"

    def test_addebito_coperto_da_due_bonifici(
        self, client_membro, affitto_e_extra, conto_alloc
    ):
        """E il simmetrico: un addebito saldato da due bonifici distinti."""
        affitto, _ = affitto_e_extra
        acconto = BankTransaction.objects.create(
            data=datetime.date(2026, 9, 3), descrizione="acconto",
            importo=Decimal("250.00"), owner_account=conto_alloc,
        )
        saldo = BankTransaction.objects.create(
            data=datetime.date(2026, 9, 10), descrizione="saldo",
            importo=Decimal("150.00"), owner_account=conto_alloc,
        )
        resp = client_membro.post(
            "/api/v1/reconciliations/",
            {
                "replace_for_transactions": [acconto.pk, saldo.pk],
                "items": [
                    {"bank_transaction": acconto.pk, "receivable": affitto.pk,
                     "importo": "250.00"},
                    {"bank_transaction": saldo.pk, "receivable": affitto.pk,
                     "importo": "150.00"},
                ],
            },
            format="json",
        )

        assert resp.status_code == 200, resp.content
        affitto.refresh_from_db()
        assert affitto.stato == StatoPagamento.PAGATO
        assert affitto.importo_pagato == Decimal("400.00")
