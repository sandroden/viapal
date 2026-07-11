"""
Test di isolamento cross-property (multiproprietà) — rete di sicurezza.

Un utente della property 1 NON deve poter leggere né scrivere dati della
property 2, su nessun endpoint. Setup: due "mondi" completi e speculari:

- mondo A su ``immobile``: owner A (user + membership + OwnerProfile +
  OwnershipShare + conto), inquilino A (user + stanza + assignment +
  receivable), spesa, categoria, fornitore, periodo utenze, bolletta,
  movimento bancario, voci contabili (ledger/settlement/bilaterale);
- mondo B, identico, su ``immobile2``.

L'utente A è membro SOLO di A; l'utente B SOLO di B.

Coperture:
1. header ``X-Property-Id`` dell'immobile altrui → 403 su ogni endpoint
   di gestione (con controprova 200 sul proprio immobile);
2. senza header (fallback sulla propria property) le liste non contengono
   mai oggetti del mondo B;
3. dettaglio per id di oggetti del mondo B → 404 (fuori dal queryset);
4. scritture cross: la property di una Expense è assegnata dal server;
   registra-pagamento / azioni tenant su oggetti B → 403/404;
5. ruoli membership: gestore = come proprietario su A; sola_lettura
   legge (200) ma non scrive (403);
6. l'inquilino di A non vede nulla del mondo B;
7. impersonation: l'owner A non può impersonare l'inquilino B.
"""
import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from accounting.models import InterOwnerEntry, OwnerLedgerEntry, OwnerSettlement
from billing.models import (
    BankTransaction,
    Expense,
    ExpenseCategory,
    Receivable,
    StatoPagamento,
    Supplier,
    UtilityBill,
    UtilityChargePeriod,
)
from properties.models import (
    Contract,
    OwnerBankAccount,
    OwnerProfile,
    OwnershipShare,
    PropertyMembership,
    Room,
    RoomAssignment,
    TenantProfile,
)

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


