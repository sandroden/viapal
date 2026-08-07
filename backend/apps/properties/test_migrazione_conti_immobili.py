"""Backfill della migrazione ``properties.0036``: conto → immobili in uso.

Il punto delicato è la sorgente più indiretta: un conto la cui unica traccia
su un immobile sono i movimenti già riconciliati con addebiti di quell'immobile
(gli import storici). Senza quella sorgente il backfill sembrerebbe corretto e
farebbe sparire in silenzio quei movimenti dalla riconciliazione.

La funzione si esercita direttamente sui modelli reali: ``apps.get_model`` del
registry vero restituisce le stesse classi che vede la migrazione, e qui non ci
sono differenze di schema fra i due stati.
"""
import datetime
import importlib
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import User

from billing.models import (
    BankTransaction,
    BankTransactionAllocation,
    Receivable,
    StatoPagamento,
)
from properties.models import (
    OwnerBankAccount,
    OwnerProfile,
    PropertyMembership,
    Room,
    RoomAssignment,
    TenantProfile,
)

# Il nome del modulo inizia con una cifra: si importa solo così.
collega_conti_agli_immobili = importlib.import_module(
    "properties.migrations.0036_ownerbankaccount_properties"
).collega_conti_agli_immobili

pytestmark = pytest.mark.django_db


def _conto(owner, iban_suffix):
    return OwnerBankAccount.objects.create(
        owner=owner,
        banca=f"Banca {iban_suffix}",
        intestatario="Tizio",
        iban=f"IT60X05428111010000000{iban_suffix:05d}",
    )


@pytest.fixture
def scenario(immobile, immobile2):
    """Un proprietario di A che è anche *gestore* di B: il caso reale."""
    u = User.objects.create_user("mig_owner", password="pwd123!")
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    PropertyMembership.objects.create(
        property=immobile2, user=u, ruolo=PropertyMembership.Ruolo.GESTORE
    )
    owner = OwnerProfile.objects.create(user=u, nominativo="Proprietario A")
    return owner, immobile, immobile2


def _esegui_backfill():
    """Esegue il backfill svuotando prima i collegamenti già presenti."""
    for c in OwnerBankAccount.objects.all():
        c.properties.clear()
    collega_conti_agli_immobili(django_apps, None)


def test_il_conto_del_gestore_non_entra_nell_immobile_gestito(scenario):
    owner, immobile, immobile2 = scenario
    conto = _conto(owner, 1)

    _esegui_backfill()

    assert list(conto.properties.values_list("pk", flat=True)) == [immobile.pk]
    assert not conto.properties.filter(pk=immobile2.pk).exists()


def test_conto_utenze_dell_immobile(scenario):
    owner, immobile, immobile2 = scenario
    conto = _conto(owner, 2)
    immobile2.bank_account_utenze = conto
    immobile2.save(update_fields=["bank_account_utenze"])

    _esegui_backfill()

    assert set(conto.properties.values_list("pk", flat=True)) == {
        immobile.pk,
        immobile2.pk,
    }


def test_conto_affitto_di_un_assegnazione(scenario):
    owner, immobile, immobile2 = scenario
    conto = _conto(owner, 3)
    u = User.objects.create_user("mig_inq", password="pwd123!")
    tenant = TenantProfile.objects.create(
        user=u, property=immobile2, nominativo="Inquilino", giorno_pagamento_affitto=1
    )
    room = Room.objects.create(property=immobile2, nome="Camera mig", ordinamento=1)
    RoomAssignment.objects.create(
        room=room,
        tenant=tenant,
        valid_from=datetime.date(2024, 9, 1),
        canone_mensile=Decimal("400"),
        bank_account_affitto=conto,
    )

    _esegui_backfill()

    assert conto.properties.filter(pk=immobile2.pk).exists()


def test_movimenti_gia_riconciliati_tengono_il_conto_sull_immobile(scenario):
    """La sorgente critica: nessun altro legame se non le allocazioni."""
    owner, immobile, immobile2 = scenario
    conto = _conto(owner, 4)

    u = User.objects.create_user("mig_inq_alloc", password="pwd123!")
    tenant = TenantProfile.objects.create(
        user=u, property=immobile2, nominativo="Inquilino", giorno_pagamento_affitto=1
    )
    room = Room.objects.create(property=immobile2, nome="Camera alloc", ordinamento=2)
    assignment = RoomAssignment.objects.create(
        room=room,
        tenant=tenant,
        valid_from=datetime.date(2024, 9, 1),
        canone_mensile=Decimal("400"),
    )
    receivable = Receivable.objects.create(
        assignment=assignment,
        causale=Receivable.Causale.AFFITTO,
        competenza_da=datetime.date(2026, 5, 1),
        competenza_a=datetime.date(2026, 5, 31),
        importo_dovuto=Decimal("400"),
        scadenza=datetime.date(2026, 5, 1),
        stato=StatoPagamento.ATTESO,
    )
    bt = BankTransaction.objects.create(
        data=datetime.date(2026, 5, 2),
        descrizione="Bonifico storico",
        importo=Decimal("400"),
        owner_account=conto,
    )
    BankTransactionAllocation.objects.create(
        bank_transaction=bt, receivable=receivable, importo=Decimal("400")
    )

    _esegui_backfill()

    assert conto.properties.filter(pk=immobile2.pk).exists(), (
        "il movimento riconciliato è l'unico legame con l'immobile: senza "
        "questa sorgente sparirebbe dalla riconciliazione"
    )


def test_conto_di_destinazione_su_un_addebito(scenario):
    owner, immobile, immobile2 = scenario
    conto = _conto(owner, 5)

    u = User.objects.create_user("mig_inq_dest", password="pwd123!")
    tenant = TenantProfile.objects.create(
        user=u, property=immobile2, nominativo="Inquilino", giorno_pagamento_affitto=1
    )
    room = Room.objects.create(property=immobile2, nome="Camera dest", ordinamento=3)
    assignment = RoomAssignment.objects.create(
        room=room,
        tenant=tenant,
        valid_from=datetime.date(2024, 9, 1),
        canone_mensile=Decimal("400"),
    )
    Receivable.objects.create(
        assignment=assignment,
        causale=Receivable.Causale.AFFITTO,
        competenza_da=datetime.date(2026, 6, 1),
        competenza_a=datetime.date(2026, 6, 30),
        importo_dovuto=Decimal("400"),
        scadenza=datetime.date(2026, 6, 1),
        stato=StatoPagamento.ATTESO,
        bank_account_destinazione=conto,
    )

    _esegui_backfill()

    assert conto.properties.filter(pk=immobile2.pk).exists()


def test_idempotente(scenario):
    owner, immobile, _immobile2 = scenario
    conto = _conto(owner, 6)

    _esegui_backfill()
    collega_conti_agli_immobili(django_apps, None)

    assert list(conto.properties.values_list("pk", flat=True)) == [immobile.pk]
