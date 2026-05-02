"""
Test per l'app properties.

Coprono:
- OwnershipShare: somma quote attive deve fare 1.0 (vincolo clean())
- RoomAssignment: nessun overlap per la stessa stanza
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from properties.models import OwnerBankAccount, OwnerProfile, OwnershipShare, Room, RoomAssignment, TenantProfile


# ---------------------------------------------------------------------------
# Fixture comuni
# ---------------------------------------------------------------------------


@pytest.fixture
def user_a(db):
    return User.objects.create_user("sandro", email="sandro@v.it", password="pwd")


@pytest.fixture
def user_b(db):
    return User.objects.create_user("bruna", email="bruna@v.it", password="pwd")


@pytest.fixture
def user_c(db):
    return User.objects.create_user("fabio", email="fabio@v.it", password="pwd")


@pytest.fixture
def user_inquilino(db):
    return User.objects.create_user("mariasevera", email="ms@v.it", password="pwd")


@pytest.fixture
def user_inquilino_2(db):
    return User.objects.create_user("davide", email="davide@v.it", password="pwd")


@pytest.fixture
def owner_a(db, user_a):
    return OwnerProfile.objects.create(user=user_a, nominativo="Sandro Dentella")


@pytest.fixture
def owner_b(db, user_b):
    return OwnerProfile.objects.create(user=user_b, nominativo="Bruna Dentella")


@pytest.fixture
def owner_c(db, user_c):
    return OwnerProfile.objects.create(user=user_c, nominativo="Fabio Dentella")


@pytest.fixture
def tenant(db, user_inquilino):
    return TenantProfile.objects.create(
        user=user_inquilino,
        nominativo="Mariasevera",
        giorno_pagamento_affitto=1,
    )


@pytest.fixture
def tenant_2(db, user_inquilino_2):
    return TenantProfile.objects.create(
        user=user_inquilino_2,
        nominativo="Davide",
        giorno_pagamento_affitto=5,
    )


@pytest.fixture
def room(db):
    return Room.objects.create(nome="Camera 1", ordinamento=1)


# ---------------------------------------------------------------------------
# Test OwnershipShare
# ---------------------------------------------------------------------------


class TestOwnershipShare:
    """Verifica il vincolo di somma quote = 1.0."""

    def test_tre_quote_uguali_valide(self, db, owner_a, owner_b, owner_c):
        """Tre quote da 1/3 ciascuna devono superare clean()."""
        data = datetime.date(2024, 9, 1)
        quota = Decimal("0.3333")

        OwnershipShare.objects.create(owner=owner_a, valid_from=data, quota=quota)
        OwnershipShare.objects.create(owner=owner_b, valid_from=data, quota=quota)

        # La terza quota porta il totale a ~1.0 (0.3334 per arrotondamento)
        share_c = OwnershipShare(owner=owner_c, valid_from=data, quota=Decimal("0.3334"))
        share_c.full_clean()  # non deve sollevare eccezioni

    def test_somma_maggiore_di_uno_invalida(self, db, owner_a, owner_b):
        """Una quota che porta il totale > 1.0 deve sollevare ValidationError."""
        data = datetime.date(2024, 9, 1)
        OwnershipShare.objects.create(owner=owner_a, valid_from=data, quota=Decimal("0.6"))

        share_b = OwnershipShare(owner=owner_b, valid_from=data, quota=Decimal("0.6"))
        with pytest.raises(ValidationError):
            share_b.full_clean()

    def test_stesso_owner_quota_duplicata_invalida(self, db, owner_a, owner_b):
        """Lo stesso proprietario non può avere due quote attive nella stessa data."""
        data = datetime.date(2024, 9, 1)
        OwnershipShare.objects.create(owner=owner_a, valid_from=data, quota=Decimal("0.5"))

        # Stessa data, stesso owner: deve fallire
        share_dup = OwnershipShare(owner=owner_a, valid_from=data, quota=Decimal("0.3"))
        with pytest.raises(ValidationError):
            share_dup.full_clean()

    def test_somma_quote_attive_uguale_a_uno(self, db, owner_a, owner_b, owner_c):
        """Dopo aver inserito tutte le quote, la somma deve essere 1.0."""
        from django.db.models import Q

        data = datetime.date(2024, 9, 1)
        OwnershipShare.objects.create(owner=owner_a, valid_from=data, quota=Decimal("0.3333"))
        OwnershipShare.objects.create(owner=owner_b, valid_from=data, quota=Decimal("0.3333"))
        OwnershipShare.objects.create(owner=owner_c, valid_from=data, quota=Decimal("0.3334"))

        # Verifica diretta che la somma in DB sia 1.0
        quote_attive = OwnershipShare.objects.filter(
            valid_from__lte=data,
        ).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gt=data)
        )
        somma = sum(s.quota for s in quote_attive)
        assert abs(somma - Decimal("1.0")) < Decimal("0.001")

    def test_quota_zero_invalida(self, db, owner_a):
        """Una quota pari a 0 deve essere rifiutata."""
        share = OwnershipShare(owner=owner_a, valid_from=datetime.date(2024, 1, 1), quota=Decimal("0"))
        with pytest.raises(ValidationError):
            share.full_clean()

    def test_quote_versionate_non_interferiscono(self, db, owner_a, owner_b, owner_c):
        """Quote del periodo 1 (valid_to=data_2) non influenzano il periodo 2 (valid_from=data_2).

        Semantica di valid_to: esclusiva. Una quota con valid_to=data_2 NON è più attiva
        a data_2 (usa valid_to__gt per il filtro). I due periodi sono distinti e non
        devono interferire nella validazione della somma.
        """
        data_1 = datetime.date(2024, 9, 1)
        data_2 = datetime.date(2025, 6, 1)

        # Periodo 1: tre quote da 1/3, valide fino a data_2 (esclusiva)
        OwnershipShare.objects.create(owner=owner_a, valid_from=data_1, valid_to=data_2, quota=Decimal("0.3333"))
        OwnershipShare.objects.create(owner=owner_b, valid_from=data_1, valid_to=data_2, quota=Decimal("0.3333"))
        OwnershipShare.objects.create(owner=owner_c, valid_from=data_1, valid_to=data_2, quota=Decimal("0.3334"))

        # Periodo 2: Fabio esce, due quote da 0.5 (Sandro e Bruna)
        # La prima inserzione da sola (0.5) non supera 1.0 e non è duplicata -> passa
        share_a2 = OwnershipShare(owner=owner_a, valid_from=data_2, quota=Decimal("0.5"))
        share_a2.full_clean()
        share_a2.save()

        # La seconda completa il totale a 1.0 -> passa
        share_b2 = OwnershipShare(owner=owner_b, valid_from=data_2, quota=Decimal("0.5"))
        share_b2.full_clean()
        share_b2.save()

        # Verifica finale: somma a data_2 = 1.0
        from django.db.models import Q
        quote_at_data_2 = OwnershipShare.objects.filter(
            valid_from__lte=data_2,
        ).filter(Q(valid_to__isnull=True) | Q(valid_to__gt=data_2))
        somma = sum(s.quota for s in quote_at_data_2)
        assert abs(somma - Decimal("1.0")) < Decimal("0.001")


# ---------------------------------------------------------------------------
# Test RoomAssignment
# ---------------------------------------------------------------------------


class TestRoomAssignment:
    """Verifica il vincolo di no-overlap per la stessa stanza."""

    def test_singola_assegnazione_valida(self, db, room, tenant):
        """Una singola assegnazione deve essere creata senza problemi."""
        assignment = RoomAssignment(
            room=room,
            tenant=tenant,
            valid_from=datetime.date(2024, 9, 1),
            canone_mensile=Decimal("450"),
            deposito_versato=Decimal("900"),
        )
        assignment.full_clean()
        assignment.save()
        assert assignment.pk is not None

    def test_assegnazioni_consecutive_valide(self, db, room, tenant, tenant_2):
        """Due assegnazioni consecutive (senza overlap) per la stessa stanza."""
        RoomAssignment.objects.create(
            room=room,
            tenant=tenant,
            valid_from=datetime.date(2024, 9, 1),
            valid_to=datetime.date(2025, 3, 31),
            canone_mensile=Decimal("450"),
            deposito_versato=Decimal("900"),
        )

        # Il secondo inizia dopo la fine del primo: non c'è overlap
        assignment_2 = RoomAssignment(
            room=room,
            tenant=tenant_2,
            valid_from=datetime.date(2025, 4, 1),
            canone_mensile=Decimal("480"),
            deposito_versato=Decimal("960"),
        )
        assignment_2.full_clean()  # non deve sollevare eccezioni

    def test_overlap_stessa_stanza_invalido(self, db, room, tenant, tenant_2):
        """Due assegnazioni sovrapposte per la stessa stanza devono fallire."""
        RoomAssignment.objects.create(
            room=room,
            tenant=tenant,
            valid_from=datetime.date(2024, 9, 1),
            valid_to=datetime.date(2025, 6, 30),
            canone_mensile=Decimal("450"),
            deposito_versato=Decimal("900"),
        )

        # Inizia durante l'assegnazione esistente: overlap
        assignment_2 = RoomAssignment(
            room=room,
            tenant=tenant_2,
            valid_from=datetime.date(2025, 3, 1),  # dentro il periodo del primo
            canone_mensile=Decimal("480"),
            deposito_versato=Decimal("960"),
        )
        with pytest.raises(ValidationError):
            assignment_2.full_clean()

    def test_overlap_aperto_invalido(self, db, room, tenant, tenant_2):
        """Un assignment aperto (valid_to=None) blocca qualsiasi successivo sulla stessa stanza."""
        RoomAssignment.objects.create(
            room=room,
            tenant=tenant,
            valid_from=datetime.date(2024, 9, 1),
            valid_to=None,  # aperto
            canone_mensile=Decimal("450"),
            deposito_versato=Decimal("900"),
        )

        assignment_2 = RoomAssignment(
            room=room,
            tenant=tenant_2,
            valid_from=datetime.date(2025, 1, 1),
            canone_mensile=Decimal("480"),
            deposito_versato=Decimal("960"),
        )
        with pytest.raises(ValidationError):
            assignment_2.full_clean()

    def test_stanze_diverse_nessun_conflitto(self, db, room, tenant, tenant_2):
        """Assegnazioni sovrapposte ma su stanze diverse sono valide."""
        room_2 = Room.objects.create(nome="Camera 2", ordinamento=2)

        RoomAssignment.objects.create(
            room=room,
            tenant=tenant,
            valid_from=datetime.date(2024, 9, 1),
            canone_mensile=Decimal("450"),
            deposito_versato=Decimal("900"),
        )

        # Stessa finestra temporale, stanza diversa: deve passare
        assignment_2 = RoomAssignment(
            room=room_2,
            tenant=tenant_2,
            valid_from=datetime.date(2024, 9, 1),
            canone_mensile=Decimal("420"),
            deposito_versato=Decimal("840"),
        )
        assignment_2.full_clean()  # non deve sollevare eccezioni


# ---------------------------------------------------------------------------
# Test OwnerBankAccount
# ---------------------------------------------------------------------------


class TestOwnerBankAccount:
    """Smoke test per OwnerBankAccount."""

    def test_creazione(self, db, owner_a):
        account = OwnerBankAccount.objects.create(
            owner=owner_a,
            banca="Banca Mediolanum",
            intestatario="Sandro Dentella",
            iban="IT60X0542811101000000123456",
        )
        assert str(account) == "Sandro Dentella — Banca Mediolanum (3456)"
