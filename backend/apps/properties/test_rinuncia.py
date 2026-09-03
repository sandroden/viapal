"""
Test per la rinuncia a un'assegnazione (``RoomAssignment.rinunciata``).

Il caso reale: un inquilino versa la caparra, poi rinuncia prima di entrare.
L'assegnazione deve restare — è l'unica cosa che tiene agganciato il deposito,
la FK è PROTECT — ma non deve produrre nulla né occupare la stanza.

Coprono:
- ``valid_to == valid_from`` ammesso solo sotto rinuncia (vincolo DB + clean)
- la data di rinuncia da sola non è ammessa
- nessun addebito d'affitto, nessuna quota condominio
- la stanza resta assegnabile ad altri (no-overlap)
- l'inquilino non risulta fra gli attivi
- il costo di cessione non viene generato
- API: il flag governa da solo la fine occupazione, in entrambi i versi
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from properties.models import (
    PropertyMembership,
    Room,
    RoomAssignment,
    TenantProfile,
)

INGRESSO = datetime.date(2026, 9, 5)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def stanza(db, immobile):
    return Room.objects.create(property=immobile, nome="Camera Rinuncia", ordinamento=1)


@pytest.fixture
def make_tenant(db, immobile):
    counter = [0]

    def _make(nominativo="Rinunciatario"):
        counter[0] += 1
        u = User.objects.create_user(
            username=f"tenant_rin_{counter[0]}",
            email=f"tenant_rin_{counter[0]}@v.it",
            password="pwd",
        )
        return TenantProfile.objects.create(
            property=immobile,
            user=u,
            nominativo=f"{nominativo} {counter[0]}",
            giorno_pagamento_affitto=1,
        )

    return _make


@pytest.fixture
def rinuncia(db, stanza, make_tenant):
    """Un'assegnazione mai perfezionata: ingresso previsto il 5 settembre."""
    return RoomAssignment.objects.create(
        room=stanza,
        tenant=make_tenant("Simona"),
        valid_from=INGRESSO,
        valid_to=INGRESSO,
        rinunciata=True,
        data_rinuncia=datetime.date(2026, 8, 28),
        canone_mensile=Decimal("490.00"),
    )


# ---------------------------------------------------------------------------
# Vincoli sulle date
# ---------------------------------------------------------------------------


class TestVincoloDate:
    def test_durata_nulla_ammessa_solo_sotto_rinuncia(self, rinuncia):
        """La rinuncia esiste già come fixture: il vincolo DB l'ha accettata."""
        rinuncia.refresh_from_db()
        assert rinuncia.valid_to == rinuncia.valid_from

    def test_durata_nulla_rifiutata_senza_flag(self, db, stanza, make_tenant):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                RoomAssignment.objects.create(
                    room=stanza,
                    tenant=make_tenant("Ordinario"),
                    valid_from=INGRESSO,
                    valid_to=INGRESSO,
                    canone_mensile=Decimal("490.00"),
                )

    def test_clean_rifiuta_durata_nulla_senza_flag(self, db, stanza, make_tenant):
        a = RoomAssignment(
            room=stanza,
            tenant=make_tenant("Ordinario"),
            valid_from=INGRESSO,
            valid_to=INGRESSO,
            canone_mensile=Decimal("490.00"),
        )
        with pytest.raises(ValidationError) as exc:
            a.full_clean()
        assert "valid_to" in exc.value.message_dict

    def test_clean_allinea_la_fine_all_inizio(self, db, stanza, make_tenant):
        """Marcando la rinuncia non serve calcolare la fine: la mette il modello."""
        a = RoomAssignment(
            room=stanza,
            tenant=make_tenant("Simona"),
            valid_from=INGRESSO,
            valid_to=datetime.date(2026, 12, 31),
            rinunciata=True,
            canone_mensile=Decimal("490.00"),
        )
        a.full_clean()
        assert a.valid_to == INGRESSO

    def test_data_rinuncia_senza_flag_rifiutata(self, db, stanza, make_tenant):
        a = RoomAssignment(
            room=stanza,
            tenant=make_tenant("Ordinario"),
            valid_from=INGRESSO,
            rinunciata=False,
            data_rinuncia=datetime.date(2026, 8, 28),
            canone_mensile=Decimal("490.00"),
        )
        with pytest.raises(ValidationError) as exc:
            a.full_clean()
        assert "data_rinuncia" in exc.value.message_dict


# ---------------------------------------------------------------------------
# Effetti sui calcolatori
# ---------------------------------------------------------------------------


class TestNessunAddebito:
    def test_niente_affitto_nel_mese_dell_ingresso_previsto(self, rinuncia):
        from billing.calc.rent import genera_pagamenti_mese

        esito = genera_pagamenti_mese(2026, 9)
        assert esito["creati"] == 0
        assert esito["payments"] == []

    def test_niente_affitto_nemmeno_nei_mesi_successivi(self, rinuncia):
        from billing.calc.rent import genera_pagamenti_mese

        assert genera_pagamenti_mese(2026, 10)["creati"] == 0

    def test_un_inquilino_vero_nella_stessa_stanza_viene_comunque_fatturato(
        self, rinuncia, stanza, make_tenant
    ):
        """La rinuncia non deve né generare né far sparire gli altri."""
        from billing.calc.rent import genera_pagamenti_mese

        RoomAssignment.objects.create(
            room=stanza,
            tenant=make_tenant("Subentrante"),
            valid_from=INGRESSO,
            canone_mensile=Decimal("500.00"),
        )
        esito = genera_pagamenti_mese(2026, 9)
        assert esito["creati"] == 1


