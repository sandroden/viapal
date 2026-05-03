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
"""
import csv
import datetime
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from billing.models import Receivable
from billing.models.payments import StatoPagamento
from properties.models import OwnerProfile, TenantProfile

# Mappa keyword (uppercase) → last_name del TenantProfile
TENANT_KEYWORDS = {
    "DI MAIO": "Di Maio",
    "DAVIDE": "Di Maio",
    "MARIASEVERA": "Armas",
    "MARIA SEVERA": "Armas",
    "SEVERA": "Armas",
    "ARMAS": "Armas",
    "POLKOTU": "Polkotu Hetti Arachchilage",
    "ESHANI": "Polkotu Hetti Arachchilage",
    "SINGARAYAR": "Singarayar",
    "ARUN": "Singarayar",
    "PORRAS": "Porras Rodriguez",
    "DIANA": "Porras Rodriguez",
    "LINDY": "Nyathi",
    "NYATHI": "Nyathi",
    "ELISA": "Chiappini",
    "CHIAPPINI": "Chiappini",
}

OWNER_KEYWORDS = {
    "bruna": "Bruna Laura",
    "alessandro": "Alessandro",
    "sandro": "Alessandro",
    "fabio": "Fabio Francesco",
}

# Pattern di riconoscimento tipo movimento (priorità: extra > utenza > affitto)
RE_EXTRA = re.compile(
    r"CONSUNTIVO|CONGUAGLIO|SPESE\s+CONDOMINIALI\s+ANNO|CONS(\.|\s)+COND",
    re.IGNORECASE,
)
RE_UTILITY = re.compile(
    r"UTENZE|BILLS|BOLLETTE|CONSUMI|UTILITIES|BOLLETTA",
    re.IGNORECASE,
)
RE_AFFITTO = re.compile(
    r"AFFITTO|CANONE|RENT(\b|\s)",
    re.IGNORECASE,
)


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


def riconosci_tenant(descrizione: str) -> Optional[TenantProfile]:
    upper = descrizione.upper()
    for kw, last_name in TENANT_KEYWORDS.items():
        if kw in upper:
            return TenantProfile.objects.filter(user__last_name=last_name).first()
    return None


def classifica(descrizione: str) -> str:
    """Ritorna 'extra' | 'utility' | 'rent' | 'unknown'."""
    if RE_EXTRA.search(descrizione):
        return "extra"
    if RE_UTILITY.search(descrizione):
        return "utility"
    if RE_AFFITTO.search(descrizione):
        return "rent"
    return "unknown"


def match_rent(tenant: TenantProfile, mov: Movimento) -> list[Receivable]:
    """Cerca Receivable affitto del tenant nel mese del bonifico (±1 mese)."""
    y, m = mov.data.year, mov.data.month
    candidati: list[Receivable] = []
    for delta in (0, -1, 1):
        target_m = m + delta
        target_y = y
        if target_m == 0:
            target_m, target_y = 12, y - 1
        elif target_m == 13:
            target_m, target_y = 1, y + 1
        candidati = list(
            Receivable.objects.filter(
                causale=Receivable.Causale.AFFITTO,
                assignment__tenant=tenant,
                competenza_da__year=target_y,
                competenza_da__month=target_m,
            )
        )
        if candidati:
            break
    return candidati


def match_utility(tenant: TenantProfile, mov: Movimento) -> list[Receivable]:
    """Receivable utenze del tenant: il bonifico paga il PERIODO PRECEDENTE
    (es. utenze gennaio pagate a febbraio). Cerco periodo nei 3 mesi prima.
    """
    y, m = mov.data.year, mov.data.month
    candidati: list[Receivable] = []
    for delta in (-1, -2, 0, -3):
        target_m = m + delta
        target_y = y
        while target_m <= 0:
            target_m += 12
            target_y -= 1
        candidati = list(
            Receivable.objects.filter(
                causale=Receivable.Causale.UTENZE,
                assignment__tenant=tenant,
                utility_period__periodo_da__year=target_y,
                utility_period__periodo_da__month=target_m,
            )
        )
        if candidati:
            break
    return candidati


def match_extra(tenant: TenantProfile, mov: Movimento) -> list[Receivable]:
    """Receivable extra del tenant nell'anno del bonifico (anno solare cassa)."""
    return list(
        Receivable.objects.filter(
            causale=Receivable.Causale.EXTRA,
            assignment__tenant=tenant,
            scadenza__year=mov.data.year,
        )
    )


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
        skip_no_tenant = []
        skip_no_tipo = []
        ambiguo = []
        no_match = []

        with transaction.atomic():
            for mov in mov_list:
                tenant = riconosci_tenant(mov.descrizione)
                if not tenant:
                    skip_no_tenant.append(mov)
                    continue

                tipo = classifica(mov.descrizione)
                if tipo == "rent":
                    candidati = match_rent(tenant, mov)
                elif tipo == "utility":
                    candidati = match_utility(tenant, mov)
                elif tipo == "extra":
                    candidati = match_extra(tenant, mov)
                else:
                    # fallback: importo grande → rent, piccolo → utility
                    if mov.importo >= Decimal("400"):
                        tipo = "rent"
                        candidati = match_rent(tenant, mov)
                    else:
                        tipo = "utility"
                        candidati = match_utility(tenant, mov)

                if not candidati:
                    no_match.append((mov, tenant.nominativo, tipo))
                    continue

                # Se più candidati: preferisco match sull'importo, poi PAGATO, poi primo
                if len(candidati) > 1:
                    by_importo = [
                        c for c in candidati
                        if abs((c.importo_dovuto or Decimal("0")) - mov.importo) < 1
                    ]
                    if len(by_importo) == 1:
                        target = by_importo[0]
                    else:
                        pagati = [c for c in candidati if c.stato == StatoPagamento.PAGATO]
                        if len(pagati) == 1:
                            target = pagati[0]
                        else:
                            ambiguo.append((mov, tenant.nominativo, tipo, len(candidati)))
                            continue
                else:
                    target = candidati[0]

                if not dry_run:
                    target.incassato_da_owner_id = owner.id
                    update_fields = ["incassato_da_owner"]
                    # Il bonifico È la prova del pagamento: se ancora pendente
                    # promuoviamo a PAGATO con la data/importo del bonifico.
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
