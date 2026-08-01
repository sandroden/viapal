"""
Test di **caratterizzazione** di ``GET /api/v1/dashboard/inquilino/``.

Scritto prima dell'estrazione di ``billing.calc.posizione.posizione_inquilino``
e verde sul codice pre-refactor: la home dell'inquilino è la fonte dei numeri
che finiranno anche nell'email di riepilogo, quindi il refactor deve essere a
regressione zero, **tipi compresi** (i totali restano ``float``: se un
``Decimal`` sfuggisse nel payload, DRF lo serializzerebbe come stringa).

Lo scenario copre tutte le forme che l'estrazione deve preservare:
affitto scaduto, utenze *dichiarate* (contate nel totale), un parziale,
una rata di deposito positiva, un extra **negativo** (credito) e un
bonifico con resto non imputato (che scala il netto da versare).
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()

IBAN_OK = "IT60X0542811101000000123456"


@pytest.fixture
def scenario(immobile):
    """Inquilino con cinque addebiti aperti e un bonifico con resto.

    Le date sono relative a *oggi* perché la view usa ``date.today()``:
    fissarle renderebbe il test dipendente dal calendario.
    """
    from billing.models import (
        BankTransaction,
        BankTransactionAllocation,
        Receivable,
        StatoPagamento,
    )
    from properties.models import (
        OwnerBankAccount,
        OwnerProfile,
        Room,
        RoomAssignment,
        TenantProfile,
    )

    oggi = datetime.date.today()

    owner_user = User.objects.create_user("owner_snap", password="x")
    owner = OwnerProfile.objects.create(user=owner_user, nominativo="Owner Snap")
    conto = OwnerBankAccount.objects.create(
        owner=owner, banca="Banca Snap", intestatario="Owner Snap", iban=IBAN_OK
    )
    immobile.bank_account_utenze = conto
    immobile.save(update_fields=["bank_account_utenze"])

    room = Room.objects.create(property=immobile, nome="Camera Snap", ordinamento=1)
    user = User.objects.create_user(
        "tenant_snap", password="x", email="snap@example.com"
    )
    grp, _ = Group.objects.get_or_create(name="inquilini")
    user.groups.add(grp)
    tenant = TenantProfile.objects.create(
        property=immobile,
        user=user,
        nominativo="Snap Rossi",
        giorno_pagamento_affitto=1,
    )
    assignment = RoomAssignment.objects.create(
        tenant=tenant,
        room=room,
        valid_from=oggi - datetime.timedelta(days=400),
        canone_mensile=Decimal("400.00"),
    )

    def _rec(causale, dovuto, scadenza, competenza, **extra):
        return Receivable.objects.create(
            assignment=assignment,
            causale=causale,
            competenza_da=competenza,
            scadenza=scadenza,
            importo_dovuto=Decimal(dovuto),
            **extra,
        )

    # 1. affitto del mese corrente, scaduto da 10 giorni
    affitto = _rec(
        Receivable.Causale.AFFITTO,
        "400.00",
        oggi - datetime.timedelta(days=10),
        oggi.replace(day=1),
    )
    # 2. affitto del mese scorso, coperto solo in parte da un bonifico
    parziale = _rec(
        Receivable.Causale.AFFITTO,
        "400.00",
        oggi - datetime.timedelta(days=40),
        (oggi.replace(day=1) - datetime.timedelta(days=1)).replace(day=1),
    )
    # 3. utenze dichiarate dall'inquilino: entrano nel totale, non nei "pagati"
    utenze = _rec(
        Receivable.Causale.UTENZE,
        "80.00",
        oggi - datetime.timedelta(days=5),
        oggi.replace(day=1),
        stato=StatoPagamento.DICHIARATO,
    )
    # 4. rata di versamento del deposito (positiva) in scadenza
    deposito = _rec(
        Receivable.Causale.DEPOSITO,
        "200.00",
        oggi + datetime.timedelta(days=20),
        oggi.replace(day=1),
    )
    # 5. extra negativo: un credito riconosciuto all'inquilino
    extra = _rec(
        Receivable.Causale.EXTRA,
        "-50.00",
        oggi + datetime.timedelta(days=30),
        oggi.replace(day=1),
        descrizione="Rimborso lampadine",
    )

    # Bonifico da 150 € imputato per 100 € sull'affitto arretrato: restano
    # 50 € versati e mai imputati (il "credito disponibile" della home).
    bt = BankTransaction.objects.create(
        data=oggi - datetime.timedelta(days=20),
        descrizione="Bonifico Snap Rossi",
        importo=Decimal("150.00"),
        owner_account=conto,
    )
    BankTransactionAllocation.objects.create(
        bank_transaction=bt, receivable=parziale, importo=Decimal("100.00")
    )

    client = APIClient()
    client.force_authenticate(user=user)
    return {
        "client": client,
        "tenant": tenant,
        "assignment": assignment,
        "oggi": oggi,
        "affitto": affitto,
        "parziale": parziale,
        "utenze": utenze,
        "deposito": deposito,
        "extra": extra,
    }


def _body(scenario):
    resp = scenario["client"].get("/api/v1/dashboard/inquilino/")
    assert resp.status_code == 200, resp.content
    return resp.json()


class TestSnapshotDashboardInquilino:
    def test_chiavi_top_level(self, scenario):
        body = _body(scenario)
        assert set(body) == {
            "tenant",
            "stanza_corrente",
            "da_pagare",
            "saldo_totale",
            "ultimi_pagamenti",
        }
        assert body["tenant"]["nominativo"] == "Snap Rossi"
        assert body["ultimi_pagamenti"] == []

    def test_stanza_corrente(self, scenario):
        body = _body(scenario)
        assert body["stanza_corrente"] == {
            "id": scenario["assignment"].room_id,
            "nome": "Camera Snap",
            "canone_mensile": 400.0,
            "valid_from": scenario["assignment"].valid_from.isoformat(),
            "tipo_gestione": scenario["assignment"].room.property.tipo_gestione,
        }

    def test_da_pagare_ordine_e_chiavi(self, scenario):
        body = _body(scenario)
        da_pagare = body["da_pagare"]
        # ordinati per scadenza crescente
        assert [x["id"] for x in da_pagare] == [
            scenario["parziale"].id,
            scenario["affitto"].id,
            scenario["utenze"].id,
            scenario["deposito"].id,
            scenario["extra"].id,
        ]
        assert set(da_pagare[0]) == {
            "tipo",
            "id",
            "descrizione",
            "competenza",
            "importo",
            "importo_dovuto",
            "importo_pagato",
            "residuo",
            "parziale",
            "scadenza",
            "stato",
            "giorni_ritardo",
            "semaforo",
            "pagamento",
            "allocazioni",
            "commenti",
        }

    def test_item_affitto_scaduto(self, scenario):
        body = _body(scenario)
        item = next(x for x in body["da_pagare"] if x["id"] == scenario["affitto"].id)
        assert item["tipo"] == "rent"
        assert item["importo"] == 400.0
        assert item["importo_dovuto"] == 400.0
        assert item["importo_pagato"] == 0.0
        assert item["residuo"] == 400.0
        assert item["parziale"] is False
        assert item["stato"] == "atteso"
        assert item["giorni_ritardo"] == 10
        assert item["semaforo"] == "argilla_scuro"
        assert item["allocazioni"] == []
        assert item["commenti"] == []
        assert item["pagamento"]["iban"] == IBAN_OK
        assert item["descrizione"].startswith("Affitto ")

    def test_item_parziale_con_allocazione(self, scenario):
        body = _body(scenario)
        item = next(x for x in body["da_pagare"] if x["id"] == scenario["parziale"].id)
        assert item["importo_pagato"] == 100.0
        assert item["residuo"] == 300.0
        assert item["parziale"] is True
        # il parziale resta 'atteso' (signal _riallinea_receivable)
        assert item["stato"] == "atteso"
        assert item["allocazioni"] == [
            {
                "data": (scenario["oggi"] - datetime.timedelta(days=20)).isoformat(),
                "quota": 100.0,
                "bonifico_totale": 150.0,
            }
        ]

    def test_item_dichiarato_resta_in_lista(self, scenario):
        body = _body(scenario)
        item = next(x for x in body["da_pagare"] if x["id"] == scenario["utenze"].id)
        assert item["stato"] == "dichiarato"
        assert item["tipo"] == "utility_charge"
        assert item["residuo"] == 80.0

    def test_item_deposito_e_extra_negativo(self, scenario):
        body = _body(scenario)
        dep = next(x for x in body["da_pagare"] if x["id"] == scenario["deposito"].id)
        assert dep["tipo"] == "deposit"
        assert dep["residuo"] == 200.0
        assert dep["giorni_ritardo"] == -20

        extra = next(x for x in body["da_pagare"] if x["id"] == scenario["extra"].id)
        assert extra["tipo"] == "extra"
        assert extra["descrizione"] == "Rimborso lampadine"
        assert extra["residuo"] == -50.0

    def test_saldo_totale(self, scenario):
        body = _body(scenario)
        # 400 (affitto) + 300 (parziale) + 80 (dichiarato) + 200 (deposito)
        # − 50 (credito extra) = 930; meno i 50 € di resto bonifico = 880.
        assert body["saldo_totale"] == {
            "importo": 880.0,
            "lordo": 930.0,
            "credito_disponibile": 50.0,
            "pagamento": {
                "beneficiario": "Owner Snap",
                "iban": IBAN_OK,
                "banca": "Banca Snap",
                "causale": "Saldo Viapal - Snap Rossi",
            },
        }

    def test_tipi_float_non_stringhe(self, scenario):
        """I totali escono ``float``: un Decimal diventerebbe stringa JSON."""
        body = _body(scenario)
        for chiave in ("importo", "lordo", "credito_disponibile"):
            assert isinstance(body["saldo_totale"][chiave], float), chiave
        for item in body["da_pagare"]:
            for chiave in ("importo", "importo_dovuto", "importo_pagato", "residuo"):
                assert isinstance(item[chiave], float), (item["id"], chiave)
            assert isinstance(item["giorni_ritardo"], int)
            assert isinstance(item["scadenza"], str)
