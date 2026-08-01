"""
Test dell'email di **riepilogo addebiti** (``billing.calc.riepilogo``) e del
comando ``invia_riepilogo_addebiti``.

Coprono la selezione (canone del mese, finestra dei pendenti, voci
dichiarate), quello che la mail **non** deve contenere (totali, QR, IBAN),
il dry-run come default del comando e la coerenza dei numeri con la home
dell'inquilino.
"""
import datetime
from decimal import Decimal
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command

pytestmark = pytest.mark.django_db

User = get_user_model()

OGGI = datetime.date.today()
MESE_CORRENTE = OGGI.replace(day=1)


def _inquilino(
    immobile,
    suffisso,
    email="",
    email_alt="",
    valid_to=None,
):
    """Inquilino con stanza e assegnazione (eventualmente già terminata)."""
    from properties.models import Room, RoomAssignment, TenantProfile

    room = Room.objects.create(
        property=immobile, nome=f"Camera {suffisso}", ordinamento=1
    )
    user = User.objects.create_user(
        username=f"tenant_riep_{suffisso}", password="x", email=email
    )
    grp, _ = Group.objects.get_or_create(name="inquilini")
    user.groups.add(grp)
    tenant = TenantProfile.objects.create(
        property=immobile,
        user=user,
        nominativo=f"Inquilino {suffisso}",
        email_alt=email_alt,
        giorno_pagamento_affitto=1,
    )
    assignment = RoomAssignment.objects.create(
        tenant=tenant,
        room=room,
        valid_from=OGGI - datetime.timedelta(days=400),
        valid_to=valid_to,
        canone_mensile=Decimal("400.00"),
    )
    return tenant, assignment


def _rec(assignment, causale, importo, scadenza, competenza=None, **extra):
    from billing.models import Receivable

    return Receivable.objects.create(
        assignment=assignment,
        causale=causale,
        competenza_da=competenza or MESE_CORRENTE,
        scadenza=scadenza,
        importo_dovuto=Decimal(importo),
        **extra,
    )


def _canone_del_mese(assignment, importo="400.00"):
    from billing.models import Receivable

    return _rec(
        assignment,
        Receivable.Causale.AFFITTO,
        importo,
        MESE_CORRENTE + datetime.timedelta(days=4),
        MESE_CORRENTE,
    )


