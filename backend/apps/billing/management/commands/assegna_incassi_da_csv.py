"""
Importa estratti conto reali (CSV) e assegna `incassato_da_owner` ai
Receivable corrispondenti (causale affitto / utenze / extra).

Convenzione: bonifici sul conto X ⇒ incassato_da_owner = X.

Formati supportati:

  --formato semplice   (es. dati/movimenti-bruna-2026.csv)
      Colonne: data,descrizione,importo_signed
      Salta importi negativi (uscite).

  --formato banca      (es. dati/movimenti-sandro-anno-in.csv)
      Colonne: Data Contabile,Data Valuta,Importo,Divisa,Causale / Descrizione,...
      Salta righe la cui causale non contiene "BON.DA".
      L'importo usa la virgola decimale e separatore migliaia "."

Uso:
    uv run manage.py assegna_incassi_da_csv \\
        --csv dati/movimenti-bruna-2026.csv --owner bruna --formato semplice
    uv run manage.py assegna_incassi_da_csv \\
        --csv dati/movimenti-sandro-anno-in.csv --owner alessandro --formato banca

Idempotente: rilanciato sovrascrive lo stesso campo.

Il matching tenant ↔ Receivable e la classificazione causale sono delegati al
modulo condiviso `billing.calc.matching` (riusato anche da `genera_storico`).
"""
import csv
import datetime
from dataclasses import dataclass
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from billing.calc.matching import (
    classifica_descrizione,
    finestra_match,
    riconosci_tenant,
)
from billing.models import Receivable
from billing.models.payments import StatoPagamento
from properties.models import OwnerProfile, TenantProfile

OWNER_KEYWORDS = {
    "bruna": "Bruna Laura",
    "alessandro": "Alessandro",
    "sandro": "Alessandro",
    "fabio": "Fabio Francesco",
}


@dataclass
class Movimento:
    data: datetime.date
    importo: Decimal
    descrizione: str
    sorgente_riga: int  # numero riga CSV (per report)


def parse_formato_semplice(path: str) -> list[Movimento]:
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):  # start=2 per intestazione
            if not row.get("data"):
                continue
            try:
                imp = Decimal(row["importo_signed"].strip())
            except Exception:
                continue
            if imp <= 0:
                continue  # uscite e zero saltate
            try:
                d = datetime.datetime.strptime(row["data"].strip(), "%Y-%m-%d").date()
            except Exception:
                continue
            out.append(Movimento(d, imp, row["descrizione"].strip(), i))
    return out


def parse_formato_banca(path: str) -> list[Movimento]:
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            causale = (row.get("Causale / Descrizione") or "").strip()
            if "BON.DA" not in causale.upper():
                continue
            raw_imp = (row.get("Importo") or "").strip().replace(".", "").replace(",", ".")
            try:
                imp = Decimal(raw_imp)
            except Exception:
                continue
            if imp <= 0:
                continue
            try:
                d = datetime.datetime.strptime(
                    row["Data Contabile"].strip(), "%d/%m/%Y"
                ).date()
            except Exception:
                continue
            out.append(Movimento(d, imp, causale, i))
    return out


def candidati_per_movimento(
    tenant: TenantProfile, mov: Movimento, causale: str
) -> list[Receivable]:
    """Ritorna i Receivable del tenant compatibili con il bonifico:
    stessa causale, e ``mov.data`` cade dentro la finestra del Receivable
    (vedi `billing.calc.matching.finestra_match`)."""
    qs = Receivable.objects.filter(
        causale=causale, assignment__tenant=tenant
    ).select_related("assignment__tenant")
    return [r for r in qs if finestra_match(r)[0] <= mov.data <= finestra_match(r)[1]]


