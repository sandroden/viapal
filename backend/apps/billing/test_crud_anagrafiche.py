"""
Test CRUD anagrafiche billing (Fase D — sostituzione admin Django).

Coprono:
- ExpenseCategoryViewSet: da read-only a CRUD (property dal server,
  delete protetto → 409, codice univoco per immobile);
- SupplierViewSet (nuovo): CRUD property-scoped;
- AnnualUtilityCostViewSet (nuovo): CRUD property-scoped.

Per ogni endpoint: CRUD felice da membro operativo, 403 scritture per
sola_lettura e inquilini, isolamento cross-property.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from billing.models import AnnualUtilityCost, Expense, ExpenseCategory, Supplier
from properties.models import OwnerProfile, PropertyMembership, TenantProfile

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


def _client(user):
    c = APIClient(enforce_csrf_checks=False)
    c.force_login(user)
    return c


@pytest.fixture
def user_owner(immobile, gruppo_proprietari):
    u = User.objects.create_user("bil_owner", email="bil_owner@v.it", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.PROPRIETARIO
    )
    return u


@pytest.fixture
def owner_profile(user_owner):
    return OwnerProfile.objects.create(user=user_owner, nominativo="Owner Billing")


@pytest.fixture
def client_operativo(user_owner, owner_profile):
    return _client(user_owner)


@pytest.fixture
def client_sola_lettura(immobile, gruppo_proprietari):
    u = User.objects.create_user("bil_readonly", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.SOLA_LETTURA
    )
    return _client(u)


@pytest.fixture
def client_inquilino(immobile, gruppo_inquilini):
    u = User.objects.create_user("bil_inq", email="bil_inq@v.it", password="pwd123!")
    u.groups.add(gruppo_inquilini)
    TenantProfile.objects.create(
        user=u, property=immobile, nominativo="Inquilino Billing",
        giorno_pagamento_affitto=1,
    )
    return _client(u)


@pytest.fixture
def categoria(immobile):
    return ExpenseCategory.objects.create(
        property=immobile, nome="Manutenzione", codice="manutenzione"
    )


@pytest.fixture
def supplier(immobile):
    return Supplier.objects.create(
        property=immobile, nome="Fornitore Test", tipo=Supplier.TipoFornitore.ENERGIA
    )


@pytest.fixture
def costo_annuale(immobile):
    return AnnualUtilityCost.objects.create(
        property=immobile,
        voce=AnnualUtilityCost.VoceAnnuale.TARI,
        anno=2026,
        importo_annuale=Decimal("300.00"),
        valid_from=datetime.date(2026, 1, 1),
        valid_to=datetime.date(2026, 12, 31),
    )


@pytest.fixture
def mondo_b(immobile2):
    """Oggetti billing sul secondo immobile, per l'isolamento cross-property."""
    from types import SimpleNamespace

    m = SimpleNamespace(property=immobile2)
    m.categoria = ExpenseCategory.objects.create(
        property=immobile2, nome="Manutenzione B", codice="manutenzione-b"
    )
    m.supplier = Supplier.objects.create(
        property=immobile2, nome="Fornitore B", tipo=Supplier.TipoFornitore.GAS
    )
    m.costo_annuale = AnnualUtilityCost.objects.create(
        property=immobile2,
        voce=AnnualUtilityCost.VoceAnnuale.TARI,
        anno=2026,
        importo_annuale=Decimal("250.00"),
        valid_from=datetime.date(2026, 1, 1),
    )
    return m


# ---------------------------------------------------------------------------
# ExpenseCategoryViewSet
# ---------------------------------------------------------------------------


