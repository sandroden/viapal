"""
Inserisce un ExtraCharge "Conguaglio condominiale <anno>" per ogni inquilino
attivo a una data di riferimento, e segna come pagati quelli passati come argomento.

Uso (default 2025):
    python manage.py inserisci_conguaglio_condominiale --anno 2025 --importo 262 \
        --data-invio 2026-01-28 --giorni-scadenza 60 \
        --pagato Eshani:2026-04-08 --pagato "Maria Severa":2026-03-28 \
        --pagato Davide:2026-03-28
"""
import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from billing.models import Receivable, StatoPagamento
from properties.models import RoomAssignment, TenantProfile  # noqa: F401


def _parse_date(s: str) -> datetime.date:
    return datetime.datetime.strptime(s, "%Y-%m-%d").date()


class Command(BaseCommand):
    help = "Inserisce ExtraCharge per il conguaglio condominiale annuo."

    def add_arguments(self, parser):
        parser.add_argument("--anno", type=int, required=True)
        parser.add_argument("--importo", type=str, required=True)
        parser.add_argument(
            "--data-invio",
            type=str,
            required=True,
            help="Data di invio del conguaglio (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--giorni-scadenza",
            type=int,
            default=60,
            help="Giorni dalla data invio entro cui pagare (default: 60).",
        )
        parser.add_argument(
            "--pagato",
            action="append",
            default=[],
            help="Coppie 'nome_parziale:YYYY-MM-DD' per marcare pagati.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Stampa cosa farebbe senza scrivere.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        anno = opts["anno"]
        importo = Decimal(opts["importo"])
        data_invio = _parse_date(opts["data_invio"])
        scadenza = data_invio + datetime.timedelta(days=opts["giorni_scadenza"])
        pagati_arg = opts["pagato"]
        dry = opts["dry_run"]
        oggi = datetime.date.today()

        pagati_map: dict[str, datetime.date] = {}
        for p in pagati_arg:
            if ":" not in p:
                raise CommandError(f"Argomento --pagato malformato: {p}")
            nome, data_str = p.rsplit(":", 1)
            pagati_map[nome.strip().lower()] = _parse_date(data_str)

        riferimento = datetime.date(anno, 12, 31)

        assignments = (
            RoomAssignment.objects
            .filter(valid_from__lte=riferimento)
            .filter(
                # attivo a fine anno: senza valid_to oppure valid_to dopo riferimento
                # (ma anche valid_to all'interno dell'anno significa "presente nell'anno")
            )
            .select_related("tenant")
            .order_by("tenant__nominativo")
        )
        # Prendiamo gli assignment ATTIVI alla data_invio (chi paga ora il conguaglio
        # dell'anno scorso e' chi e' presente all'invio). In alternativa si potrebbe
        # filtrare su presenza nell'anno: per ora usiamo "attivo alla data invio".
        assignments_attivi = []
        for a in assignments:
            if a.valid_from <= data_invio and (a.valid_to is None or a.valid_to >= data_invio):
                assignments_attivi.append(a)

        self.stdout.write(self.style.NOTICE(
            f"Inserisco conguaglio condominiale {anno} (importo {importo}€) "
            f"per {len(assignments_attivi)} inquilini attivi al {data_invio}."
        ))
        self.stdout.write(f"Scadenza: {scadenza}.")

        descrizione = f"Conguaglio condominiale {anno}"
        creati = 0
        aggiornati = 0
        skipped = 0

        for a in assignments_attivi:
            nominativo = a.tenant.nominativo
            nome_lower = nominativo.lower()

            data_pagamento = None
            for chiave, dt in pagati_map.items():
                if chiave in nome_lower:
                    data_pagamento = dt
                    break

            if data_pagamento:
                stato = StatoPagamento.PAGATO
                importo_pagato = importo
            elif scadenza < oggi:
                stato = StatoPagamento.IN_RITARDO
                importo_pagato = None
            else:
                stato = StatoPagamento.ATTESO
                importo_pagato = None

            existing = Receivable.objects.filter(
                assignment=a,
                causale=Receivable.Causale.EXTRA,
                descrizione=descrizione,
            ).first()

            if existing:
                self.stdout.write(
                    f"  - {nominativo}: gia' presente (id={existing.id}), aggiorno stato={stato}"
                )
                if not dry:
                    existing.importo_dovuto = importo
                    existing.scadenza = scadenza
                    existing.competenza_da = data_invio
                    existing.stato = stato
                    if data_pagamento:
                        existing.data_pagamento = data_pagamento
                        existing.importo_pagato = importo_pagato
                    existing.save()
                aggiornati += 1
                continue

            self.stdout.write(
                f"  + {nominativo}: stato={stato}"
                + (f" pagato il {data_pagamento}" if data_pagamento else "")
            )
            if not dry:
                Receivable.objects.create(
                    assignment=a,
                    causale=Receivable.Causale.EXTRA,
                    competenza_da=data_invio,
                    descrizione=descrizione,
                    importo_dovuto=importo,
                    scadenza=scadenza,
                    stato=stato,
                    importo_pagato=importo_pagato,
                    data_pagamento=data_pagamento,
                    note=(
                        f"Inserito da management command (data invio msg: {data_invio}, "
                        f"scadenza legge 2 mesi)."
                    ),
                )
            creati += 1

        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN: nessuna scrittura."))
            transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS(
            f"Done. Creati={creati}, aggiornati={aggiornati}, skipped={skipped}."
        ))
