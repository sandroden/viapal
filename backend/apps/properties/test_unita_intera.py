"""
Test per ``Property.tipo_gestione`` e la Room implicita degli immobili a
unità intera.

Coprono:
- creazione Property(tipo_gestione=UNITA_INTERA) -> Room "Appartamento" auto-creata
- vincolo massimo 1 Room su unità intera (model + API)
- cambio tipo_gestione -> UNITA_INTERA rifiutato con 2+ stanze (model + serializer)
- prima-assegnazione con 'room' opzionale su unità intera, obbligatorio su stanze
- esposizione tipo_gestione: PropertySerializer, /api/auth/user/, dashboard inquilino
- smoke test genera_pagamenti_mese + ripartizione utenze su unità intera con 1 inquilino
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from rest_framework.test import APIClient

from properties.models import Property, PropertyMembership, Room, RoomAssignment, TenantProfile

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gruppo_proprietari(db):
    grp, _ = Group.objects.get_or_create(name="proprietari")
    return grp


@pytest.fixture
def gruppo_inquilini(db):
    grp, _ = Group.objects.get_or_create(name="inquilini")
    return grp


@pytest.fixture
def unita(db):
    """Immobile a unità intera: la Room implicita viene creata dal signal."""
    return Property.objects.create(
        nome="Loft Unità", tipo_gestione=Property.TipoGestione.UNITA_INTERA
    )


@pytest.fixture
def user_owner_unita(db, gruppo_proprietari, unita):
    u = User.objects.create_user("unita_owner", email="uo@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=unita, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    return u


@pytest.fixture
def client_unita(user_owner_unita, unita):
    c = APIClient(enforce_csrf_checks=False)
    c.force_login(user_owner_unita)
    c.credentials(HTTP_X_PROPERTY_ID=str(unita.pk))
    return c


@pytest.fixture
def tenant_unita(db, gruppo_inquilini, unita):
    u = User.objects.create_user("unita_tenant", email="ut@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    return TenantProfile.objects.create(
        user=u, property=unita, nominativo="Inquilino Unità", giorno_pagamento_affitto=1,
    )


@pytest.fixture
def user_owner_stanze(db, gruppo_proprietari, immobile):
    u = User.objects.create_user("stanze_owner", email="so@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    return u


@pytest.fixture
def client_stanze(user_owner_stanze, immobile):
    c = APIClient(enforce_csrf_checks=False)
    c.force_login(user_owner_stanze)
    c.credentials(HTTP_X_PROPERTY_ID=str(immobile.pk))
    return c


@pytest.fixture
def tenant_stanze(db, gruppo_inquilini, immobile):
    u = User.objects.create_user("stanze_tenant", email="st@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    return TenantProfile.objects.create(
        user=u, property=immobile, nominativo="Inquilino Stanze", giorno_pagamento_affitto=1,
    )


# ---------------------------------------------------------------------------
# Room implicita
# ---------------------------------------------------------------------------


class TestRoomImplicita:
    def test_creazione_property_unita_intera_crea_room(self, unita):
        assert unita.rooms.count() == 1
        assert unita.rooms.first().nome == "Appartamento"

    def test_property_stanze_non_crea_room(self, immobile):
        assert immobile.rooms.count() == 0

    def test_cambio_a_unita_intera_senza_stanze_crea_room(self, immobile):
        immobile.tipo_gestione = Property.TipoGestione.UNITA_INTERA
        immobile.full_clean()
        immobile.save()
        assert immobile.rooms.count() == 1
        assert immobile.rooms.first().nome == "Appartamento"

    def test_cambio_a_unita_intera_con_1_stanza_non_duplica(self, immobile):
        Room.objects.create(property=immobile, nome="Unica")
        immobile.tipo_gestione = Property.TipoGestione.UNITA_INTERA
        immobile.full_clean()
        immobile.save()
        assert immobile.rooms.count() == 1
        assert immobile.rooms.first().nome == "Unica"


# ---------------------------------------------------------------------------
# Seed demo: Casa Lago è un'unità intera con la sola stanza del seed
# ---------------------------------------------------------------------------


class TestSeedDemoUnitaIntera:
    def test_casa_lago_unita_intera_una_sola_stanza(self, db):
        """seed_demo crea Casa Lago come unità intera senza violare il vincolo
        max-1 Room: la stanza del seed resta l'unica (l'ordine di creazione
        evita la 'Appartamento' implicita del signal)."""
        call_command("seed_demo")
        prop = Property.objects.get(nome="Casa Lago")
        assert prop.tipo_gestione == Property.TipoGestione.UNITA_INTERA
        assert prop.rooms.count() == 1
        assert prop.rooms.first().nome == "Appartamento intero"


# ---------------------------------------------------------------------------
# Vincolo massimo 1 stanza su unità intera
# ---------------------------------------------------------------------------


class TestVincoloUnaStanza:
    def test_seconda_room_su_unita_intera_rifiutata_model(self, unita):
        seconda = Room(property=unita, nome="Seconda")
        with pytest.raises(ValidationError):
            seconda.full_clean()

    def test_seconda_room_su_stanze_permessa_model(self, immobile):
        Room.objects.create(property=immobile, nome="Prima")
        seconda = Room(property=immobile, nome="Seconda")
        seconda.full_clean()  # non deve sollevare

    def test_cambio_tipo_rifiutato_con_2_stanze_model(self, immobile):
        Room.objects.create(property=immobile, nome="A")
        Room.objects.create(property=immobile, nome="B")
        immobile.tipo_gestione = Property.TipoGestione.UNITA_INTERA
        with pytest.raises(ValidationError):
            immobile.full_clean()

    def test_cambio_tipo_permesso_con_0_stanze_model(self, immobile):
        immobile.tipo_gestione = Property.TipoGestione.UNITA_INTERA
        immobile.full_clean()  # non deve sollevare

    def test_cambio_a_stanze_sempre_libero_model(self, unita):
        # 'unita' ha già la Room implicita, ma il ritorno a 'stanze' non è
        # mai vincolato dal numero di stanze.
        Room.objects.create(property=unita, nome="Extra")  # 2 stanze totali
        # full_clean del modello Room fallirebbe se tipo restasse unita_intera:
        # qui verifichiamo solo il cambio tipo, non la creazione della stanza.
        unita.tipo_gestione = Property.TipoGestione.STANZE
        unita.full_clean()  # non deve sollevare


# ---------------------------------------------------------------------------
# API: Property e Room
# ---------------------------------------------------------------------------


class TestAPIPropertyRoom:
    def test_api_create_property_unita_intera_crea_room(self, client_stanze):
        resp = client_stanze.post(
            "/api/v1/properties/",
            {"nome": "Bilocale API", "tipo_gestione": "unita_intera"},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        data = resp.json()
        assert data["tipo_gestione"] == "unita_intera"
        prop = Property.objects.get(pk=data["id"])
        assert prop.rooms.count() == 1
        assert prop.rooms.first().nome == "Appartamento"

    def test_api_seconda_room_su_unita_intera_rifiutata(self, client_unita):
        resp = client_unita.post("/api/v1/rooms/", {"nome": "Seconda"}, format="json")
        assert resp.status_code == 400, resp.content

    def test_api_seconda_room_su_stanze_permessa(self, client_stanze):
        resp = client_stanze.post("/api/v1/rooms/", {"nome": "Prima"}, format="json")
        assert resp.status_code == 201, resp.content
        resp2 = client_stanze.post("/api/v1/rooms/", {"nome": "Seconda"}, format="json")
        assert resp2.status_code == 201, resp2.content

    def test_api_cambio_tipo_rifiutato_con_2_stanze(self, client_stanze, immobile):
        Room.objects.create(property=immobile, nome="A")
        Room.objects.create(property=immobile, nome="B")
        resp = client_stanze.patch(
            f"/api/v1/properties/{immobile.pk}/",
            {"tipo_gestione": "unita_intera"},
            format="json",
        )
        assert resp.status_code == 400, resp.content

    def test_api_cambio_tipo_permesso_con_1_stanza(self, client_stanze, immobile):
        Room.objects.create(property=immobile, nome="Unica")
        resp = client_stanze.patch(
            f"/api/v1/properties/{immobile.pk}/",
            {"tipo_gestione": "unita_intera"},
            format="json",
        )
        assert resp.status_code == 200, resp.content


# ---------------------------------------------------------------------------
# Esposizione tipo_gestione
# ---------------------------------------------------------------------------


class TestEsposizioneTipoGestione:
    def test_in_property_serializer(self, client_unita, unita):
        resp = client_unita.get(f"/api/v1/properties/{unita.pk}/")
        assert resp.status_code == 200
        assert resp.json()["tipo_gestione"] == "unita_intera"

    def test_in_user_endpoint(self, client_unita):
        resp = client_unita.get("/api/auth/user/")
        assert resp.status_code == 200
        props = resp.json()["properties"]
        assert any(p["tipo_gestione"] == "unita_intera" for p in props)

    def test_in_public_gallery(self, unita):
        unita.pubblica = True
        unita.save(update_fields=["pubblica"])
        client = APIClient(enforce_csrf_checks=False)
        resp = client.get(f"/api/v1/public/galleria/{unita.slug}/")
        assert resp.status_code == 200, resp.content
        assert resp.json()["tipo_gestione"] == "unita_intera"

    def test_in_dashboard_inquilino(self, tenant_unita):
        room = tenant_unita.property.rooms.first()
        RoomAssignment.objects.create(
            room=room,
            tenant=tenant_unita,
            valid_from=datetime.date(2026, 1, 1),
            canone_mensile=Decimal("900"),
        )
        c = APIClient(enforce_csrf_checks=False)
        c.force_login(tenant_unita.user)
        resp = c.get("/api/v1/dashboard/inquilino/")
        assert resp.status_code == 200
        assert resp.json()["stanza_corrente"]["tipo_gestione"] == "unita_intera"


# ---------------------------------------------------------------------------
# prima-assegnazione: 'room' opzionale
# ---------------------------------------------------------------------------


class TestPrimaAssegnazioneRoomOpzionale:
    URL = "/api/v1/room-assignments/prima-assegnazione/"

    def test_senza_room_su_unita_intera_usa_room_implicita(
        self, client_unita, tenant_unita, unita
    ):
        payload = {
            "tenant": tenant_unita.id,
            "valid_from": "2026-08-01",
            "canone_mensile": "900.00",
            "ciclo_fatturazione": "solare",
        }
        resp = client_unita.post(self.URL, payload, format="json")
        assert resp.status_code == 201, resp.content
        assignment = RoomAssignment.objects.get(tenant=tenant_unita)
        assert assignment.room == unita.rooms.first()

    def test_senza_room_su_stanze_400(self, client_stanze, tenant_stanze):
        payload = {
            "tenant": tenant_stanze.id,
            "valid_from": "2026-08-01",
            "canone_mensile": "450.00",
            "ciclo_fatturazione": "solare",
        }
        resp = client_stanze.post(self.URL, payload, format="json")
        assert resp.status_code == 400, resp.content
        assert "room" in resp.json()


# ---------------------------------------------------------------------------
# Smoke test billing: pagatore unico su unità intera
# ---------------------------------------------------------------------------


class TestBillingUnitaIntera:
    def test_genera_pagamenti_mese_pagatore_unico(self, unita, tenant_unita):
        from billing.calc.rent import genera_pagamenti_mese
        from billing.models import Receivable

        room = unita.rooms.first()
        RoomAssignment.objects.create(
            room=room,
            tenant=tenant_unita,
            valid_from=datetime.date(2026, 5, 1),
            canone_mensile=Decimal("900.00"),
        )
        esito = genera_pagamenti_mese(2026, 5, property=unita)
        assert len(esito["payments"]) == 1
        rec = Receivable.objects.get(pk=esito["payments"][0])
        assert rec.importo_dovuto == Decimal("900.00")
        assert rec.assignment.tenant_id == tenant_unita.pk

    def test_ripartizione_utenze_pagatore_unico_100_percento(self, unita, tenant_unita):
        from billing.calc.utility import calcola_conguaglio_periodo
        from billing.models import Supplier, UtilityBill, UtilityChargePeriod

        room = unita.rooms.first()
        RoomAssignment.objects.create(
            room=room,
            tenant=tenant_unita,
            valid_from=datetime.date(2026, 5, 1),
            canone_mensile=Decimal("900.00"),
        )
        supplier = Supplier.objects.create(property=unita, nome="Enel Unità", tipo="energia")
        period = UtilityChargePeriod.objects.create(
            property=unita,
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            criterio_ripartizione="pro_rata_giorni",
            data_invio=datetime.date(2026, 6, 1),
        )
        UtilityBill.objects.create(
            immobile=unita,
            supplier=supplier,
            numero_fattura="ENEL-UNITA-1",
            data_emissione=datetime.date(2026, 5, 15),
            periodo_da=datetime.date(2026, 5, 1),
            periodo_a=datetime.date(2026, 5, 31),
            importo_totale=Decimal("120.00"),
        )

        risultato = calcola_conguaglio_periodo(period.pk)
        assert len(risultato["quote"]) == 1
        assert risultato["quote"][0]["quota"] == Decimal("120.00")
        assert risultato["totale_periodo"] == Decimal("120.00")
