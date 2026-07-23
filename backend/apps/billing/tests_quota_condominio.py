"""
Test per ``_quota_condominio_per`` (billing/calc/rent.py) e per la sua
integrazione in ``genera_pagamenti_mese``.

Coprono il bug multiproprietà: la vecchia implementazione sommava TUTTE le
``TenantCondominioRate`` valide alla data, senza filtrare per immobile né
per inquilino. La nuova versione prende UNA sola riga per (property,
inquilino): la quota specifica del tenant se presente, altrimenti la
generica dell'immobile; mai la somma.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from billing.calc.rent import _quota_condominio_per, genera_pagamenti_mese
from billing.models import Receivable, TenantCondominioRate
from properties.models import Contract, Room, RoomAssignment, TenantProfile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def contract_1(db, immobile):
    return Contract.objects.create(
        property=immobile,
        data_stipula=datetime.date(2024, 1, 1),
        data_decorrenza=datetime.date(2024, 1, 1),
        durata_anni=4,
    )


@pytest.fixture
def contract_2(db, immobile2):
    """Contratto di un ALTRO immobile: usato per il test di regressione del
    bug della somma globale."""
    return Contract.objects.create(
        property=immobile2,
        data_stipula=datetime.date(2024, 1, 1),
        data_decorrenza=datetime.date(2024, 1, 1),
        durata_anni=4,
    )


@pytest.fixture
def room_1(db, immobile):
    return Room.objects.create(property=immobile, nome="Camera QC 1", ordinamento=1)


@pytest.fixture
def make_tenant(db, immobile):
    counter = [0]

    def _make(nominativo="Inquilino QC"):
        counter[0] += 1
        u = User.objects.create_user(
            username=f"tenant_qc_{counter[0]}",
            email=f"tenant_qc_{counter[0]}@v.it",
            password="pwd",
        )
        return TenantProfile.objects.create(
            property=immobile,
            user=u,
            nominativo=nominativo,
            giorno_pagamento_affitto=1,
        )

    return _make


@pytest.fixture
def tenant_a(make_tenant):
    return make_tenant("Tenant A")


@pytest.fixture
def tenant_b(make_tenant):
    return make_tenant("Tenant B")


@pytest.fixture
def assignment_a(db, room_1, tenant_a):
    return RoomAssignment.objects.create(
        room=room_1,
        tenant=tenant_a,
        valid_from=datetime.date(2026, 1, 1),
        canone_mensile=Decimal("400.00"),
    )


COMPETENZA = datetime.date(2026, 5, 1)


# ---------------------------------------------------------------------------
# _quota_condominio_per
# ---------------------------------------------------------------------------


class TestQuotaCondominioPer:
    def test_solo_generica(self, contract_1, assignment_a):
        TenantCondominioRate.objects.create(
            contract=contract_1,
            valid_from=datetime.date(2025, 1, 1),
            importo_mensile=Decimal("90.00"),
        )
        assert _quota_condominio_per(assignment_a, COMPETENZA) == Decimal("90.00")

    def test_generica_e_specifica_del_tenant(self, contract_1, assignment_a):
        TenantCondominioRate.objects.create(
            contract=contract_1,
            valid_from=datetime.date(2025, 1, 1),
            importo_mensile=Decimal("90.00"),
        )
        TenantCondominioRate.objects.create(
            contract=contract_1,
            tenant=assignment_a.tenant,
            valid_from=datetime.date(2025, 1, 1),
            importo_mensile=Decimal("70.00"),
        )
        # La specifica prevale: NON è la somma (160).
        assert _quota_condominio_per(assignment_a, COMPETENZA) == Decimal("70.00")

    def test_specifica_di_altro_tenant_ignorata(
        self, contract_1, assignment_a, tenant_b
    ):
        TenantCondominioRate.objects.create(
            contract=contract_1,
            valid_from=datetime.date(2025, 1, 1),
            importo_mensile=Decimal("90.00"),
        )
        TenantCondominioRate.objects.create(
            contract=contract_1,
            tenant=tenant_b,
            valid_from=datetime.date(2025, 1, 1),
            importo_mensile=Decimal("70.00"),
        )
        # L'eccezione di tenant_b non deve influenzare tenant_a.
        assert _quota_condominio_per(assignment_a, COMPETENZA) == Decimal("90.00")

    def test_quota_di_altra_property_non_conta(
        self, contract_2, assignment_a
    ):
        """Regressione del bug: quota di un'ALTRA property non deve sommarsi
        (né sostituirsi) alla quota (assente) degli assignment di questa."""
        TenantCondominioRate.objects.create(
            contract=contract_2,
            valid_from=datetime.date(2025, 1, 1),
            importo_mensile=Decimal("90.00"),
        )
        assert _quota_condominio_per(assignment_a, COMPETENZA) == Decimal("0")

    def test_nessuna_quota(self, assignment_a):
        assert _quota_condominio_per(assignment_a, COMPETENZA) == Decimal("0")

    def test_due_generiche_sovrapposte_vince_la_piu_recente(
        self, contract_1, assignment_a
    ):
        TenantCondominioRate.objects.create(
            contract=contract_1,
            valid_from=datetime.date(2024, 1, 1),
            importo_mensile=Decimal("70.00"),
        )
        TenantCondominioRate.objects.create(
            contract=contract_1,
            valid_from=datetime.date(2026, 1, 1),
            importo_mensile=Decimal("90.00"),
        )
        # Vince la più recente (90), non la somma (160).
        assert _quota_condominio_per(assignment_a, COMPETENZA) == Decimal("90.00")


# ---------------------------------------------------------------------------
# genera_pagamenti_mese: due tenant, uno con quota specifica
# ---------------------------------------------------------------------------


class TestGeneraPagamentiMeseQuotaSpecifica:
    def test_due_tenant_stessa_property_importi_diversi(
        self, contract_1, room_1, tenant_a, tenant_b
    ):
        from properties.models import Room

        room_b = Room.objects.create(
            property=tenant_b.property, nome="Camera QC 2", ordinamento=2
        )
        assignment_a = RoomAssignment.objects.create(
            room=room_1,
            tenant=tenant_a,
            valid_from=datetime.date(2026, 1, 1),
            canone_mensile=Decimal("400.00"),
        )
        assignment_b = RoomAssignment.objects.create(
            room=room_b,
            tenant=tenant_b,
            valid_from=datetime.date(2026, 1, 1),
            canone_mensile=Decimal("400.00"),
        )
        TenantCondominioRate.objects.create(
            contract=contract_1,
            valid_from=datetime.date(2025, 1, 1),
            importo_mensile=Decimal("90.00"),
        )
        TenantCondominioRate.objects.create(
            contract=contract_1,
            tenant=tenant_a,
            valid_from=datetime.date(2025, 1, 1),
            importo_mensile=Decimal("70.00"),
        )

        genera_pagamenti_mese(2026, 5, persist=True)

        rec_a = Receivable.objects.get(
            assignment=assignment_a, causale=Receivable.Causale.AFFITTO
        )
        rec_b = Receivable.objects.get(
            assignment=assignment_b, causale=Receivable.Causale.AFFITTO
        )
        # tenant_a: canone 400 + quota specifica 70 = 470
        assert rec_a.importo_dovuto == Decimal("470.00")
        # tenant_b: canone 400 + quota generica 90 = 490
        assert rec_b.importo_dovuto == Decimal("490.00")
