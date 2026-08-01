"""
Test del **registro delle comunicazioni** (``Notification``).

Il registro deve rispondere a "cosa è stato inviato, a chi e con che testo"
— e anche a "cosa NON è partito": un invio fallito lascia una riga con
``errore`` valorizzato e ``inviata_at`` nullo, e non interrompe l'invio agli
altri destinatari.
"""
import datetime
from decimal import Decimal
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives

pytestmark = pytest.mark.django_db

User = get_user_model()


def _inquilino(immobile, suffisso, email):
    from properties.models import Room, RoomAssignment, TenantProfile

    room = Room.objects.create(
        property=immobile, nome=f"Camera {suffisso}", ordinamento=1
    )
    user = User.objects.create_user(
        username=f"tenant_reg_{suffisso}", password="x", email=email
    )
    tenant = TenantProfile.objects.create(
        property=immobile,
        user=user,
        nominativo=f"Inquilino {suffisso}",
        giorno_pagamento_affitto=1,
    )
    return RoomAssignment.objects.create(
        tenant=tenant,
        room=room,
        valid_from=datetime.date(2024, 1, 1),
        canone_mensile=Decimal("400.00"),
    )


@pytest.fixture
def periodo_con_addebiti(immobile):
    """Un periodo utenze con due addebiti già emessi (due inquilini)."""
    from billing.models import Receivable, UtilityChargePeriod

    period = UtilityChargePeriod.objects.create(
        property=immobile,
        periodo_da=datetime.date(2025, 6, 1),
        periodo_a=datetime.date(2025, 6, 30),
    )
    for suffisso, email in (("A", "a@example.com"), ("B", "b@example.com")):
        assignment = _inquilino(immobile, suffisso, email)
        Receivable.objects.create(
            assignment=assignment,
            causale=Receivable.Causale.UTENZE,
            utility_period=period,
            competenza_da=period.periodo_da,
            competenza_a=period.periodo_a,
            scadenza=datetime.date(2025, 7, 15),
            importo_dovuto=Decimal("55.00"),
        )
    return period


class TestRegistroInvioRiuscito:
    def test_riga_completa(self, mailoutbox, periodo_con_addebiti):
        from billing.calc.avvisi import invia_avvisi_utenze
        from notifications.models import Notification

        esito = invia_avvisi_utenze(periodo_con_addebiti, dry_run=False)
        assert esito["inviati"] == 2
        assert len(mailoutbox) == 2

        righe = Notification.objects.filter(codice="avviso_utenze")
        assert righe.count() == 2
        riga = righe.get(destinatario="a@example.com")
        assert riga.inviata_at is not None
        assert riga.errore == ""
        assert riga.canale == Notification.CanaleComunicazione.EMAIL
        # l'HTML realmente recapitato è archiviato, non più buttato via
        assert "<a href=" in riga.corpo_html
        assert riga.oggetto in [m.subject for m in mailoutbox]

    def test_dry_run_non_scrive(self, mailoutbox, periodo_con_addebiti):
        from billing.calc.avvisi import invia_avvisi_utenze
        from notifications.models import Notification

        invia_avvisi_utenze(periodo_con_addebiti, dry_run=True)
        assert Notification.objects.count() == 0
        assert len(mailoutbox) == 0


class TestRegistroInvioFallito:
    def test_fallimento_registrato_e_invio_prosegue(
        self, mailoutbox, periodo_con_addebiti
    ):
        """Il primo destinatario fallisce, il secondo riceve: due righe con
        esito diverso, e il batch non si ferma al primo errore."""
        from billing.calc.avvisi import invia_avvisi_utenze
        from notifications.models import Notification

        vero_send = EmailMultiAlternatives.send
        chiamate = {"n": 0}

        def send_ballerino(self, *args, **kwargs):
            chiamate["n"] += 1
            if chiamate["n"] == 1:
                raise RuntimeError("SMTP non raggiungibile")
            return vero_send(self, *args, **kwargs)

        with mock.patch.object(EmailMultiAlternatives, "send", send_ballerino):
            esito = invia_avvisi_utenze(periodo_con_addebiti, dry_run=False)

        assert esito["inviati"] == 1
        assert esito["errori"] == 1
        assert len(mailoutbox) == 1

        fallita = Notification.objects.get(destinatario="a@example.com")
        assert fallita.inviata_at is None
        assert "SMTP non raggiungibile" in fallita.errore
        assert fallita.codice == "avviso_utenze"
        assert fallita.corpo_html  # il testo tentato resta consultabile

        riuscita = Notification.objects.get(destinatario="b@example.com")
        assert riuscita.inviata_at is not None
        assert riuscita.errore == ""

    def test_scadenza_non_toccata_su_fallimento(self, periodo_con_addebiti):
        """La scadenza si sposta solo per gli avvisi effettivamente partiti."""
        from billing.calc.avvisi import invia_avvisi_utenze
        from billing.models import Receivable

        scadenze_prima = dict(
            Receivable.objects.filter(
                utility_period=periodo_con_addebiti
            ).values_list("id", "scadenza")
        )
        with mock.patch.object(
            EmailMultiAlternatives, "send", side_effect=RuntimeError("giù")
        ):
            invia_avvisi_utenze(periodo_con_addebiti, dry_run=False)

        scadenze_dopo = dict(
            Receivable.objects.filter(
                utility_period=periodo_con_addebiti
            ).values_list("id", "scadenza")
        )
        assert scadenze_dopo == scadenze_prima


class TestRegistroPush:
    def test_push_registra_device_e_codice(self, settings, immobile):
        from notifications.models import Notification, PushSubscription
        from notifications.push import invia_push

        settings.VAPID_PRIVATE_KEY = "test-vapid-private"
        settings.VAPID_PUBLIC_KEY = "test-vapid-public"
        settings.VAPID_CLAIMS_SUB = "mailto:test@viapal.it"

        assignment = _inquilino(immobile, "P", "p@example.com")
        user = assignment.tenant.user
        PushSubscription.objects.create(
            user=user,
            endpoint="https://push.example.com/registro",
            p256dh="p",
            auth="a",
            device_label="Pixel di prova",
        )
        with mock.patch("pywebpush.webpush"):
            invia_push(
                user,
                titolo="Prova",
                corpo="Corpo",
                url="/i/",
                codice="riepilogo_addebiti",
            )
        riga = Notification.objects.get(canale=Notification.CanaleComunicazione.PUSH)
        assert riga.codice == "riepilogo_addebiti"
        assert riga.destinatario == "Pixel di prova"