def _crea_mondo(prop, suff, gruppo_proprietari, gruppo_inquilini):
    """Costruisce un "mondo" completo (owner, tenant, dati di dominio) su ``prop``."""
    m = SimpleNamespace(property=prop)

    # Owner: user + membership proprietario + profilo + quota + conto.
    m.user_owner = User.objects.create_user(
        f"xp_owner_{suff}", email=f"owner_{suff}@v.it", password="pwd123!"
    )
    m.user_owner.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=prop, user=m.user_owner,
        ruolo=PropertyMembership.Ruolo.PROPRIETARIO,
    )
    m.owner = OwnerProfile.objects.create(
        user=m.user_owner, nominativo=f"Owner {suff.upper()}"
    )
    m.quota = OwnershipShare.objects.create(
        property=prop, owner=m.owner, quota=Decimal("1.0000"),
        valid_from=datetime.date(2024, 1, 1),
    )
    m.conto = OwnerBankAccount.objects.create(
        owner=m.owner,
        banca=f"Banca {suff.upper()}",
        intestatario=f"Owner {suff.upper()}",
        iban="IT60X0542811101000000000001",
    )

    # Tenant: user + profilo + stanza + assignment + receivable affitto.
    m.user_tenant = User.objects.create_user(
        f"xp_inq_{suff}", email=f"inq_{suff}@v.it", password="pwd123!"
    )
    m.user_tenant.groups.add(gruppo_inquilini)
    m.tenant = TenantProfile.objects.create(
        user=m.user_tenant,
        property=prop,
        nominativo=f"Inquilino {suff.upper()}",
        giorno_pagamento_affitto=1,
    )
    m.room = Room.objects.create(
        property=prop, nome=f"Camera {suff.upper()}", ordinamento=1
    )
    m.assignment = RoomAssignment.objects.create(
        room=m.room,
        tenant=m.tenant,
        valid_from=datetime.date(2024, 9, 1),
        canone_mensile=Decimal("400"),
    )
    m.contract = Contract.objects.create(
        property=prop,
        data_stipula=datetime.date(2024, 9, 15),
        data_decorrenza=datetime.date(2024, 9, 20),
        durata_anni=4,
    )
    m.receivable = Receivable.objects.create(
        assignment=m.assignment,
        causale=Receivable.Causale.AFFITTO,
        competenza_da=datetime.date(2026, 5, 1),
        competenza_a=datetime.date(2026, 5, 31),
        importo_dovuto=Decimal("400"),
        scadenza=datetime.date(2026, 5, 1),
        stato=StatoPagamento.ATTESO,
    )

    # Spese, utenze, banca.
    m.categoria = ExpenseCategory.objects.create(
        property=prop, nome=f"Manutenzione {suff.upper()}"
    )
    m.expense = Expense.objects.create(
        property=prop,
        data=datetime.date(2026, 3, 1),
        category=m.categoria,
        importo=Decimal("100"),
        descrizione=f"Spesa {suff.upper()}",
        anticipata_da_owner=m.owner,
    )
    m.supplier = Supplier.objects.create(
        property=prop,
        nome=f"Fornitore {suff.upper()}",
        tipo=Supplier.TipoFornitore.ENERGIA,
    )
    m.periodo = UtilityChargePeriod.objects.create(
        property=prop,
        periodo_da=datetime.date(2026, 4, 1),
        periodo_a=datetime.date(2026, 4, 30),
        stato="inviato",
        tot_luce=Decimal("50.00"),
        tot_gas=Decimal("20.00"),
        tot_tari=Decimal("10.00"),
        giorni_totali=30,
    )
    m.bolletta = UtilityBill.objects.create(
        immobile=prop,
        supplier=m.supplier,
        prodotto=UtilityBill.Prodotto.LUCE,
        data_emissione=datetime.date(2026, 4, 15),
        periodo_da=datetime.date(2026, 4, 1),
        periodo_a=datetime.date(2026, 4, 30),
        importo_totale=Decimal("50.00"),
    )
    m.bank_tx = BankTransaction.objects.create(
        data=datetime.date(2026, 5, 2),
        descrizione=f"Bonifico {suff.upper()}",
        importo=Decimal("400"),
        owner_account=m.conto,
    )

    # Contabilità proprietari.
    m.ledger = OwnerLedgerEntry.objects.create(
        property=prop,
        owner=m.owner,
        data=datetime.date(2026, 5, 2),
        descrizione=f"Voce {suff.upper()}",
        importo=Decimal("100"),
        tipo=OwnerLedgerEntry.TipoVoce.AGGIUSTAMENTO,
    )
    m.settlement = OwnerSettlement.objects.create(
        property=prop,
        data=datetime.date(2026, 6, 30),
        periodo_da=datetime.date(2026, 1, 1),
        periodo_a=datetime.date(2026, 6, 30),
        descrizione=f"Chiusura {suff.upper()}",
        snapshot={},
    )
    m.inter = InterOwnerEntry.objects.create(
        property=prop,
        owner_da=m.owner,
        owner_a=m.owner,
        data=datetime.date(2026, 5, 2),
        importo=Decimal("50"),
        descrizione=f"Bilaterale {suff.upper()}",
    )
    return m


@pytest.fixture
def mondo_a(immobile, gruppo_proprietari, gruppo_inquilini):
    return _crea_mondo(immobile, "a", gruppo_proprietari, gruppo_inquilini)


@pytest.fixture
def mondo_b(immobile2, gruppo_proprietari, gruppo_inquilini):
    return _crea_mondo(immobile2, "b", gruppo_proprietari, gruppo_inquilini)


def _client(user):
    c = APIClient(enforce_csrf_checks=False)
    c.force_login(user)
    return c


@pytest.fixture
def client_owner_a(mondo_a):
    """Owner A, membro SOLO dell'immobile A."""
    return _client(mondo_a.user_owner)


@pytest.fixture
def client_tenant_a(mondo_a):
    return _client(mondo_a.user_tenant)


@pytest.fixture
def client_gestore_a(immobile, gruppo_proprietari, mondo_a):
    u = User.objects.create_user("xp_gestore_a", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.GESTORE
    )
    return _client(u)


@pytest.fixture
def client_sola_lettura_a(immobile, gruppo_proprietari, mondo_a):
    u = User.objects.create_user("xp_readonly_a", password="pwd123!")
    u.groups.add(gruppo_proprietari)
    PropertyMembership.objects.create(
        property=immobile, user=u, ruolo=PropertyMembership.Ruolo.SOLA_LETTURA
    )
    return _client(u)


def _ids(resp):
    """Set di id dai risultati (lista piatta o pagina {results: [...]})."""
    data = resp.json()
    if isinstance(data, dict):
        data = data["results"]
    return {obj["id"] for obj in data}


