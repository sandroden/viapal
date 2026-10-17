"""
Ritocchi di presentazione del db demo prima delle riprese video.

Dopo ``anonimizza_demo`` i dati sono finti ma restano quelli della storia
vera, con qualche coda che in un video per proprietari potenziali clienti
racconta la cosa sbagliata:

* addebiti di ex inquilini rimasti aperti da anni (cruscotto con "1322 g di
  ritardo"): passano a ``insoluto``, lo stato con cui un proprietario li
  stralcerebbe; il cruscotto e i ritardi li escludono già;
* il membro tecnico ``bot`` (lead del bot Facebook) nella lista membri;
* le notifiche push fallite nel registro degli inviati.

Gira solo su ``viapal_demo`` con ``ENV=demo``; idempotente.
"""
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from billing.models import Receivable
from billing.models.payments import StatoPagamento
from notifications.models import Notification
from properties.models import PropertyMembership

LIMITE_STORICO = date(2026, 1, 1)


class Command(BaseCommand):
    help = "Ritocchi di presentazione del db demo (solo viapal_demo, ENV=demo)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Mostra cosa cambierebbe e annulla.")

    def handle(self, *args, **opts):
        nome_db = settings.DATABASES["default"]["NAME"]
        if nome_db != "viapal_demo" or not getattr(settings, "DEMO", False):
            raise CommandError(f"Rifiuto: servono ENV=demo e db 'viapal_demo' (db: {nome_db}).")

        with transaction.atomic():
            vecchi = Receivable.objects.filter(
                stato__in=[StatoPagamento.ATTESO, StatoPagamento.IN_RITARDO],
                scadenza__lt=LIMITE_STORICO,
                assignment__valid_to__lt=LIMITE_STORICO,
            )
            n_insoluti = vecchi.update(stato=StatoPagamento.INSOLUTO)

            n_bot = PropertyMembership.objects.filter(user__username="bot").delete()[0]

            n_push = Notification.objects.filter(canale="push").filter(
                Q(inviata_at__isnull=True) | ~Q(errore="")).delete()[0]

            self.stdout.write(
                f"addebiti storici → insoluto: {n_insoluti}\n"
                f"membership del bot rimosse: {n_bot}\n"
                f"notifiche push fallite rimosse: {n_push}")
            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write("dry-run: annullato")