class TestExpenseCategoryCrud:
    def test_create_atterra_su_immobile_attivo(self, client_operativo, immobile):
        resp = client_operativo.post(
            "/api/v1/expense-categories/",
            {"nome": "Assicurazione", "codice": "assicurazione",
             "ripartibile_inquilini": False},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        creata = ExpenseCategory.objects.get(pk=resp.json()["id"])
        assert creata.property_id == immobile.id
        assert resp.json()["property"] == immobile.id

    def test_codice_duplicato_400(self, client_operativo, categoria):
        resp = client_operativo.post(
            "/api/v1/expense-categories/",
            {"nome": "Doppione", "codice": categoria.codice},
            format="json",
        )
        assert resp.status_code == 400
        assert "codice" in resp.json()

    def test_stesso_codice_su_altro_immobile_ok(self, client_operativo, mondo_b):
        # Il vincolo è per immobile: il codice di B è libero su A.
        resp = client_operativo.post(
            "/api/v1/expense-categories/",
            {"nome": "Manutenzione B", "codice": mondo_b.categoria.codice},
            format="json",
        )
        assert resp.status_code == 201, resp.content

    def test_update(self, client_operativo, categoria):
        resp = client_operativo.patch(
            f"/api/v1/expense-categories/{categoria.id}/",
            {"nome": "Manutenzione ordinaria", "ripartibile_inquilini": True},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        categoria.refresh_from_db()
        assert categoria.nome == "Manutenzione ordinaria"
        assert categoria.ripartibile_inquilini is True

    def test_delete_inutilizzata(self, client_operativo, categoria):
        resp = client_operativo.delete(f"/api/v1/expense-categories/{categoria.id}/")
        assert resp.status_code == 204

    def test_delete_con_spese_409(self, client_operativo, categoria, owner_profile):
        Expense.objects.create(
            property=categoria.property,
            data=datetime.date(2026, 3, 1),
            category=categoria,
            importo=Decimal("100"),
            descrizione="Spesa",
            anticipata_da_owner=owner_profile,
        )
        resp = client_operativo.delete(f"/api/v1/expense-categories/{categoria.id}/")
        assert resp.status_code == 409
        assert ExpenseCategory.objects.filter(pk=categoria.id).exists()

    def test_sola_lettura_non_scrive(self, client_sola_lettura, categoria):
        resp = client_sola_lettura.post(
            "/api/v1/expense-categories/", {"nome": "X", "codice": "x"}, format="json"
        )
        assert resp.status_code == 403

    def test_inquilino_non_accede(self, client_inquilino):
        resp = client_inquilino.post(
            "/api/v1/expense-categories/", {"nome": "X", "codice": "x"}, format="json"
        )
        assert resp.status_code == 403

    def test_categoria_altrui_404(self, client_operativo, mondo_b):
        resp = client_operativo.patch(
            f"/api/v1/expense-categories/{mondo_b.categoria.id}/",
            {"nome": "Hack"}, format="json",
        )
        assert resp.status_code == 404
        resp = client_operativo.delete(
            f"/api/v1/expense-categories/{mondo_b.categoria.id}/"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# SupplierViewSet
# ---------------------------------------------------------------------------


class TestSupplierCrud:
    def test_create_atterra_su_immobile_attivo(self, client_operativo, immobile):
        resp = client_operativo.post(
            "/api/v1/suppliers/",
            {"nome": "Enel", "tipo": "energia", "partita_iva": "00934061003"},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        creato = Supplier.objects.get(pk=resp.json()["id"])
        assert creato.property_id == immobile.id
        assert creato.tipo == "energia"

    def test_list_scopata(self, client_operativo, supplier, mondo_b):
        resp = client_operativo.get("/api/v1/suppliers/")
        assert resp.status_code == 200
        ids = {s["id"] for s in resp.json()}
        assert supplier.id in ids
        assert mondo_b.supplier.id not in ids

    def test_update(self, client_operativo, supplier):
        resp = client_operativo.patch(
            f"/api/v1/suppliers/{supplier.id}/",
            {"contatto": "800900800"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        supplier.refresh_from_db()
        assert supplier.contatto == "800900800"

    def test_delete(self, client_operativo, supplier):
        resp = client_operativo.delete(f"/api/v1/suppliers/{supplier.id}/")
        assert resp.status_code == 204

    def test_delete_con_spese_409(
        self, client_operativo, supplier, categoria, owner_profile
    ):
        Expense.objects.create(
            property=supplier.property,
            data=datetime.date(2026, 3, 1),
            category=categoria,
            supplier=supplier,
            importo=Decimal("50"),
            descrizione="Spesa fornitore",
            anticipata_da_owner=owner_profile,
        )
        resp = client_operativo.delete(f"/api/v1/suppliers/{supplier.id}/")
        assert resp.status_code == 409
        assert Supplier.objects.filter(pk=supplier.id).exists()

    def test_sola_lettura_non_scrive(self, client_sola_lettura):
        resp = client_sola_lettura.post(
            "/api/v1/suppliers/", {"nome": "X", "tipo": "altro"}, format="json"
        )
        assert resp.status_code == 403

    def test_inquilino_non_accede(self, client_inquilino):
        resp = client_inquilino.get("/api/v1/suppliers/")
        assert resp.status_code == 403

    def test_fornitore_altrui_404(self, client_operativo, mondo_b):
        resp = client_operativo.delete(f"/api/v1/suppliers/{mondo_b.supplier.id}/")
        assert resp.status_code == 404
        assert Supplier.objects.filter(pk=mondo_b.supplier.id).exists()


# ---------------------------------------------------------------------------
# AnnualUtilityCostViewSet
# ---------------------------------------------------------------------------


class TestAnnualUtilityCostCrud:
    def test_create_atterra_su_immobile_attivo(self, client_operativo, immobile):
        resp = client_operativo.post(
            "/api/v1/annual-utility-costs/",
            {
                "voce": "tari",
                "anno": 2027,
                "importo_annuale": "320.00",
                "valid_from": "2027-01-01",
                "valid_to": "2027-12-31",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        creato = AnnualUtilityCost.objects.get(pk=resp.json()["id"])
        assert creato.property_id == immobile.id
        assert creato.importo_annuale == Decimal("320.00")

    def test_list_scopata(self, client_operativo, costo_annuale, mondo_b):
        resp = client_operativo.get("/api/v1/annual-utility-costs/")
        assert resp.status_code == 200
        ids = {c["id"] for c in resp.json()}
        assert costo_annuale.id in ids
        assert mondo_b.costo_annuale.id not in ids

    def test_update(self, client_operativo, costo_annuale):
        resp = client_operativo.patch(
            f"/api/v1/annual-utility-costs/{costo_annuale.id}/",
            {"importo_annuale": "310.00"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        costo_annuale.refresh_from_db()
        assert costo_annuale.importo_annuale == Decimal("310.00")

    def test_delete(self, client_operativo, costo_annuale):
        resp = client_operativo.delete(
            f"/api/v1/annual-utility-costs/{costo_annuale.id}/"
        )
        assert resp.status_code == 204

    def test_sola_lettura_non_scrive(self, client_sola_lettura, costo_annuale):
        resp = client_sola_lettura.patch(
            f"/api/v1/annual-utility-costs/{costo_annuale.id}/",
            {"importo_annuale": "1.00"},
            format="json",
        )
        assert resp.status_code == 403

    def test_inquilino_non_accede(self, client_inquilino):
        resp = client_inquilino.get("/api/v1/annual-utility-costs/")
        assert resp.status_code == 403

    def test_costo_altrui_404(self, client_operativo, mondo_b):
        resp = client_operativo.delete(
            f"/api/v1/annual-utility-costs/{mondo_b.costo_annuale.id}/"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TenantCondominioRateViewSet
# ---------------------------------------------------------------------------


def _tenant(property, nominativo):
    """TenantProfile con il suo utente (la FK a User è obbligatoria)."""
    u = User.objects.create_user(
        f"inq_{nominativo.lower()}_{property.pk}", password="pwd123!"
    )
    return TenantProfile.objects.create(
        user=u, property=property, nominativo=nominativo,
        giorno_pagamento_affitto=1,
    )


@pytest.fixture
def quota_base(immobile):
    from billing.models import TenantCondominioRate

    return TenantCondominioRate.objects.create(
        property=immobile,
        valid_from=datetime.date(2026, 1, 1),
        importo_mensile=Decimal("90.00"),
    )


class TestQuotaCondominioCrud:
    URL = "/api/v1/quote-condominio/"

    def test_create_senza_contratto(self, client_operativo, immobile):
        """Il caso dell'immobile appena creato: nessun contratto registrato,
        la quota base si inserisce lo stesso."""
        from billing.models import TenantCondominioRate

        resp = client_operativo.post(
            self.URL,
            {"valid_from": "2026-08-01", "importo_mensile": "100.00"},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        creata = TenantCondominioRate.objects.get(pk=resp.json()["id"])
        assert creata.property_id == immobile.id
        assert creata.contract_id is None
        assert creata.tenant_id is None

    def test_create_eccezione_per_inquilino(self, client_operativo, immobile):
        inq = _tenant(immobile, "Eccezione")
        resp = client_operativo.post(
            self.URL,
            {
                "tenant": inq.id,
                "valid_from": "2026-08-01",
                "importo_mensile": "70.00",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        assert resp.json()["tenant_nominativo"] == "Eccezione"

    def test_create_inquilino_di_altro_immobile_400(
        self, client_operativo, immobile2
    ):
        altrui = _tenant(immobile2, "Altrui")
        resp = client_operativo.post(
            self.URL,
            {
                "tenant": altrui.id,
                "valid_from": "2026-08-01",
                "importo_mensile": "70.00",
            },
            format="json",
        )
        assert resp.status_code == 400
        assert "tenant" in resp.json()

    def test_fine_validita_prima_dell_inizio_400(self, client_operativo):
        resp = client_operativo.post(
            self.URL,
            {
                "valid_from": "2026-08-01",
                "valid_to": "2026-07-01",
                "importo_mensile": "70.00",
            },
            format="json",
        )
        assert resp.status_code == 400
        assert "valid_to" in resp.json()

    def test_list_scopata(self, client_operativo, quota_base, immobile2):
        from billing.models import TenantCondominioRate

        altrui = TenantCondominioRate.objects.create(
            property=immobile2,
            valid_from=datetime.date(2026, 1, 1),
            importo_mensile=Decimal("50.00"),
        )
        resp = client_operativo.get(self.URL)
        assert resp.status_code == 200
        ids = {q["id"] for q in resp.json()}
        assert quota_base.id in ids
        assert altrui.id not in ids

    def test_filtro_per_inquilino(self, client_operativo, immobile, quota_base):
        """?tenant=<id>: la base più le eccezioni di quell'inquilino, non
        quelle degli altri."""
        from billing.models import TenantCondominioRate

        uno = _tenant(immobile, "Uno")
        due = _tenant(immobile, "Due")
        sua = TenantCondominioRate.objects.create(
            property=immobile, tenant=uno,
            valid_from=datetime.date(2026, 2, 1), importo_mensile=Decimal("70.00"),
        )
        altrui = TenantCondominioRate.objects.create(
            property=immobile, tenant=due,
            valid_from=datetime.date(2026, 2, 1), importo_mensile=Decimal("60.00"),
        )
        resp = client_operativo.get(f"{self.URL}?tenant={uno.id}")
        assert resp.status_code == 200
        ids = {q["id"] for q in resp.json()}
        assert ids == {quota_base.id, sua.id}
        assert altrui.id not in ids

    def test_update_e_delete(self, client_operativo, quota_base):
        from billing.models import TenantCondominioRate

        resp = client_operativo.patch(
            f"{self.URL}{quota_base.id}/", {"importo_mensile": "95.00"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        quota_base.refresh_from_db()
        assert quota_base.importo_mensile == Decimal("95.00")

        resp = client_operativo.delete(f"{self.URL}{quota_base.id}/")
        assert resp.status_code == 204
        assert not TenantCondominioRate.objects.filter(pk=quota_base.id).exists()

    def test_sola_lettura_non_scrive(self, client_sola_lettura, quota_base):
        resp = client_sola_lettura.patch(
            f"{self.URL}{quota_base.id}/", {"importo_mensile": "1.00"},
            format="json",
        )
        assert resp.status_code == 403

    def test_inquilino_non_accede(self, client_inquilino):
        resp = client_inquilino.get(self.URL)
        assert resp.status_code == 403

    def test_quota_altrui_404(self, client_operativo, immobile2):
        from billing.models import TenantCondominioRate

        altrui = TenantCondominioRate.objects.create(
            property=immobile2,
            valid_from=datetime.date(2026, 1, 1),
            importo_mensile=Decimal("50.00"),
        )
        resp = client_operativo.delete(f"{self.URL}{altrui.id}/")
        assert resp.status_code == 404