class Command(BaseCommand):
    help = "Assegna incassato_da_owner ai pagamenti dal CSV dell'estratto conto."

    def add_arguments(self, parser):
        parser.add_argument("--csv", required=True, help="Path al CSV.")
        parser.add_argument(
            "--owner",
            required=True,
            help="bruna | alessandro | sandro | fabio (chi ha incassato).",
        )
        parser.add_argument(
            "--formato",
            required=True,
            choices=["semplice", "banca"],
            help="Formato CSV.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Non scrive nel DB, mostra solo cosa farebbe.",
        )

    def handle(self, *args, **opts):
        csv_path = opts["csv"]
        owner_key = opts["owner"].lower()
        formato = opts["formato"]
        dry_run = opts["dry_run"]

        if owner_key not in OWNER_KEYWORDS:
            raise CommandError(f"--owner deve essere uno di {list(OWNER_KEYWORDS)}")
        owner_first_name = OWNER_KEYWORDS[owner_key]
        owner = OwnerProfile.objects.filter(user__first_name=owner_first_name).first()
        if not owner:
            raise CommandError(
                f"OwnerProfile con first_name={owner_first_name!r} non trovato."
            )
        self.stdout.write(f"Owner: {owner.nominativo} (id={owner.id})")
        self.stdout.write(f"CSV:   {csv_path} ({formato})")
        self.stdout.write(f"Mode:  {'DRY-RUN' if dry_run else 'WRITE'}")
        self.stdout.write("")

        if formato == "semplice":
            mov_list = parse_formato_semplice(csv_path)
        else:
            mov_list = parse_formato_banca(csv_path)

        ok_count = 0
        skip_no_tenant: list[Movimento] = []
        ambiguo: list[tuple] = []
        no_match: list[tuple] = []

        with transaction.atomic():
            for mov in mov_list:
                tenant = riconosci_tenant(mov.descrizione)
                if not tenant:
                    skip_no_tenant.append(mov)
                    continue

                causale = classifica_descrizione(mov.descrizione)
                if causale == "unknown":
                    # fallback: importo grande → affitto, piccolo → utenze
                    causale = (
                        Receivable.Causale.AFFITTO
                        if mov.importo >= Decimal("400")
                        else Receivable.Causale.UTENZE
                    )

                candidati = candidati_per_movimento(tenant, mov, causale)
                if not candidati:
                    no_match.append((mov, tenant.nominativo, causale))
                    continue

                if len(candidati) > 1:
                    by_importo = [
                        c
                        for c in candidati
                        if abs((c.importo_dovuto or Decimal("0")) - mov.importo) < 1
                    ]
                    if len(by_importo) == 1:
                        target = by_importo[0]
                    else:
                        pagati = [
                            c for c in candidati if c.stato == StatoPagamento.PAGATO
                        ]
                        if len(pagati) == 1:
                            target = pagati[0]
                        else:
                            ambiguo.append(
                                (mov, tenant.nominativo, causale, len(candidati))
                            )
                            continue
                else:
                    target = candidati[0]

                if not dry_run:
                    target.incassato_da_owner_id = owner.id
                    update_fields = ["incassato_da_owner"]
                    if target.stato in (
                        StatoPagamento.ATTESO,
                        StatoPagamento.DICHIARATO,
                        StatoPagamento.IN_RITARDO,
                        StatoPagamento.INSOLUTO,
                    ):
                        target.stato = StatoPagamento.PAGATO
                        target.data_pagamento = mov.data
                        target.importo_pagato = mov.importo
                        update_fields += ["stato", "data_pagamento", "importo_pagato"]
                    target.save(update_fields=update_fields)
                ok_count += 1

            if dry_run:
                transaction.set_rollback(True)

        # Report
        self.stdout.write(self.style.SUCCESS(f"OK: {ok_count} record aggiornati"))
        self.stdout.write(
            f"  Totale righe CSV processate (entrate): {len(mov_list)}"
        )
        if skip_no_tenant:
            self.stdout.write(
                self.style.WARNING(f"\nSKIP (tenant non riconosciuto): {len(skip_no_tenant)}")
            )
            for m in skip_no_tenant:
                self.stdout.write(
                    f"  riga {m.sorgente_riga}: {m.data} {m.importo}€ — "
                    f"{m.descrizione[:80]}"
                )
        if ambiguo:
            self.stdout.write(
                self.style.WARNING(f"\nAMBIGUO (>1 match, non aggiornato): {len(ambiguo)}")
            )
            for m, tn, tipo, n in ambiguo:
                self.stdout.write(
                    f"  riga {m.sorgente_riga}: {m.data} {m.importo}€ "
                    f"[{tn} / {tipo} / {n} candidati]"
                )
        if no_match:
            self.stdout.write(
                self.style.WARNING(f"\nNO MATCH (nessun candidato DB): {len(no_match)}")
            )
            for m, tn, tipo in no_match:
                self.stdout.write(
                    f"  riga {m.sorgente_riga}: {m.data} {m.importo}€ "
                    f"[{tn} / {tipo}] — {m.descrizione[:60]}"
                )