class TestSelezioneDestinatari:
    def test_senza_addebiti_non_compare(self, mailoutbox, immobile):
        from billing.calc.riepilogo import invia_riepiloghi

        _inquilino(immobile, "vuoto", email="vuoto@example.com")
        esito = invia_riepiloghi(immobile, dry_run=False)
        assert esito["totale"] == 0
        assert esito["riepiloghi"] == []
        assert len(mailoutbox) == 0

    def test_solo_dichiarati_niente_da_sollecitare(self, mailoutbox, immobile):
        from billing.calc.riepilogo import invia_riepiloghi
        from billing.models import Receivable, StatoPagamento

        _, assignment = _inquilino(immobile, "dich", email="dich@example.com")
        _rec(
            assignment,
            Receivable.Causale.UTENZE,
            "60.00",
            OGGI - datetime.timedelta(days=3),
            stato=StatoPagamento.DICHIARATO,
        )
        esito = invia_riepiloghi(immobile, dry_run=False)
        assert esito["totale"] == 1
        assert esito["riepiloghi"][0]["esito"] == "niente_da_sollecitare"
        assert esito["inviati"] == 0
        assert len(mailoutbox) == 0

    def test_uscito_con_pendenti_riceve(self, mailoutbox, immobile):
        """Opposto della regola degli avvisi utenze: gli ex inquilini con
        arretrati sono proprio la popolazione da sollecitare."""
        from billing.calc.riepilogo import invia_riepiloghi
        from billing.models import Receivable

        _, assignment = _inquilino(
            immobile,
            "uscito",
            email="uscito@example.com",
            valid_to=OGGI - datetime.timedelta(days=30),
        )
        _rec(
            assignment,
            Receivable.Causale.UTENZE,
            "70.00",
            OGGI - datetime.timedelta(days=20),
        )
        esito = invia_riepiloghi(immobile, dry_run=False)
        r = esito["riepiloghi"][0]
        assert r["uscito"] is True
        assert r["notificare"] is True
        assert r["canone"] is None  # nessun canone del mese
        assert r["esito"] == "inviato"
        assert len(mailoutbox) == 1

    def test_esclusione_per_tenant_id(self, mailoutbox, immobile):
        from billing.calc.riepilogo import invia_riepiloghi

        tenant, assignment = _inquilino(immobile, "escl", email="escl@example.com")
        _canone_del_mese(assignment)
        esito = invia_riepiloghi(
            immobile, dry_run=False, escludi_ids=[tenant.id]
        )
        assert esito["riepiloghi"][0]["esito"] == "escluso"
        assert esito["esclusi"] == [tenant.nominativo]
        assert len(mailoutbox) == 0

    def test_isolamento_cross_property(self, mailoutbox, immobile, immobile2):
        from billing.calc.riepilogo import invia_riepiloghi

        _, a1 = _inquilino(immobile, "uno", email="uno@example.com")
        _canone_del_mese(a1)
        _, a2 = _inquilino(immobile2, "due", email="due@example.com")
        _canone_del_mese(a2)

        esito = invia_riepiloghi(immobile, dry_run=False)
        assert [r["tenant_nominativo"] for r in esito["riepiloghi"]] == [
            "Inquilino uno"
        ]
        assert [m.to for m in mailoutbox] == [["uno@example.com"]]