def _payload_expense(mondo, **extra):
    payload = {
        "data": "2026-06-01",
        "category": mondo.categoria.id,
        "importo": "120.00",
        "descrizione": "Spesa via API",
        "anticipata_da_owner": mondo.owner.id,
        "crea_bank_transaction": False,
    }
    payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# 1. Header X-Property-Id dell'immobile altrui → 403 su ogni endpoint gestione
# ---------------------------------------------------------------------------


ENDPOINT_GESTIONE = [
    "/api/v1/tenants/",
    "/api/v1/rooms/",
    "/api/v1/room-assignments/",
    "/api/v1/contracts/",
    "/api/v1/owners/",
    "/api/v1/bank-accounts/",
    "/api/v1/expenses/",
    "/api/v1/expense-categories/",
    "/api/v1/utility-periods/",
    "/api/v1/utility-bills/",
    "/api/v1/bank-transactions/",
    "/api/v1/receivables/",
    "/api/v1/rent-payments/",
    "/api/v1/owner-ledger/",
    "/api/v1/owner-settlements/",
    "/api/v1/inter-owner-entries/",
    "/api/v1/dashboard/proprietario/",
    "/api/v1/dashboard/conto-economico/",
    "/api/v1/quadro-annuale/2026/",
]


class TestHeaderPropertyAltrui:
    @pytest.mark.parametrize("url", ENDPOINT_GESTIONE)
    def test_403_su_property_altrui_200_sulla_propria(
        self, client_owner_a, mondo_a, mondo_b, url
    ):
        # Header verso una property di cui NON si è membri → 403.
        resp = client_owner_a.get(url, HTTP_X_PROPERTY_ID=str(mondo_b.property.id))
        assert resp.status_code == 403, (url, resp.status_code)

        # Controprova: con l'header della propria property l'endpoint risponde
        # (il 403 sopra dipende dall'immobile, non da altro).
        resp_ok = client_owner_a.get(url, HTTP_X_PROPERTY_ID=str(mondo_a.property.id))
        assert resp_ok.status_code == 200, (url, resp_ok.status_code, resp_ok.content)


# ---------------------------------------------------------------------------
# 2. Senza header (fallback sulla propria property): mai oggetti del mondo B
# ---------------------------------------------------------------------------


LISTE_SCOPATE = [
    ("/api/v1/tenants/", "tenant"),
    ("/api/v1/rooms/", "room"),
    ("/api/v1/room-assignments/", "assignment"),
    ("/api/v1/contracts/", "contract"),
    ("/api/v1/owners/", "owner"),
    ("/api/v1/bank-accounts/", "conto"),
    ("/api/v1/expenses/", "expense"),
    ("/api/v1/expense-categories/", "categoria"),
    ("/api/v1/utility-periods/", "periodo"),
    ("/api/v1/utility-bills/", "bolletta"),
    ("/api/v1/bank-transactions/", "bank_tx"),
    ("/api/v1/receivables/", "receivable"),
    ("/api/v1/rent-payments/", "receivable"),
    ("/api/v1/owner-ledger/", "ledger"),
    ("/api/v1/owner-settlements/", "settlement"),
    ("/api/v1/inter-owner-entries/", "inter"),
]


class TestListeSenzaHeader:
    @pytest.mark.parametrize("url,attr", LISTE_SCOPATE)
    def test_lista_contiene_a_ed_esclude_b(
        self, client_owner_a, mondo_a, mondo_b, url, attr
    ):
        resp = client_owner_a.get(url)
        assert resp.status_code == 200, (url, resp.status_code, resp.content)
        ids = _ids(resp)
        assert getattr(mondo_b, attr).id not in ids, url
        assert getattr(mondo_a, attr).id in ids, url


# ---------------------------------------------------------------------------
# 3. Dettaglio per id di oggetti del mondo B → 404 (fuori dal queryset)
# ---------------------------------------------------------------------------


DETTAGLI_CROSS = [
    ("/api/v1/tenants/{id}/", "tenant"),
    ("/api/v1/receivables/{id}/", "receivable"),
    ("/api/v1/rent-payments/{id}/", "receivable"),
    ("/api/v1/expenses/{id}/", "expense"),
    ("/api/v1/contracts/{id}/", "contract"),
    ("/api/v1/rooms/{id}/", "room"),
]


class TestDettaglioCross:
    @pytest.mark.parametrize("template,attr", DETTAGLI_CROSS)
    def test_dettaglio_oggetto_b_404(self, client_owner_a, mondo_b, template, attr):
        url = template.format(id=getattr(mondo_b, attr).id)
        resp = client_owner_a.get(url)
        assert resp.status_code == 404, (url, resp.status_code)


