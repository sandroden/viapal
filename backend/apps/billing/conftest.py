"""Fixture condivise per i test su allocazioni e bonifici."""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    Receivable,
)
from properties.models import (
    OwnerBankAccount,
    OwnerProfile,
    Room,
    RoomAssignment,
    TenantProfile,
)


@pytest.fixture
def conto_alloc(db, immobile):
    u = User.objects.create_user("prop_alloc", email="pa@v.it", password="pwd")
    owner = OwnerProfile.objects.create(user=u, nominativo="Owner Alloc")
    acct = OwnerBankAccount.objects.create(
        owner=owner,
        banca="Banca Alloc",
        intestatario="Owner Alloc",
        iban="IT00X0000000000000000000001",
    )
    acct.properties.add(immobile)
    return acct


@pytest.fixture
def assignment_alloc(db, immobile):
    u = User.objects.create_user("inq_alloc", email="ia@v.it", password="pwd")
    tenant = TenantProfile.objects.create(
        property=immobile, user=u, nominativo="Simona Test",
        giorno_pagamento_affitto=5,
    )
    room = Room.objects.create(property=immobile, nome="Stanza Alloc", ordinamento=30)
    return RoomAssignment.objects.create(
        room=room,
        tenant=tenant,
        valid_from=datetime.date(2026, 9, 5),
        canone_mensile=Decimal("390"),
    )


@pytest.fixture
def deposito_alloc(db, assignment_alloc):
    """Deposito da 980 €, la cifra del caso reale."""
    return Receivable.objects.create(
        assignment=assignment_alloc,
        causale=Receivable.Causale.DEPOSITO,
        descrizione="Deposito (versamento)",
        competenza_da=datetime.date(2026, 9, 5),
        scadenza=datetime.date(2026, 9, 5),
        importo_dovuto=Decimal("980.00"),
    )


@pytest.fixture
def deposito_sbilanciato(db, deposito_alloc, conto_alloc):
    """Lo stato in cui si trovava il DB: 390 + 100 incassati, ma 980 allocati.

    Il secondo bonifico è stato corretto da 590.100 a 100 € *dopo* la
    riconciliazione, senza toccare l'allocazione da 590 €.
    """
    bt_1 = BankTransaction.objects.create(
        data=datetime.date(2026, 8, 10),
        descrizione="Bonifico deposito_alloc — 1^ acconto",
        importo=Decimal("390.00"),
        owner_account=conto_alloc,
    )
    BankTransactionAllocation.objects.create(
        bank_transaction=bt_1, receivable=deposito_alloc, importo=Decimal("390.00")
    )
    bt_2 = BankTransaction.objects.create(
        data=datetime.date(2026, 8, 14),
        descrizione="Bonifico deposito_alloc",
        importo=Decimal("100.00"),
        owner_account=conto_alloc,
    )
    alloc = BankTransactionAllocation.objects.create(
        bank_transaction=bt_2, receivable=deposito_alloc, importo=Decimal("590.00")
    )
    return bt_2, alloc


@pytest.fixture
def client_admin(db):
    from django.test import Client

    User.objects.create_superuser("admin_alloc", "admin@v.it", "pwd123!")
    c = Client()
    c.login(username="admin_alloc", password="pwd123!")
    return c
