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
7. impersonation: l'owner A non può impersonare l'inquilino B;
8. conti bancari: un utente membro di *entrambi* (proprietario di A, gestore
   di B) non porta i propri conti né i propri movimenti dentro B — l'unico
   caso in cui i due mondi si toccano, e quello da cui nasce il collegamento
   esplicito conto↔immobile.
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
    m.conto.properties.add(prop)

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
    "/api/v1/gallery-areas/",
    "/api/v1/gallery-images/",
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


# ---------------------------------------------------------------------------
# 8. FALLE CHIUSE (review 2026-07-24) — regressione sui fix di questa review
# ---------------------------------------------------------------------------
# Ogni test riproduce una falla cross-property CONFERMATA prima del fix
# (sarebbe rosso senza la correzione corrispondente) e resta come test di
# regressione.


class TestReceivableCreateAssignmentCross:
    """REGRESSIONE (chiusa): _ReceivableMixin.create (rent/utility/extra)
    accettava un ``assignment`` (e un ``period`` per le utenze) di
    qualunque property: i campi sono FK a queryset globale, non vincolati
    dalla permission (property-scoped solo il queryset di lettura)."""

    def test_rent_payment_assignment_altra_property_rifiutato(
        self, client_owner_a, mondo_a, mondo_b
    ):
        resp = client_owner_a.post(
            "/api/v1/rent-payments/",
            {
                "assignment": mondo_b.assignment.id,
                "competenza_da": "2026-06-01",
                "competenza_a": "2026-06-30",
                "importo_dovuto": "400.00",
                "scadenza": "2026-06-01",
                "stato": "atteso",
            },
            format="json",
        )
        assert resp.status_code == 400, resp.content
        assert not Receivable.objects.filter(
            causale=Receivable.Causale.AFFITTO,
            assignment=mondo_b.assignment,
            competenza_da=datetime.date(2026, 6, 1),
        ).exists()

    def test_utility_charge_period_altra_property_rifiutato(
        self, client_owner_a, mondo_a, mondo_b
    ):
        resp = client_owner_a.post(
            "/api/v1/utility-charges/",
            {
                "assignment": mondo_a.assignment.id,
                "period": mondo_b.periodo.id,
                "importo_totale": "30.00",
                "scadenza": "2026-05-15",
                "stato": "atteso",
            },
            format="json",
        )
        assert resp.status_code == 400, resp.content

    def test_rent_payment_sulla_propria_property_ok(self, client_owner_a, mondo_a):
        # Controprova: la stessa create funziona nella property attiva.
        resp = client_owner_a.post(
            "/api/v1/rent-payments/",
            {
                "assignment": mondo_a.assignment.id,
                "competenza_da": "2026-06-01",
                "competenza_a": "2026-06-30",
                "importo_dovuto": "400.00",
                "scadenza": "2026-06-01",
                "stato": "atteso",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content


class TestExpenseCampiCross:
    """REGRESSIONE (chiusa): ExpenseSerializer/ExpenseViewSet.perform_create
    non validavano che anticipata_da_owner/riferimento_quota_owner fossero
    membri dell'immobile attivo, né che category/supplier appartenessero
    alla stessa property (FK a queryset globale)."""

    def test_anticipata_da_owner_non_membro_rifiutato(
        self, client_owner_a, mondo_a, mondo_b
    ):
        payload = _payload_expense(mondo_a, anticipata_da_owner=mondo_b.owner.id)
        resp = client_owner_a.post("/api/v1/expenses/", payload, format="json")
        assert resp.status_code == 400, resp.content

    def test_riferimento_quota_owner_non_membro_rifiutato(
        self, client_owner_a, mondo_a, mondo_b
    ):
        payload = _payload_expense(mondo_a, riferimento_quota_owner=mondo_b.owner.id)
        resp = client_owner_a.post("/api/v1/expenses/", payload, format="json")
        assert resp.status_code == 400, resp.content

    def test_category_altra_property_rifiutata(self, client_owner_a, mondo_a, mondo_b):
        payload = _payload_expense(mondo_a, category=mondo_b.categoria.id)
        resp = client_owner_a.post("/api/v1/expenses/", payload, format="json")
        assert resp.status_code == 400, resp.content

    def test_supplier_altra_property_rifiutato(self, client_owner_a, mondo_a, mondo_b):
        payload = _payload_expense(mondo_a, supplier=mondo_b.supplier.id)
        resp = client_owner_a.post("/api/v1/expenses/", payload, format="json")
        assert resp.status_code == 400, resp.content


class TestRestituzioneDepositoCross:
    """REGRESSIONE (chiusa): RestituzioneDepositoView caricava il tenant
    senza scoping sulla property attiva (GET e POST), con permission di
    gruppo (IsProprietario) invece che di membership."""

    def test_get_cross_404(self, client_owner_a, mondo_b):
        resp = client_owner_a.get(
            f"/api/v1/tenants/{mondo_b.tenant.id}/restituzione-deposito/"
        )
        assert resp.status_code == 404, resp.status_code

    def test_post_cross_404_e_nessuna_scrittura(self, client_owner_a, mondo_b):
        resp = client_owner_a.post(
            f"/api/v1/tenants/{mondo_b.tenant.id}/restituzione-deposito/",
            {"data_restituzione": "2026-07-01", "importo": "500.00"},
            format="json",
        )
        assert resp.status_code == 404, resp.status_code
        assert not Receivable.objects.filter(
            assignment__tenant=mondo_b.tenant,
            causale=Receivable.Causale.DEPOSITO,
            importo_dovuto__lt=0,
        ).exists()

    def test_controprova_sul_proprio_tenant(self, client_owner_a, mondo_a):
        resp = client_owner_a.get(
            f"/api/v1/tenants/{mondo_a.tenant.id}/restituzione-deposito/"
        )
        assert resp.status_code == 200, resp.content


class TestConguagliaPrevisionaleGetCross:
    """REGRESSIONE (chiusa): il GET di ConguagliaPrevisionaleView caricava
    il tenant senza scoping (il POST già lo faceva correttamente)."""

    def test_get_cross_404(self, client_owner_a, mondo_b):
        resp = client_owner_a.get(
            f"/api/v1/tenants/{mondo_b.tenant.id}/conguaglia-previsionale/"
            "?previsionale_id=1"
        )
        assert resp.status_code == 404, resp.status_code


class TestUtenzeInquilinoBolletteCross:
    """REGRESSIONE (chiusa): UtenzeInquilinoView._bollette interrogava
    UtilityBill senza filtro immobile: l'inquilino di A vedeva le bollette
    (fornitore incluso) sovrapposte allo stesso periodo nel mondo B."""

    def test_bollette_non_include_altro_immobile(
        self, client_tenant_a, mondo_a, mondo_b
    ):
        Receivable.objects.create(
            assignment=mondo_a.assignment,
            causale=Receivable.Causale.UTENZE,
            utility_period=mondo_a.periodo,
            competenza_da=datetime.date(2026, 4, 1),
            competenza_a=datetime.date(2026, 4, 30),
            importo_dovuto=Decimal("30"),
            scadenza=datetime.date(2026, 5, 15),
            stato=StatoPagamento.ATTESO,
        )
        resp = client_tenant_a.get(f"/api/v1/utenze-inquilino/{mondo_a.periodo.id}/")
        assert resp.status_code == 200, resp.content
        fornitori = {b["supplier_nome"] for b in resp.json().get("bollette", [])}
        assert mondo_b.supplier.nome not in fornitori
        assert mondo_a.supplier.nome in fornitori


class TestUtilityBillStatisticheCross:
    """REGRESSIONE (chiusa): UtilityBillViewSet.statistiche interrogava
    UtilityBill/RoomAssignment senza filtro property: i consumi di B si
    sommavano a quelli di A nello stesso mese."""

    def test_statistiche_non_include_altro_immobile(
        self, client_owner_a, mondo_a, mondo_b
    ):
        UtilityBill.objects.filter(pk=mondo_a.bolletta.pk).update(
            consumo=Decimal("100.000")
        )
        UtilityBill.objects.filter(pk=mondo_b.bolletta.pk).update(
            consumo=Decimal("999.000")
        )
        resp = client_owner_a.get("/api/v1/utility-bills/statistiche/")
        assert resp.status_code == 200, resp.content
        righe = [r for r in resp.json() if r["anno"] == 2026 and r["mese"] == 4]
        assert len(righe) == 1, righe
        assert righe[0]["luce_consumo"] == 100.0, (
            "il consumo luce di aprile 2026 include la bolletta del mondo B "
            f"(atteso 100.0, ottenuto {righe[0]['luce_consumo']})"
        )


class TestAvvisiUtenzeTemplateCross:
    """REGRESSIONE (chiusa): il rendering degli avvisi utenze pescava il
    MessageTemplate 'avviso_utenze' senza filtro property: con un template
    configurato solo su B, l'avviso di A lo usava comunque."""

    def test_template_altra_property_non_usato(self, client_owner_a, mondo_a, mondo_b):
        from notifications.models import MessageTemplate

        MessageTemplate.objects.create(
            property=mondo_b.property,
            codice="avviso_utenze",
            titolo="TEMPLATE SOLO B",
            corpo="corpo B {{nome}}",
            canale=MessageTemplate.CanaleComunicazione.EMAIL,
        )
        Receivable.objects.create(
            assignment=mondo_a.assignment,
            causale=Receivable.Causale.UTENZE,
            utility_period=mondo_a.periodo,
            competenza_da=datetime.date(2026, 4, 1),
            competenza_a=datetime.date(2026, 4, 30),
            importo_dovuto=Decimal("30"),
            scadenza=datetime.date(2026, 5, 15),
            stato=StatoPagamento.ATTESO,
        )
        resp = client_owner_a.post(
            f"/api/v1/utility-periods/{mondo_a.periodo.id}/invia-avvisi/",
            {"dry_run": True},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        avvisi = resp.json().get("avvisi", [])
        assert avvisi, "nessun avviso generato: setup del test da rivedere"
        assert all(a["oggetto"] != "TEMPLATE SOLO B" for a in avvisi)


class TestUtilityBillImmobileReadOnlyCross:
    """REGRESSIONE (chiusa): UtilityBillSerializer.immobile era scrivibile
    → un PATCH poteva spostare la bolletta su un altro immobile."""

    def test_patch_immobile_ignorato(self, client_owner_a, mondo_a, mondo_b):
        resp = client_owner_a.patch(
            f"/api/v1/utility-bills/{mondo_a.bolletta.id}/",
            {"immobile": mondo_b.property.id},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        mondo_a.bolletta.refresh_from_db()
        assert mondo_a.bolletta.immobile_id == mondo_a.property.id


class TestUtilityBillSupplierCross:
    """REGRESSIONE (chiusa): UtilityBillSerializer.validate cercava/creava
    il Supplier da supplier_nome senza scoping per property (lookup
    cross-property + create senza property → IntegrityError); inoltre
    esigeva sempre supplier/supplier_nome anche in PATCH parziale."""

    def test_supplier_nome_esistente_su_altra_property_non_riusato(
        self, client_owner_a, mondo_a, mondo_b
    ):
        resp = client_owner_a.patch(
            f"/api/v1/utility-bills/{mondo_a.bolletta.id}/",
            {"supplier_nome": mondo_b.supplier.nome},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        mondo_a.bolletta.refresh_from_db()
        assert mondo_a.bolletta.supplier_id != mondo_b.supplier.id
        assert mondo_a.bolletta.supplier.property_id == mondo_a.property.id

    def test_patch_parziale_senza_supplier_non_400(self, client_owner_a, mondo_a):
        resp = client_owner_a.patch(
            f"/api/v1/utility-bills/{mondo_a.bolletta.id}/",
            {"numero_fattura": "NUOVO-123"},
            format="json",
        )
        assert resp.status_code == 200, resp.content


class TestGeneraPagamentiMeseScopedProperty:
    """REGRESSIONE (chiusa): i chiamanti di genera_pagamenti_mese
    (action admin, view standalone, comando genera_storico) non passavano
    ``property``: la generazione bulk iterava sugli assignment di TUTTE le
    property, producendo Receivable affitto anche nel mondo B."""

    def test_genera_storico_scoped_a_property(self, mondo_a, mondo_b):
        from django.core.management import call_command

        call_command(
            "genera_storico", "--dal", "2026-06", "--al", "2026-06",
            "--property", str(mondo_a.property.id),
        )
        assert Receivable.objects.filter(
            causale=Receivable.Causale.AFFITTO,
            assignment=mondo_a.assignment,
            competenza_da__year=2026, competenza_da__month=6,
        ).exists()
        assert not Receivable.objects.filter(
            causale=Receivable.Causale.AFFITTO,
            assignment=mondo_b.assignment,
            competenza_da__year=2026, competenza_da__month=6,
        ).exists()

    def test_genera_storico_senza_property_fallisce(self, db):
        from django.core.management import call_command

        with pytest.raises(Exception):
            call_command("genera_storico", "--dal", "2026-06", "--al", "2026-06")

    def test_admin_action_scoped_per_period_property(self, mondo_a, mondo_b):
        """L'action ``rigenera_receivables_affitto`` su un periodo di B non
        deve generare anche il Receivable affitto dell'assignment di A
        (attivo nello stesso mese)."""
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory

        from billing.admin import rigenera_receivables_affitto
        from billing.models import UtilityChargePeriod

        periodo_b_giugno = UtilityChargePeriod.objects.create(
            property=mondo_b.property,
            periodo_da=datetime.date(2026, 6, 1),
            periodo_a=datetime.date(2026, 6, 30),
        )

        factory = RequestFactory()
        request = factory.post("/admin/billing/utilitychargeperiod/")
        request.user = mondo_b.user_owner
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)

        class _StubForm:
            cleaned_data = {"force": False, "dry_run": False, "tenant": None}

            def is_valid(self):
                return True

        class _StubModelAdmin:
            def get_action_form_instance(self, request):
                return _StubForm()

        queryset = UtilityChargePeriod.objects.filter(pk=periodo_b_giugno.pk)
        rigenera_receivables_affitto(_StubModelAdmin(), request, queryset)

        assert Receivable.objects.filter(
            causale=Receivable.Causale.AFFITTO,
            assignment=mondo_b.assignment,
            competenza_da__year=2026, competenza_da__month=6,
        ).exists()
        assert not Receivable.objects.filter(
            causale=Receivable.Causale.AFFITTO,
            assignment=mondo_a.assignment,
            competenza_da__year=2026, competenza_da__month=6,
        ).exists()

    def test_admin_standalone_view_scoped_per_property_selezionata(
        self, mondo_a, mondo_b
    ):
        from django.contrib.auth.models import User
        from django.test import Client
        from django.urls import reverse

        staff = User.objects.create_superuser(
            "xp_staff_genera", "staff_genera@v.it", "pwd123!"
        )
        client = Client()
        client.force_login(staff)

        resp = client.post(
            reverse("admin:billing_receivable_genera_affitto"),
            {
                "anno": 2026, "mese": 6,
                "property": mondo_a.property.id,
                "force": "", "dry_run": "",
            },
        )
        assert resp.status_code in (200, 302), resp.content
        assert Receivable.objects.filter(
            causale=Receivable.Causale.AFFITTO,
            assignment=mondo_a.assignment,
            competenza_da__year=2026, competenza_da__month=6,
        ).exists()
        assert not Receivable.objects.filter(
            causale=Receivable.Causale.AFFITTO,
            assignment=mondo_b.assignment,
            competenza_da__year=2026, competenza_da__month=6,
        ).exists()

    def test_admin_standalone_view_property_obbligatoria(self, mondo_a):
        from django.contrib.auth.models import User
        from django.test import Client
        from django.urls import reverse

        staff = User.objects.create_superuser(
            "xp_staff_genera2", "staff_genera2@v.it", "pwd123!"
        )
        client = Client()
        client.force_login(staff)

        resp = client.post(
            reverse("admin:billing_receivable_genera_affitto"),
            {"anno": 2026, "mese": 6, "force": "", "dry_run": ""},
        )
        assert resp.status_code == 200
        assert resp.context["form"].errors.get("property")


class TestCessioneGuardie:
    """REGRESSIONE (chiusa): CessioneAssignmentSerializer non vincolava
    canone_mensile/costo_cessione a valori non negativi (a differenza di
    PrimaAssegnazioneSerializer) e l'action ``cessione`` non verificava che
    l'assignment corrente fosse ancora aperto."""

    def test_canone_negativo_rifiutato(self, client_owner_a, mondo_a):
        resp = client_owner_a.post(
            f"/api/v1/room-assignments/{mondo_a.assignment.id}/cessione/",
            {
                "data_fine": "2026-06-30",
                "nuovo_tenant": mondo_a.tenant.id,
                "canone_mensile": "-100.00",
            },
            format="json",
        )
        assert resp.status_code == 400, resp.content

    def test_cessione_assignment_gia_chiuso_rifiutata(self, client_owner_a, mondo_a):
        mondo_a.assignment.valid_to = datetime.date(2026, 6, 30)
        mondo_a.assignment.save(update_fields=["valid_to"])

        resp = client_owner_a.post(
            f"/api/v1/room-assignments/{mondo_a.assignment.id}/cessione/",
            {
                "data_fine": "2026-07-31",
                "nuovo_tenant": mondo_a.tenant.id,
                "canone_mensile": "400.00",
            },
            format="json",
        )
        assert resp.status_code == 400, resp.content


# ---------------------------------------------------------------------------
# 8. Conti bancari: visibilità per immobile, non per membership
# ---------------------------------------------------------------------------


@pytest.fixture
def doppio_ruolo(mondo_a, mondo_b, immobile2):
    """L'utente reale del caso: proprietario di A, *gestore* di B.

    Gestire l'immobile di qualcun altro non è un buon motivo perché i bonifici
    di quell'immobile arrivino sul proprio conto, né perché i propri movimenti
    bancari compaiano nella sua riconciliazione.
    """
    PropertyMembership.objects.create(
        property=immobile2,
        user=mondo_a.user_owner,
        ruolo=PropertyMembership.Ruolo.GESTORE,
    )
    return mondo_a


@pytest.fixture
def client_doppio_ruolo(doppio_ruolo):
    return _client(doppio_ruolo.user_owner)


def _su_b(client, immobile2):
    client.credentials(HTTP_X_PROPERTY_ID=str(immobile2.id))
    return client


class TestContiVisibilitaPerImmobile:
    """Il conto di un gestore non appartiene all'immobile che gestisce."""

    def test_conto_proprio_non_compare_sull_immobile_gestito(
        self, client_doppio_ruolo, doppio_ruolo, mondo_b, immobile2
    ):
        resp = _su_b(client_doppio_ruolo, immobile2).get("/api/v1/bank-accounts/")
        assert resp.status_code == 200, resp.content
        ids = _ids(resp)
        assert doppio_ruolo.conto.id not in ids
        assert ids == {mondo_b.conto.id}

    def test_movimenti_propri_non_compaiono_sull_immobile_gestito(
        self, client_doppio_ruolo, doppio_ruolo, mondo_b, immobile2
    ):
        """La regressione principale: sull'immobile di produzione erano 183
        movimenti di un altro immobile a comparire nella riconciliazione."""
        resp = _su_b(client_doppio_ruolo, immobile2).get("/api/v1/bank-transactions/")
        assert resp.status_code == 200, resp.content
        ids = _ids(resp)
        assert doppio_ruolo.bank_tx.id not in ids
        assert ids == {mondo_b.bank_tx.id}

    def test_conto_proprio_resta_visibile_sul_proprio_immobile(
        self, client_doppio_ruolo, doppio_ruolo, immobile
    ):
        """Controprova: dove il conto è in uso non cambia nulla."""
        client_doppio_ruolo.credentials(HTTP_X_PROPERTY_ID=str(immobile.id))
        assert doppio_ruolo.conto.id in _ids(
            client_doppio_ruolo.get("/api/v1/bank-accounts/")
        )
        assert doppio_ruolo.bank_tx.id in _ids(
            client_doppio_ruolo.get("/api/v1/bank-transactions/")
        )

    def test_conto_proprio_non_eleggibile_a_conto_utenze_dell_immobile_gestito(
        self, client_doppio_ruolo, doppio_ruolo, immobile2
    ):
        resp = _su_b(client_doppio_ruolo, immobile2).patch(
            f"/api/v1/properties/{immobile2.id}/",
            {"bank_account_utenze": doppio_ruolo.conto.id},
            format="json",
        )
        assert resp.status_code == 400, resp.content
        immobile2.refresh_from_db()
        assert immobile2.bank_account_utenze_id is None

    def test_conto_proprio_non_eleggibile_a_conto_affitto_dell_immobile_gestito(
        self, client_doppio_ruolo, doppio_ruolo, mondo_b, immobile2
    ):
        resp = _su_b(client_doppio_ruolo, immobile2).patch(
            f"/api/v1/room-assignments/{mondo_b.assignment.id}/",
            {"bank_account_affitto": doppio_ruolo.conto.id},
            format="json",
        )
        assert resp.status_code == 400, resp.content
        mondo_b.assignment.refresh_from_db()
        assert mondo_b.assignment.bank_account_affitto_id is None

    def test_registra_pagamento_su_immobile_gestito_col_conto_proprio(
        self, client_doppio_ruolo, doppio_ruolo, mondo_b, immobile2
    ):
        resp = _su_b(client_doppio_ruolo, immobile2).post(
            f"/api/v1/receivables/{mondo_b.receivable.id}/registra-pagamento/",
            {
                "data": "2026-05-10",
                "importo": "400.00",
                "owner_account": doppio_ruolo.conto.id,
            },
            format="json",
        )
        assert resp.status_code == 403, resp.content

    def test_spesa_anticipata_dal_gestore_col_proprio_conto_passa(
        self, client_doppio_ruolo, doppio_ruolo, mondo_b, immobile2
    ):
        """Eccezione voluta: per una spesa il conto è quello di chi ha
        anticipato il denaro, non quello su cui l'immobile incassa."""
        n_bt = BankTransaction.objects.filter(owner_account=doppio_ruolo.conto).count()
        resp = _su_b(client_doppio_ruolo, immobile2).post(
            "/api/v1/expenses/",
            {
                "data": "2026-06-01",
                "category": mondo_b.categoria.id,
                "importo": "120.00",
                "descrizione": "Anticipata dal gestore",
                "crea_bank_transaction": True,
                "bt_owner_account": doppio_ruolo.conto.id,
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        assert (
            BankTransaction.objects.filter(owner_account=doppio_ruolo.conto).count()
            == n_bt + 1
        )

    def test_spesa_con_conto_di_un_estraneo_rifiutata(
        self, client_doppio_ruolo, mondo_b, immobile2
    ):
        """L'eccezione vale per il *proprio* conto, non per uno qualsiasi."""
        estraneo = OwnerBankAccount.objects.create(
            owner=mondo_b.owner,
            banca="Banca estranea",
            intestatario="Estraneo",
            iban="IT60X0542811101000000000009",
        )
        resp = _su_b(client_doppio_ruolo, immobile2).post(
            "/api/v1/expenses/",
            {
                "data": "2026-06-01",
                "category": mondo_b.categoria.id,
                "importo": "120.00",
                "descrizione": "Conto altrui non in uso qui",
                "crea_bank_transaction": True,
                "bt_owner_account": estraneo.id,
            },
            format="json",
        )
        assert resp.status_code == 403, resp.content


class TestCollegaScollegaConto:
    """Le azioni che sostituiscono l'eliminazione impossibile."""

    def test_collegabili_elenca_i_conti_dei_membri_non_in_uso(
        self, client_doppio_ruolo, doppio_ruolo, mondo_b, immobile2
    ):
        resp = _su_b(client_doppio_ruolo, immobile2).get(
            "/api/v1/bank-accounts/collegabili/"
        )
        assert resp.status_code == 200, resp.content
        righe = resp.json()
        assert [r["id"] for r in righe] == [doppio_ruolo.conto.id]
        # L'IBAN non esce in chiaro: è l'unico punto con conti estranei.
        assert "iban" not in righe[0]
        assert righe[0]["iban_finale"] == doppio_ruolo.conto.iban[-4:]

    def test_collegabili_esclude_i_conti_non_attivi(
        self, client_doppio_ruolo, doppio_ruolo, immobile2
    ):
        doppio_ruolo.conto.attivo = False
        doppio_ruolo.conto.save(update_fields=["attivo"])
        resp = _su_b(client_doppio_ruolo, immobile2).get(
            "/api/v1/bank-accounts/collegabili/"
        )
        assert resp.json() == []

    def test_collega_e_scollega(
        self, client_doppio_ruolo, doppio_ruolo, immobile2
    ):
        client = _su_b(client_doppio_ruolo, immobile2)

        resp = client.post(f"/api/v1/bank-accounts/{doppio_ruolo.conto.id}/collega/")
        assert resp.status_code == 200, resp.content
        assert doppio_ruolo.conto.id in _ids(client.get("/api/v1/bank-accounts/"))

        resp = client.post(f"/api/v1/bank-accounts/{doppio_ruolo.conto.id}/scollega/")
        assert resp.status_code == 204, resp.content
        assert doppio_ruolo.conto.id not in _ids(client.get("/api/v1/bank-accounts/"))
        # Il conto non è stato toccato: solo il legame con l'immobile.
        assert OwnerBankAccount.objects.filter(pk=doppio_ruolo.conto.id).exists()

    def test_scollega_rifiutato_se_e_il_conto_utenze(
        self, client_doppio_ruolo, mondo_b, immobile2
    ):
        immobile2.bank_account_utenze = mondo_b.conto
        immobile2.save(update_fields=["bank_account_utenze"])

        resp = _su_b(client_doppio_ruolo, immobile2).post(
            f"/api/v1/bank-accounts/{mondo_b.conto.id}/scollega/"
        )
        assert resp.status_code == 400, resp.content
        assert mondo_b.conto.properties.filter(pk=immobile2.pk).exists()

    def test_scollega_rifiutato_se_e_il_conto_affitto_di_un_assegnazione(
        self, client_doppio_ruolo, mondo_b, immobile2
    ):
        mondo_b.assignment.bank_account_affitto = mondo_b.conto
        mondo_b.assignment.save(update_fields=["bank_account_affitto"])

        resp = _su_b(client_doppio_ruolo, immobile2).post(
            f"/api/v1/bank-accounts/{mondo_b.conto.id}/scollega/"
        )
        assert resp.status_code == 400, resp.content
        assert mondo_b.conto.properties.filter(pk=immobile2.pk).exists()

    def test_sola_lettura_non_collega(
        self, client_sola_lettura_a, mondo_a, mondo_b, immobile
    ):
        """`sola_lettura` (il commercialista) non scrive: lo blocca già
        IsPropertyMember sui metodi non-safe."""
        resp = client_sola_lettura_a.post(
            f"/api/v1/bank-accounts/{mondo_b.conto.id}/collega/",
            HTTP_X_PROPERTY_ID=str(immobile.id),
        )
        assert resp.status_code == 403, resp.content

    def test_sola_lettura_non_elenca_i_collegabili(
        self, client_sola_lettura_a, mondo_a, immobile
    ):
        """`collegabili/` è una GET, quindi IsPropertyMember da solo la
        lascerebbe passare: enumererebbe proprio i conti che il pannello
        nasconde apposta."""
        resp = client_sola_lettura_a.get(
            "/api/v1/bank-accounts/collegabili/",
            HTTP_X_PROPERTY_ID=str(immobile.id),
        )
        assert resp.status_code == 403, resp.content

    def test_collega_conto_di_immobile_estraneo_404(
        self, client_owner_a, mondo_b, immobile
    ):
        """Si possono collegare solo i conti dei membri dell'immobile."""
        resp = client_owner_a.post(
            f"/api/v1/bank-accounts/{mondo_b.conto.id}/collega/",
            HTTP_X_PROPERTY_ID=str(immobile.id),
        )
        assert resp.status_code == 404, resp.content
        assert not mondo_b.conto.properties.filter(pk=immobile.pk).exists()

    def test_conto_nuovo_nasce_in_uso_sull_immobile(self, client_owner_a, immobile):
        resp = client_owner_a.post(
            "/api/v1/bank-accounts/",
            {
                "banca": "Banca nuova",
                "intestatario": "Owner A",
                "iban": "IT60X0542811101000000000007",
                "attivo": True,
            },
            format="json",
            HTTP_X_PROPERTY_ID=str(immobile.id),
        )
        assert resp.status_code == 201, resp.content
        conto = OwnerBankAccount.objects.get(pk=resp.json()["id"])
        assert list(conto.properties.values_list("pk", flat=True)) == [immobile.pk]