class TestContenuto:
    def test_canone_in_apertura_prima_dei_pendenti(self, immobile):
        from billing.calc.riepilogo import costruisci_riepiloghi
        from billing.models import Receivable

        _, assignment = _inquilino(immobile, "canone", email="c@example.com")
        canone = _canone_del_mese(assignment, "435.50")
        _rec(
            assignment,
            Receivable.Causale.UTENZE,
            "62.00",
            OGGI - datetime.timedelta(days=2),
        )
        r = costruisci_riepiloghi(immobile)[0]

        assert r["canone"]["id"] == canone.id
        assert r["canone"]["residuo"] == 435.5
        assert "435,50" in r["corpo"]
        # il canone del mese apre la mail, i pendenti vengono dopo
        assert r["corpo"].index("435,50") < r["corpo"].index("62,00")
        assert r["corpo"].index("435,50") < r["corpo"].index("Da saldare")

    def test_finestra_pendenti(self, immobile):
        from billing.calc.riepilogo import costruisci_riepiloghi
        from billing.models import Receivable

        _, assignment = _inquilino(immobile, "fin", email="f@example.com")
        _rec(
            assignment,
            Receivable.Causale.EXTRA,
            "10.00",
            OGGI - datetime.timedelta(days=5),
            descrizione="Scaduta",
        )
        _rec(
            assignment,
            Receivable.Causale.EXTRA,
            "20.00",
            OGGI + datetime.timedelta(days=10),
            descrizione="Vicina",
        )
        _rec(
            assignment,
            Receivable.Causale.EXTRA,
            "30.00",
            OGGI + datetime.timedelta(days=20),
            descrizione="Lontana",
        )

        r = costruisci_riepiloghi(immobile)[0]
        descrizioni = [x["descrizione"] for x in r["pendenti"]]
        assert descrizioni == ["Scaduta", "Vicina"]
        assert "Lontana" not in r["corpo"]

        r30 = costruisci_riepiloghi(immobile, giorni=30)[0]
        assert [x["descrizione"] for x in r30["pendenti"]] == [
            "Scaduta",
            "Vicina",
            "Lontana",
        ]

    def test_dichiarati_in_sezione_separata(self, immobile):
        from billing.calc.riepilogo import costruisci_riepiloghi
        from billing.models import Receivable, StatoPagamento

        _, assignment = _inquilino(immobile, "sep", email="s@example.com")
        _canone_del_mese(assignment)
        _rec(
            assignment,
            Receivable.Causale.EXTRA,
            "33.00",
            OGGI - datetime.timedelta(days=7),
            descrizione="Pendente vero",
        )
        _rec(
            assignment,
            Receivable.Causale.UTENZE,
            "77.00",
            OGGI - datetime.timedelta(days=4),
            stato=StatoPagamento.DICHIARATO,
        )
        r = costruisci_riepiloghi(immobile)[0]

        assert [x["residuo"] for x in r["in_attesa"]] == [77.0]
        assert 77.0 not in [x["residuo"] for x in r["pendenti"]]
        assert "In attesa di conferma" in r["corpo"]
        assert "In attesa di conferma" in r["corpo_html"]
        # la sezione dei dichiarati sta dopo quella dei pendenti
        assert r["corpo"].index("Da saldare") < r["corpo"].index(
            "In attesa di conferma"
        )

    def test_niente_totali_ne_qr_ne_iban(self, mailoutbox, immobile):
        """La mail è un promemoria: il conto completo e i QR sono in app."""
        from billing.calc.riepilogo import invia_riepiloghi
        from billing.models import Receivable
        from properties.models import OwnerBankAccount, OwnerProfile

        owner_user = User.objects.create_user("owner_riep", password="x")
        owner = OwnerProfile.objects.create(user=owner_user, nominativo="Owner")
        immobile.bank_account_utenze = OwnerBankAccount.objects.create(
            owner=owner,
            banca="Banca",
            intestatario="Owner",
            iban="IT60X0542811101000000123456",
        )
        immobile.save(update_fields=["bank_account_utenze"])

        _, assignment = _inquilino(immobile, "qr", email="qr@example.com")
        _canone_del_mese(assignment)
        _rec(
            assignment,
            Receivable.Causale.UTENZE,
            "50.00",
            OGGI - datetime.timedelta(days=1),
        )
        invia_riepiloghi(immobile, dry_run=False)

        msg = mailoutbox[0]
        html = next(
            (c for c, mime in (msg.alternatives or []) if mime == "text/html"), ""
        )
        assert msg.attachments == []
        assert "image/png" not in str(msg.message())
        assert "IT60X0542811101000000123456" not in msg.body
        assert "IT60X0542811101000000123456" not in html
        for parola in ("Da versare", "Totale", "totale"):
            assert parola not in msg.body, parola
        # niente somma delle due voci (400 + 50)
        assert "450" not in msg.body
        assert "app Viapal" in html

    def test_multipart_e_link_app(self, mailoutbox, immobile):
        from billing.calc.riepilogo import invia_riepiloghi

        _, assignment = _inquilino(immobile, "mp", email="mp@example.com")
        _canone_del_mese(assignment, "412.30")
        invia_riepiloghi(immobile, dry_run=False)

        msg = mailoutbox[0]
        html = next(
            (c for c, mime in (msg.alternatives or []) if mime == "text/html"), ""
        )
        assert html, "manca l'alternativa text/html"
        assert "<a href=" in html
        assert "/i/" in html
        # importi in formato italiano, sia nel testo sia nell'HTML
        assert "412,30" in msg.body
        assert "412,30" in html

    def test_email_alt_usata_e_registrata(self, mailoutbox, immobile):
        from billing.calc.riepilogo import invia_riepiloghi
        from notifications.models import Notification

        _, assignment = _inquilino(
            immobile, "alt", email="", email_alt="alt@example.com"
        )
        _canone_del_mese(assignment)
        invia_riepiloghi(immobile, dry_run=False)

        assert [m.to for m in mailoutbox] == [["alt@example.com"]]
        riga = Notification.objects.get(codice="riepilogo_addebiti")
        assert riga.destinatario == "alt@example.com"
        assert riga.inviata_at is not None

    def test_senza_email(self, mailoutbox, immobile):
        from billing.calc.riepilogo import invia_riepiloghi

        _, assignment = _inquilino(immobile, "noemail")
        _canone_del_mese(assignment)
        esito = invia_riepiloghi(immobile, dry_run=False)
        assert esito["senza_email"] == ["Inquilino noemail"]
        assert len(mailoutbox) == 0


