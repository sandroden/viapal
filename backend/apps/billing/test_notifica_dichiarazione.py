"""L'avviso ai proprietari quando un inquilino dichiara di aver pagato.

Il punto delicato non è l'invio (best-effort, già coperto da ``invia_push``)
ma *chi* viene scelto: la policy per immobile ammette un restringimento a una
persona sola, e quella persona può non esistere.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from billing._notifiche import (
    destinatari_dichiarazione,
    notifica_dichiarazione_pagamento,
)
from billing.models import Receivable, StatoPagamento
from properties.models import (
    OwnerBankAccount,
    OwnerProfile,
    Property,
    PropertyMembership,
    Room,
    RoomAssignment,
    TenantProfile,
)


def _proprietario(immobile, username, ruolo=PropertyMembership.Ruolo.PROPRIETARIO):
    user = User.objects.create_user(username, email=f"{username}@v.it", password="pwd")
    PropertyMembership.objects.create(property=immobile, user=user, ruolo=ruolo)
    return user


@pytest.fixture
def anna(db, immobile):
    return _proprietario(immobile, "anna")


@pytest.fixture
def bruno(db, immobile):
    return _proprietario(immobile, "bruno")


@pytest.fixture
def gestore(db, immobile):
    return _proprietario(immobile, "gestore", PropertyMembership.Ruolo.GESTORE)


@pytest.fixture
def conto_bruno(db, immobile, bruno):
    """Il conto su cui l'immobile fa versare affitto e utenze."""
    owner = OwnerProfile.objects.create(user=bruno, nominativo="Bruno Test")
    conto = OwnerBankAccount.objects.create(
        owner=owner,
        banca="Banca Test",
        intestatario="Bruno Test",
        iban="IT00X0000000000000000000009",
    )
    conto.properties.add(immobile)
    immobile.bank_account_utenze = conto
    immobile.save(update_fields=["bank_account_utenze"])
    return conto


@pytest.fixture
def inquilino(db, immobile):
    user = User.objects.create_user("carla", email="carla@v.it", password="pwd")
    tenant = TenantProfile.objects.create(
        property=immobile, user=user, nominativo="Carla Inquilina",
        giorno_pagamento_affitto=5,
    )
    room = Room.objects.create(property=immobile, nome="Stanza 1", ordinamento=10)
    return RoomAssignment.objects.create(
        room=room,
        tenant=tenant,
        valid_from=datetime.date(2026, 1, 1),
        canone_mensile=Decimal("400"),
    )


@pytest.fixture
def addebito(db, inquilino):
    return Receivable.objects.create(
        assignment=inquilino,
        causale=Receivable.Causale.AFFITTO,
        competenza_da=datetime.date(2026, 9, 1),
        competenza_a=datetime.date(2026, 9, 30),
        importo_dovuto=Decimal("400"),
        scadenza=datetime.date(2026, 9, 5),
        stato=StatoPagamento.ATTESO,
    )


class TestDestinatari:
    def test_tutti_i_proprietari(self, addebito, anna, bruno):
        assert destinatari_dichiarazione(addebito) == [anna, bruno]

    def test_il_gestore_non_riceve(self, addebito, anna, bruno, gestore):
        """Il gestore fa il lavoro operativo, ma l'incasso non è suo: la
        scelta esplicita è avvisare chi partecipa economicamente.

        Servono *due* proprietari accanto al gestore: con uno solo il test
        passerebbe anche senza il filtro sul ruolo."""
        destinatari = destinatari_dichiarazione(addebito)
        assert destinatari == [anna, bruno]
        assert gestore not in destinatari

    def test_autore_escluso(self, addebito, anna, bruno):
        """Un proprietario può dichiarare al posto dell'inquilino: non si
        manda una notifica a chi ha appena premuto il bottone."""
        assert destinatari_dichiarazione(addebito, escludi=anna) == [bruno]

    def test_solo_destinatario_del_bonifico(self, immobile, addebito, anna, conto_bruno, bruno):
        immobile.notifica_dichiarazioni = Property.NotificaDichiarazioni.DESTINATARIO
        immobile.save(update_fields=["notifica_dichiarazioni"])
        destinatari = destinatari_dichiarazione(addebito)
        # La lista *sola* di bruno: se il ripiego scattasse ci sarebbe anche
        # anna, ed è l'unico segno che distingue i due rami.
        assert destinatari == [bruno]
        assert anna not in destinatari

    def test_destinatario_non_risolvibile_ripiega_su_tutti(
        self, immobile, addebito, anna, bruno
    ):
        """Nessun conto di destinazione impostato: la dichiarazione non deve
        sparire nel nulla solo perché l'anagrafica è incompleta."""
        immobile.notifica_dichiarazioni = Property.NotificaDichiarazioni.DESTINATARIO
        immobile.save(update_fields=["notifica_dichiarazioni"])
        assert destinatari_dichiarazione(addebito) == [anna, bruno]

    def test_proprietari_di_altri_immobili_esclusi(self, addebito, anna, immobile2):
        estraneo = _proprietario(immobile2, "estraneo")
        assert estraneo not in destinatari_dichiarazione(addebito)


class TestInvio:
    def test_invia_a_ogni_proprietario(self, addebito, anna, bruno, monkeypatch):
        chiamate = []

        def finta(user, **kw):
            chiamate.append((user, kw))
            return {"inviate": 1, "rimosse": 0, "errori": 0}

        monkeypatch.setattr("billing._notifiche.invia_push", finta)
        esito = notifica_dichiarazione_pagamento(addebito)

        assert esito == {"destinatari": 2, "inviate": 2}
        assert [c[0] for c in chiamate] == [anna, bruno]
        assert "Carla Inquilina" in chiamate[0][1]["titolo"]
        assert chiamate[0][1]["url"] == "/p/ritardi"

    def test_non_solleva_se_il_canale_esplode(self, addebito, anna, monkeypatch):
        def esplode(user, **kw):
            raise RuntimeError("push service irraggiungibile")

        monkeypatch.setattr("billing._notifiche.invia_push", esplode)
        assert notifica_dichiarazione_pagamento(addebito) == {
            "destinatari": 1, "inviate": 0,
        }


class TestApiDichiaraPagato:
    def test_la_dichiarazione_avvisa_i_proprietari(
        self, addebito, inquilino, anna, monkeypatch
    ):
        avvisati = []
        monkeypatch.setattr(
            "billing._notifiche.invia_push",
            lambda user, **kw: avvisati.append(user) or {"inviate": 1, "rimosse": 0, "errori": 0},
        )
        client = APIClient(enforce_csrf_checks=False)
        client.force_login(inquilino.tenant.user)

        resp = client.post(f"/api/v1/rent-payments/{addebito.id}/dichiara_pagato/")

        assert resp.status_code == 200
        assert avvisati == [anna]

    def test_la_dichiarazione_riesce_anche_senza_push(self, addebito, inquilino, anna):
        """Nessuno ha sottoscritto: lo stato cambia lo stesso."""
        client = APIClient(enforce_csrf_checks=False)
        client.force_login(inquilino.tenant.user)

        resp = client.post(f"/api/v1/rent-payments/{addebito.id}/dichiara_pagato/")

        addebito.refresh_from_db()
        assert resp.status_code == 200
        assert addebito.stato == StatoPagamento.DICHIARATO