# ---------------------------------------------------------------------------
# 4. Scritture cross-property
# ---------------------------------------------------------------------------


class TestScrittureCross:
    def test_post_expense_crea_sempre_sulla_propria_property(
        self, client_owner_a, mondo_a, mondo_b
    ):
        """La property della Expense è assegnata dal server dall'immobile
        attivo: anche passando ``property`` del mondo B nel payload, la spesa
        finisce su A."""
        resp = client_owner_a.post(
            "/api/v1/expenses/",
            _payload_expense(mondo_a, property=mondo_b.property.id),
            format="json",
            HTTP_X_PROPERTY_ID=str(mondo_a.property.id),
        )
        assert resp.status_code == 201, resp.content
        creata = Expense.objects.get(pk=resp.json()["id"])
        assert creata.property_id == mondo_a.property.id
        assert creata.property_id != mondo_b.property.id

    def test_registra_pagamento_su_receivable_b(self, client_owner_a, mondo_a, mondo_b):
        url = f"/api/v1/receivables/{mondo_b.receivable.id}/registra-pagamento/"
        resp = client_owner_a.post(
            url,
            {"data": "2026-06-01", "importo": "400.00", "owner_account": mondo_a.conto.id},
            format="json",
        )
        assert resp.status_code in (403, 404), resp.status_code
        # Il receivable B resta intonso.
        mondo_b.receivable.refresh_from_db()
        assert mondo_b.receivable.stato == StatoPagamento.ATTESO
        assert mondo_b.receivable.allocations.count() == 0

    @pytest.mark.parametrize("azione", ["situazione", "rendiconto"])
    def test_azioni_su_tenant_b_negate(self, client_owner_a, mondo_b, azione):
        resp = client_owner_a.get(f"/api/v1/tenants/{mondo_b.tenant.id}/{azione}/")
        assert resp.status_code in (403, 404), (azione, resp.status_code)


# ---------------------------------------------------------------------------
# 4-bis. FALLE CHIUSE — regressione sulle falle trovate durante la stesura
# ---------------------------------------------------------------------------
# Documentavano falle cross-property reali, corrette in produzione il
# 2026-07-11 (conto BT vincolato ai membri dell'immobile, completezza
# periodo scopata). Restano come test di regressione.


class TestFalleNote:
    def test_post_expense_non_deve_creare_bt_su_conto_di_b(
        self, client_owner_a, mondo_a, mondo_b
    ):
        """REGRESSIONE (chiusa): ``ExpenseSerializer`` accettava qualunque
        ``bt_owner_account`` esistente e attivo, senza verificare che il conto
        appartenga a un membro dell'immobile attivo. Omettendo
        ``anticipata_da_owner`` (derivato dal conto), l'owner A crea una
        BankTransaction sul conto dell'owner B: il movimento compare nel
        perimetro (e nelle liste bank-transactions) del mondo B."""
        payload = _payload_expense(mondo_a, crea_bank_transaction=True,
                                   bt_owner_account=mondo_b.conto.id)
        payload.pop("anticipata_da_owner")
        resp = client_owner_a.post("/api/v1/expenses/", payload, format="json")
        # Il conto è fuori dall'immobile attivo: la scrittura va rifiutata...
        assert resp.status_code == 403, (
            f"atteso 403, ottenuto {resp.status_code}: una POST expenses di A "
            "ha scritto una BankTransaction sul conto dell'owner B"
        )
        # ...e nessuna BT deve finire sul conto del mondo B.
        assert BankTransaction.objects.filter(
            owner_account=mondo_b.conto, importo__lt=0
        ).count() == 0

    def test_registra_pagamento_non_deve_usare_conto_di_b(
        self, client_owner_a, mondo_a, mondo_b
    ):
        """REGRESSIONE (chiusa): ``RegistraPagamentoInputSerializer``
        valida solo esistenza e ``attivo`` del conto: l'owner A, registrando
        un pagamento su un PROPRIO receivable, può creare la BankTransaction
        sul conto dell'owner B (che se la ritrova nel suo estratto)."""
        url = f"/api/v1/receivables/{mondo_a.receivable.id}/registra-pagamento/"
        resp = client_owner_a.post(
            url,
            {"data": "2026-06-01", "importo": "400.00",
             "owner_account": mondo_b.conto.id},
            format="json",
        )
        assert resp.status_code == 403, (
            f"atteso 403, ottenuto {resp.status_code}: registra-pagamento di A "
            "ha creato una BankTransaction sul conto dell'owner B"
        )
        assert BankTransaction.objects.filter(
            owner_account=mondo_b.conto
        ).count() == 1  # solo la BT di fixture del mondo B

    def test_completezza_periodo_non_deve_vedere_bollette_di_b(
        self, client_owner_a, mondo_a, mondo_b
    ):
        """REGRESSIONE (chiusa): ``UtilityChargePeriodViewSet._completezza`` interrogava
        UtilityBill (e AnnualUtilityCost) senza filtro property: la
        "completezza" del periodo di A riflette le bollette di B. Oltre al
        leak informativo, ``emetti`` usa ``completo`` come gate di emissione."""
        # Bolletta luce di luglio SOLO nel mondo B.
        UtilityBill.objects.create(
            immobile=mondo_b.property,
            supplier=mondo_b.supplier,
            prodotto=UtilityBill.Prodotto.LUCE,
            data_emissione=datetime.date(2026, 7, 10),
            periodo_da=datetime.date(2026, 7, 1),
            periodo_a=datetime.date(2026, 7, 31),
            importo_totale=Decimal("60.00"),
        )
        resp = client_owner_a.get(
            "/api/v1/utility-periods/per-mese/?anno=2026&mese=7"
        )
        assert resp.status_code == 200
        completezza = resp.json()["completezza"]
        assert completezza["luce"] is False, (
            "la completezza del periodo di A segnala una bolletta luce "
            "che esiste solo nel mondo B"
        )


