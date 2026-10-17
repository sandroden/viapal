"""
Ritocchi di presentazione del db demo prima delle riprese video.

Dopo ``anonimizza_demo`` i dati sono finti ma restano quelli della storia
vera, con qualche coda che in un video per proprietari potenziali clienti
racconta la cosa sbagliata:

* addebiti di ex inquilini rimasti aperti da anni (cruscotto con "1322 g di
  ritardo"): passano a ``insoluto``, lo stato con cui un proprietario li
  stralcerebbe; il cruscotto e i ritardi li escludono già;
* gli arretrati degli ex inquilini (nessuna assegnazione in corso), che la
  pagina Notifiche addebiti conta comunque, ``insoluto`` compreso (il suo
  criterio e' lo stato "da pagare" + assenza di assegnazione attiva, non la
  data): senza allocazioni si eliminano, con allocazioni parziali il dovuto
  scende a quanto incassato e l'addebito diventa pagato (con incassante,
  vincolo ``pagato => incassante``);
* i documenti generati dal sistema (atti, cessioni) dell'inquilino delle
  riprese, cosi' il dialog "Genera" non dice "verra' sostituito";
* il membro tecnico ``bot`` (lead del bot Facebook) nella lista membri;
* le notifiche push fallite nel registro degli inviati.

Gira solo su ``viapal_demo`` con ``ENV=demo``; idempotente.
"""
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max, Q, Sum

from billing.dashboard_views import CAUSALI_OPERATIVE, STATI_DA_PAGARE
from billing.models import Receivable
from billing.models.payments import StatoPagamento
from notifications.models import Notification
from properties.models import PropertyMembership, RoomAssignment, TenantDocument
from properties.models.tenant import assegnazione_in_corso_q

LIMITE_STORICO = date(2026, 1, 1)
# inquilini delle riprese: i documenti generati si tolgono per mostrare "Genera" pulito
USERNAME_RIPRESE = ("daniela",)


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
            rimossi, saldati, irrisolti = self._ex_inquilini(date.today())

            vecchi = Receivable.objects.filter(
                stato__in=[StatoPagamento.ATTESO, StatoPagamento.IN_RITARDO],
                scadenza__lt=LIMITE_STORICO,
                assignment__valid_to__lt=LIMITE_STORICO,
            )
            n_insoluti = vecchi.update(stato=StatoPagamento.INSOLUTO)

            n_bot = PropertyMembership.objects.filter(user__username="bot").delete()[0]

            n_push = Notification.objects.filter(canale="push").filter(
                Q(inviata_at__isnull=True) | ~Q(errore="")).delete()[0]

            n_doc = self._documenti_generati()

            self.stdout.write(
                f"arretrati ex inquilini eliminati: {rimossi}, saldati: {saldati}, "
                f"irrisolti: {irrisolti}\n"
                f"documenti generati rimossi: {n_doc}\n"
                f"addebiti storici → insoluto: {n_insoluti}\n"
                f"membership del bot rimosse: {n_bot}\n"
                f"notifiche push fallite rimosse: {n_push}")
            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write("dry-run: annullato")

    def _ex_inquilini(self, oggi):
        """Toglie dalla pagina Notifiche addebiti gli arretrati degli ex inquilini.

        Stesso criterio di ``billing.calc.posizione.posizione_inquilino``: addebiti
        in stato "da pagare" (causali operative, o rate di deposito positive) di
        chi non ha un'assegnazione in corso.
        """
        attivi = RoomAssignment.objects.filter(assegnazione_in_corso_q(oggi)).values("tenant")
        aperti = (
            Receivable.objects.filter(stato__in=STATI_DA_PAGARE)
            .filter(Q(causale__in=CAUSALI_OPERATIVE)
                    | Q(causale=Receivable.Causale.DEPOSITO, importo_dovuto__gt=0))
            .exclude(assignment__tenant__in=attivi)
        )
        da_eliminare, saldati, irrisolti = [], 0, 0
        for r in aperti.annotate(tot=Sum("allocations__importo"),
                                 ultima=Max("allocations__bank_transaction__data")):
            if r.tot is None:
                da_eliminare.append(r.pk)
                continue
            if r.tot <= Decimal(0):
                irrisolti += 1   # allocazioni di segno opposto: da guardare a mano
                continue
            ultima = r.allocations.select_related("bank_transaction__owner_account") \
                .order_by("-bank_transaction__data").first()
            Receivable.objects.filter(pk=r.pk).update(
                importo_dovuto=r.tot, importo_pagato=r.tot, stato=StatoPagamento.PAGATO,
                data_pagamento=r.ultima,
                incassato_da_owner_id=ultima.bank_transaction.owner_account.owner_id)
            saldati += 1
        # le rettifiche (conguaglio_di, PROTECT) vanno via prima dell'addebito che compensano
        Receivable.objects.filter(conguaglio_di_id__in=da_eliminare,
                                  allocations__isnull=True).delete()
        rimossi = Receivable.objects.filter(pk__in=da_eliminare).delete()[1].get(
            "billing.Receivable", 0)
        return rimossi, saldati, irrisolti

    def _documenti_generati(self):
        docs = TenantDocument.objects.filter(
            generato=True, tenant__user__username__in=USERNAME_RIPRESE)
        n = docs.count()
        for d in docs:
            d.file.delete(save=False)
            d.delete()
        return n