class TestEffettiCollaterali:
    def test_scadenze_immutate(self, mailoutbox, immobile):
        """A differenza degli avvisi utenze, il riepilogo non riscrive le
        scadenze: lo farebbe azzerare i ritardi già maturati."""
        from billing.calc.riepilogo import invia_riepiloghi
        from billing.models import Receivable

        _, assignment = _inquilino(immobile, "scad", email="sc@example.com")
        _canone_del_mese(assignment)
        _rec(
            assignment,
            Receivable.Causale.UTENZE,
            "45.00",
            OGGI - datetime.timedelta(days=12),
        )
        prima = dict(
            Receivable.objects.filter(assignment=assignment).values_list(
                "id", "scadenza"
            )
        )
        invia_riepiloghi(immobile, dry_run=False)
        dopo = dict(
            Receivable.objects.filter(assignment=assignment).values_list(
                "id", "scadenza"
            )
        )
        assert dopo == prima
        assert len(mailoutbox) == 1

    def test_importi_coerenti_con_la_home(self, immobile):
        """Ogni riga della mail riporta lo stesso residuo che l'inquilino
        vede in ``/i/``: è tutta la ragione di ``posizione_inquilino``."""
        from rest_framework.test import APIClient

        from billing.calc.riepilogo import costruisci_riepiloghi
        from billing.models import (
            BankTransaction,
            BankTransactionAllocation,
            Receivable,
        )
        from properties.models import OwnerBankAccount, OwnerProfile

        owner_user = User.objects.create_user("owner_coe", password="x")
        owner = OwnerProfile.objects.create(user=owner_user, nominativo="Owner C")
        conto = OwnerBankAccount.objects.create(
            owner=owner,
            banca="Banca C",
            intestatario="Owner C",
            iban="IT60X0542811101000000123456",
        )
        tenant, assignment = _inquilino(immobile, "coe", email="coe@example.com")
        canone = _canone_del_mese(assignment)
        utenze = _rec(
            assignment,
            Receivable.Causale.UTENZE,
            "90.00",
            OGGI - datetime.timedelta(days=6),
        )
        # un parziale: il residuo non è più il dovuto
        bt = BankTransaction.objects.create(
            data=OGGI - datetime.timedelta(days=2),
            descrizione="acconto",
            importo=Decimal("30.00"),
            owner_account=conto,
        )
        BankTransactionAllocation.objects.create(
            bank_transaction=bt, receivable=utenze, importo=Decimal("30.00")
        )

        client = APIClient()
        client.force_authenticate(user=tenant.user)
        home = client.get("/api/v1/dashboard/inquilino/").json()
        residui_home = {x["id"]: x["residuo"] for x in home["da_pagare"]}

        r = costruisci_riepiloghi(immobile)[0]
        voci = [r["canone"], *r["pendenti"], *r["in_attesa"]]
        assert {x["id"] for x in voci} == {canone.id, utenze.id}
        for voce in voci:
            assert voce["residuo"] == residui_home[voce["id"]]
        assert "60,00" in r["corpo"]  # 90 − 30 imputati

    def test_ultimo_invio_solo_del_riepilogo(self, mailoutbox, immobile):
        """``ultimo_invio_at`` non deve pescare l'email di invito, che ha la
        stessa GenericFK sul profilo inquilino."""
        from billing.calc.riepilogo import costruisci_riepiloghi, invia_riepiloghi
        from notifications.models import Notification

        tenant, assignment = _inquilino(immobile, "ult", email="u@example.com")
        _canone_del_mese(assignment)
        Notification.objects.create(
            user=tenant.user,
            canale=Notification.CanaleComunicazione.EMAIL,
            codice="invito_inquilino",
            destinatario="u@example.com",
            oggetto="Invito",
            corpo="…",
            inviata_at=None,
            oggetto_riferimento=tenant,
        )
        assert costruisci_riepiloghi(immobile)[0]["ultimo_invio_at"] is None

        invia_riepiloghi(immobile, dry_run=False)
        assert costruisci_riepiloghi(immobile)[0]["ultimo_invio_at"] is not None