# ---------------------------------------------------------------------------
# 5. Ruoli membership: gestore operativo, sola_lettura read-only
# ---------------------------------------------------------------------------


class TestRuoliMembership:
    def test_gestore_legge_come_proprietario(self, client_gestore_a, mondo_a):
        resp = client_gestore_a.get("/api/v1/tenants/")
        assert resp.status_code == 200
        assert mondo_a.tenant.id in {t["id"] for t in resp.json()}

    def test_gestore_scrive_come_proprietario(self, client_gestore_a, mondo_a):
        resp = client_gestore_a.post(
            "/api/v1/expenses/", _payload_expense(mondo_a), format="json"
        )
        assert resp.status_code == 201, resp.content
        assert (
            Expense.objects.get(pk=resp.json()["id"]).property_id
            == mondo_a.property.id
        )

    def test_sola_lettura_legge(self, client_sola_lettura_a, mondo_a):
        resp = client_sola_lettura_a.get("/api/v1/expenses/")
        assert resp.status_code == 200
        assert mondo_a.expense.id in {e["id"] for e in resp.json()}

    def test_sola_lettura_non_scrive(self, client_sola_lettura_a, mondo_a):
        resp = client_sola_lettura_a.post(
            "/api/v1/expenses/", _payload_expense(mondo_a), format="json"
        )
        assert resp.status_code == 403, resp.status_code
        assert not Expense.objects.filter(descrizione="Spesa via API").exists()


# ---------------------------------------------------------------------------
# 6. L'inquilino del mondo A non vede nulla del mondo B
# ---------------------------------------------------------------------------


class TestInquilinoCross:
    def test_rent_payments_solo_propri(self, client_tenant_a, mondo_a, mondo_b):
        resp = client_tenant_a.get("/api/v1/rent-payments/")
        assert resp.status_code == 200
        ids = _ids(resp)
        assert ids == {mondo_a.receivable.id}
        assert mondo_b.receivable.id not in ids

    def test_dettaglio_receivable_b_404(self, client_tenant_a, mondo_b):
        resp = client_tenant_a.get(f"/api/v1/rent-payments/{mondo_b.receivable.id}/")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 7. Impersonation cross-property
# ---------------------------------------------------------------------------


class TestImpersonationCross:
    def test_owner_a_non_impersona_tenant_b(self, client_owner_a, mondo_b):
        resp = client_owner_a.post(f"/api/auth/impersonate/{mondo_b.tenant.id}/")
        assert resp.status_code == 403, resp.status_code

    def test_owner_a_impersona_il_proprio_tenant(self, mondo_a):
        # Controprova: il gate nega per property, non in assoluto.
        client = _client(mondo_a.user_owner)
        resp = client.post(f"/api/auth/impersonate/{mondo_a.tenant.id}/")
        assert resp.status_code == 200, resp.content
