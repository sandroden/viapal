"""Collega le occupazioni al contratto sotto cui stanno.

``RoomAssignment.contract`` è facoltativo, e finché resta vuoto l'inquilino
**non vede nessuna carta di contratto**: né in elenco né in download, perché
il gate è lo stesso in `PropertyDocumentViewSet` e in `core/media_private.py`.
Contratto firmato, side letter e ricevuta di registrazione spariscono dalla
sua pagina anche se spuntati «visibile agli inquilini».

Questo command collega in un colpo solo le occupazioni **iniziate dalla
decorrenza di un contratto in poi**, che è il criterio con cui la prima
assegnazione già propone il contratto: quello in vigore alla data d'ingresso.

  * **Non tocca** le occupazioni che un contratto ce l'hanno già: la
    correzione manuale vince sempre sulla regola.
  * **Non indovina** i casi a cavallo — occupazioni cominciate prima della
    decorrenza e finite dopo. Le elenca e le lascia stare: a quale contratto
    appartenga chi c'era già è una decisione di merito, non una regola.
  * Idempotente: rilanciarlo non cambia nulla.

Uso::

    uv run manage.py collega_assegnazioni_contratto --contratto "Collettivo 2025"
    uv run manage.py collega_assegnazioni_contratto --contratto "Collettivo 2025" --apply

``--dal`` sovrascrive la soglia, che di default è la decorrenza del contratto.
"""
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from properties.models import Contract, RoomAssignment


class Command(BaseCommand):
    help = "Collega al contratto le occupazioni iniziate dalla sua decorrenza."

    def add_arguments(self, parser):
        parser.add_argument(
            "--contratto",
            required=True,
            help="Nome del contratto (deve essere univoco).",
        )
        parser.add_argument(
            "--dal",
            help="Soglia AAAA-MM-GG; default: la decorrenza del contratto.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Scrive i collegamenti; senza, mostra soltanto cosa farebbe.",
        )

    def handle(self, *args, **opzioni):
        contratto = self._trova_contratto(opzioni["contratto"])
        soglia = (
            datetime.date.fromisoformat(opzioni["dal"])
            if opzioni["dal"]
            else contratto.data_decorrenza
        )
        applica = opzioni["apply"]

        if not applica:
            self.stdout.write(self.style.WARNING("DRY-RUN — niente viene scritto.\n"))
        self.stdout.write(
            f"Contratto «{contratto}» ({contratto.property.nome}), "
            f"occupazioni dal {soglia} in poi.\n"
        )

        da_collegare = RoomAssignment.objects.select_related("tenant", "room").filter(
            room__property=contratto.property,
            valid_from__gte=soglia,
            contract__isnull=True,
        ).order_by("valid_from")

        for a in da_collegare:
            self.stdout.write(
                f"  [{a.pk}] {a.valid_from} → {a.valid_to or 'in corso'} · "
                f"{a.room.nome} · {a.tenant.nominativo}"
            )
        if applica and da_collegare:
            with transaction.atomic():
                # update() e non save(): nessun calcolo legge questo campo —
                # canoni, conguagli e conto economico non lo toccano, e
                # `regime_fiscale` del contratto è solo esposto, mai usato in
                # un conto. Lo leggono la visibilità dei documenti, la
                # visualizzazione e l'eredità nella cessione. I signal delle
                # assegnazioni ricalcolerebbero addebiti senza motivo.
                RoomAssignment.objects.filter(
                    pk__in=[a.pk for a in da_collegare]
                ).update(contract=contratto)

        self.stdout.write("")
        self.stdout.write(f"Collegate: {len(da_collegare)}")
        self._segnala_gia_collegate(contratto, soglia)
        self._segnala_a_cavallo(contratto, soglia)

    # ------------------------------------------------------------------

    def _trova_contratto(self, nome):
        trovati = list(Contract.objects.select_related("property").filter(nome=nome))
        if len(trovati) != 1:
            raise CommandError(
                f"«{nome}»: {len(trovati)} contratti con questo nome. "
                "Serve un nome univoco."
            )
        return trovati[0]

    def _segnala_gia_collegate(self, contratto, soglia):
        altrui = RoomAssignment.objects.select_related("tenant", "room").filter(
            room__property=contratto.property,
            valid_from__gte=soglia,
            contract__isnull=False,
        ).exclude(contract=contratto)
        if not altrui:
            return
        self.stdout.write(
            self.style.WARNING(
                "\nNon toccate, hanno già un altro contratto:"
            )
        )
        for a in altrui:
            self.stdout.write(
                f"  [{a.pk}] {a.valid_from} · {a.tenant.nominativo} → «{a.contract}»"
            )

    def _segnala_a_cavallo(self, contratto, soglia):
        """Chi c'era già alla decorrenza: la regola non li copre."""
        a_cavallo = [
            a
            for a in RoomAssignment.objects.select_related("tenant", "room").filter(
                room__property=contratto.property,
                valid_from__lt=soglia,
                contract__isnull=True,
            ).order_by("valid_from")
            if a.valid_to is None or a.valid_to >= soglia
        ]
        if not a_cavallo:
            return
        self.stdout.write(
            self.style.WARNING(
                "\nA cavallo della decorrenza (iniziate prima, finite dopo): "
                "da decidere a mano, nessuna regola le copre."
            )
        )
        for a in a_cavallo:
            self.stdout.write(
                f"  [{a.pk}] {a.valid_from} → {a.valid_to or 'in corso'} · "
                f"{a.room.nome} · {a.tenant.nominativo}"
            )