class TestComando:
    def test_dry_run_di_default_su_tutti_gli_immobili(
        self, mailoutbox, immobile, immobile2
    ):
        from notifications.models import Notification

        _, a1 = _inquilino(immobile, "cmd1", email="cmd1@example.com")
        _canone_del_mese(a1)
        _, a2 = _inquilino(immobile2, "cmd2", email="cmd2@example.com")
        _canone_del_mese(a2)
        _, a3 = _inquilino(immobile2, "cmd3", email="cmd3@example.com")
        _canone_del_mese(a3)

        out = StringIO()
        call_command("invia_riepilogo_addebiti", stdout=out)
        testo = out.getvalue()

        assert len(mailoutbox) == 0
        assert Notification.objects.count() == 0
        assert "DRY-RUN" in testo
        # entrambi gli immobili elencati, con i propri conteggi
        assert f"[{immobile.nome}]" in testo
        assert f"[{immobile2.nome}]" in testo
        assert "1 riepiloghi" in testo  # immobile
        assert "2 riepiloghi" in testo  # immobile2

    def test_invia_manda_le_email(self, mailoutbox, immobile, immobile2):
        from notifications.models import Notification

        _, a1 = _inquilino(immobile, "cmd4", email="cmd4@example.com")
        _canone_del_mese(a1)
        _, a2 = _inquilino(immobile2, "cmd5", email="cmd5@example.com")
        _canone_del_mese(a2)

        out = StringIO()
        call_command("invia_riepilogo_addebiti", "--invia", stdout=out)

        assert len(mailoutbox) == 2
        assert Notification.objects.filter(
            codice="riepilogo_addebiti", inviata_at__isnull=False
        ).count() == 2

    def test_property_esplicita_e_giorni(self, mailoutbox, immobile, immobile2):
        from billing.models import Receivable

        _, a1 = _inquilino(immobile, "cmd6", email="cmd6@example.com")
        _rec(
            a1,
            Receivable.Causale.EXTRA,
            "15.00",
            OGGI + datetime.timedelta(days=25),
            descrizione="Fra 25 giorni",
        )
        _, a2 = _inquilino(immobile2, "cmd7", email="cmd7@example.com")
        _canone_del_mese(a2)

        out = StringIO()
        call_command(
            "invia_riepilogo_addebiti",
            "--property",
            str(immobile.id),
            "--giorni",
            "30",
            "--invia",
            stdout=out,
        )
        assert [m.to for m in mailoutbox] == [["cmd6@example.com"]]
        assert "Fra 25 giorni" in mailoutbox[0].body

    def test_tenant_singolo(self, mailoutbox, immobile):
        tenant, a1 = _inquilino(immobile, "cmd8", email="cmd8@example.com")
        _canone_del_mese(a1)
        _, a2 = _inquilino(immobile, "cmd9", email="cmd9@example.com")
        _canone_del_mese(a2)

        call_command(
            "invia_riepilogo_addebiti",
            "--tenant",
            str(tenant.id),
            "--invia",
            stdout=StringIO(),
        )
        assert [m.to for m in mailoutbox] == [["cmd8@example.com"]]