class TestStanzaLibera:
    def test_la_rinuncia_non_blocca_un_altro_inquilino(
        self, rinuncia, stanza, make_tenant
    ):
        """Il caso che rendeva la stanza inassegnabile: nessun overlap."""
        altro = RoomAssignment(
            room=stanza,
            tenant=make_tenant("Subentrante"),
            valid_from=INGRESSO,
            canone_mensile=Decimal("500.00"),
        )
        altro.full_clean()  # non solleva
        altro.save()
        assert RoomAssignment.objects.filter(room=stanza).count() == 2

    def test_una_rinuncia_non_e_bloccata_da_un_occupante(
        self, db, stanza, make_tenant
    ):
        RoomAssignment.objects.create(
            room=stanza,
            tenant=make_tenant("Occupante"),
            valid_from=datetime.date(2026, 1, 1),
            canone_mensile=Decimal("500.00"),
        )
        a = RoomAssignment(
            room=stanza,
            tenant=make_tenant("Rinunciatario"),
            valid_from=INGRESSO,
            rinunciata=True,
            canone_mensile=Decimal("490.00"),
        )
        a.full_clean()  # non solleva
        a.save()


class TestNonRisultaAttivo:
    def test_non_e_fra_gli_inquilini_attivi(self, rinuncia):
        attivi = TenantProfile.objects.attivi(oggi=INGRESSO)
        assert rinuncia.tenant not in attivi

    def test_un_occupante_vero_resta_attivo(self, rinuncia, stanza, make_tenant):
        vero = RoomAssignment.objects.create(
            room=stanza,
            tenant=make_tenant("Occupante"),
            valid_from=datetime.date(2026, 1, 1),
            canone_mensile=Decimal("500.00"),
        )
        assert vero.tenant in TenantProfile.objects.attivi(oggi=INGRESSO)


class TestCostoCessione:
    def test_non_genera_la_registrazione(self, db, stanza, make_tenant):
        """La registrazione si emette dopo l'ingresso reale, che qui non c'è."""
        from billing.models import Expense, Receivable

        a = RoomAssignment.objects.create(
            room=stanza,
            tenant=make_tenant("Simona"),
            valid_from=INGRESSO,
            valid_to=INGRESSO,
            rinunciata=True,
            canone_mensile=Decimal("490.00"),
            costo_cessione=Decimal("67.00"),
        )
        assert not Receivable.objects.filter(
            assignment=a, causale=Receivable.Causale.REGISTRAZIONE
        ).exists()
        assert not Expense.objects.filter(
            note__contains=f"[auto:cessione:{a.pk}]"
        ).exists()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.fixture
def client_proprietario(db, immobile):
    """Un membro dell'immobile, autenticato."""
    u = User.objects.create_user("proprietario_rin", email="p@v.it", password="pwd")
    grp, _ = Group.objects.get_or_create(name="proprietari")
    u.groups.add(grp)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    c = APIClient()
    c.force_authenticate(user=u)
    c.defaults["HTTP_X_PROPERTY_ID"] = str(immobile.pk)
    return c


class TestApiRinuncia:
    def test_marcare_la_rinuncia_chiude_sul_giorno_di_ingresso(
        self, client_proprietario, db, stanza, make_tenant
    ):
        a = RoomAssignment.objects.create(
            room=stanza,
            tenant=make_tenant("Simona"),
            valid_from=INGRESSO,
            canone_mensile=Decimal("490.00"),
        )
        resp = client_proprietario.patch(
            f"/api/v1/room-assignments/{a.pk}/",
            {"rinunciata": True, "data_rinuncia": "2026-08-28"},
            format="json",
        )
        assert resp.status_code == 200, resp.data
        a.refresh_from_db()
        assert a.rinunciata is True
        assert a.valid_to == INGRESSO
        assert a.data_rinuncia == datetime.date(2026, 8, 28)

    def test_togliere_la_rinuncia_riapre_l_assegnazione(
        self, client_proprietario, rinuncia
    ):
        resp = client_proprietario.patch(
            f"/api/v1/room-assignments/{rinuncia.pk}/",
            {"rinunciata": False},
            format="json",
        )
        assert resp.status_code == 200, resp.data
        rinuncia.refresh_from_db()
        assert rinuncia.rinunciata is False
        assert rinuncia.valid_to is None
        assert rinuncia.data_rinuncia is None

    def test_chiudere_un_assegnazione_senza_subentrante(
        self, client_proprietario, db, stanza, make_tenant
    ):
        """Il buco che costringeva a passare dall'admin: fine senza cessione."""
        a = RoomAssignment.objects.create(
            room=stanza,
            tenant=make_tenant("Uscente"),
            valid_from=datetime.date(2026, 6, 1),
            canone_mensile=Decimal("500.00"),
        )
        resp = client_proprietario.patch(
            f"/api/v1/room-assignments/{a.pk}/",
            {"valid_to": "2026-09-13"},
            format="json",
        )
        assert resp.status_code == 200, resp.data
        a.refresh_from_db()
        assert a.valid_to == datetime.date(2026, 9, 13)
        assert a.rinunciata is False

    def test_i_campi_sono_esposti_in_lettura(self, client_proprietario, rinuncia):
        resp = client_proprietario.get(f"/api/v1/room-assignments/{rinuncia.pk}/")
        assert resp.status_code == 200
        assert resp.data["rinunciata"] is True
        assert resp.data["data_rinuncia"] == "2026-08-28"
