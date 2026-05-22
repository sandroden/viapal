"""Importa le spese dei proprietari dal libro mano (Contabilità.xlsx, tab «conti 2023»).

Questa prima fase importa SOLO le uscite dei proprietari, ovvero le voci a
rischio nullo di sovrapposizione con i Receivable già a sistema:

* ``tipo = a``  → arredo / manutenzione / pratiche immobile → ``Expense``
* ``tipo = g`` con "IMU" in descrizione → ``Expense`` (anticipata da un
  proprietario per conto di un altro, vedi ``riferimento_quota_owner``)

Tutti gli altri tipi (x, c, b, cauzione, p, altri g) vengono CONTATI e
riportati ma non scritti: l'affitto, le utenze e le cauzioni richiedono
l'accorpamento canone+condominio e la riconciliazione con i Receivable
esistenti — fase successiva.

Idempotente: ogni Expense importata porta nel campo ``note`` il marcatore
``[conti2023#NN]`` (NN = numero di riga nel foglio). Una seconda esecuzione
aggiorna le righe già viste invece di duplicarle. Le cifre del foglio sono
copiate senza arrotondamenti.
"""
import calendar
import datetime as dt
import re
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Codici tipo della colonna I del foglio.
TIPO_ESCLUSI = {"p"}            # personali — estranei all'affitto
TIPO_FASE2 = {"x", "c", "b", "cauzione"}  # affitto/utenze/cauzioni — fase successiva

# Colonna uscita (indice 0-based) → keyword per individuare l'OwnerProfile.
COL_USCITA_OWNER = {3: "Alessandro", 5: "Bruna", 7: "Fabio"}
COL_ENTRATA = (2, 4, 6)


class Command(BaseCommand):
    help = "Importa le spese proprietari (tipo a + IMU) dal tab «conti 2023» di Contabilità.xlsx."

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", type=str, help="Percorso del file .xlsx")
        parser.add_argument("--tab", default="conti 2023", help="Nome del foglio (default: «conti 2023»).")
        parser.add_argument("--max-row", type=int, default=214,
                            help="Ultima riga del foglio da importare (default: 214).")
        parser.add_argument("--dry-run", action="store_true", help="Non scrive nulla, mostra solo il parsing.")

    def handle(self, *args, **opts):
        try:
            from openpyxl import load_workbook
        except ImportError as e:  # noqa
            raise CommandError("openpyxl non installato: `uv add openpyxl`") from e

        xlsx_path = Path(opts["xlsx_path"]).expanduser().resolve()
        if not xlsx_path.exists():
            raise CommandError(f"File non trovato: {xlsx_path}")

        wb = load_workbook(xlsx_path, data_only=True)
        tab = opts["tab"]
        if tab not in wb.sheetnames:
            raise CommandError(f"Tab «{tab}» non trovato. Disponibili: {wb.sheetnames}")
        dry_run = opts["dry_run"]

        with transaction.atomic():
            summary = self._import(wb[tab], max_row=opts["max_row"], dry_run=dry_run)
            if dry_run:
                self.stdout.write(self.style.WARNING("DRY-RUN: rollback transazione."))
                transaction.set_rollback(True)

        self._report(summary)

    # ------------------------------------------------------------------
    def _import(self, ws, *, max_row: int, dry_run: bool) -> dict:
        from billing.models import Expense, ExpenseCategory
        from properties.models import OwnerProfile

        cat_arredo = self._categoria("arredo-manutenzione", "Arredo e manutenzione", dry_run)
        cat_imu = self._categoria("imu", "IMU", dry_run)
        owners = {kw: self._owner(kw) for kw in {"Alessandro", "Bruna", "Fabio"}}

        creati = aggiornati = 0
        tot_importato = Decimal("0")
        skip_buckets: dict[str, int] = {}
        warnings: list[str] = []
        ultima_data: dt.date | None = None

        for n, row in enumerate(ws.iter_rows(min_row=2, max_row=max_row, values_only=True), start=2):
            if not any(c not in (None, "") for c in row[:9]):
                continue
            data_raw, descr, tipo = row[0], row[1], row[8]
            descr = str(descr).strip() if descr is not None else ""
            tipo = str(tipo).strip() if tipo is not None else ""

            data_parsed = self._parse_data(data_raw)
            if data_parsed:
                ultima_data = data_parsed

            # --- voci scartate per tipo ---
            if not descr and not tipo:
                continue
            if tipo in TIPO_ESCLUSI:
                skip_buckets["p (personali)"] = skip_buckets.get("p (personali)", 0) + 1
                continue
            if tipo in TIPO_FASE2:
                skip_buckets[f"{tipo} (fase 2)"] = skip_buckets.get(f"{tipo} (fase 2)", 0) + 1
                continue

            is_imu = tipo == "g" and "imu" in descr.lower()
            if tipo == "g" and not is_imu:
                skip_buckets["g (giroconto, escluso)"] = skip_buckets.get("g (giroconto, escluso)", 0) + 1
                continue
            if tipo not in ("a",) and not is_imu:
                skip_buckets[f"{tipo or '(vuoto)'} (non gestito)"] = (
                    skip_buckets.get(f"{tipo or '(vuoto)'} (non gestito)", 0) + 1
                )
                continue

            # --- individua importo + proprietario ---
            uscite = [(idx, v) for idx in COL_USCITA_OWNER
                      if (v := self._num(row[idx]))]
            entrate = [v for idx in COL_ENTRATA if (v := self._num(row[idx]))]
            if not uscite:
                if entrate:
                    warnings.append(
                        f"riga {n}: «{descr}» è un'ENTRATA ({sum(entrate):g}€), "
                        f"non una spesa — saltata (verificare a mano)"
                    )
                else:
                    warnings.append(f"riga {n}: «{descr}» tipo {tipo} senza importo — saltata")
                continue
            if len(uscite) > 1:
                warnings.append(
                    f"riga {n}: «{descr}» ha importi in più colonne proprietario — saltata"
                )
                continue
            col_idx, importo_raw = uscite[0]
            importo = Decimal(str(importo_raw)).quantize(Decimal("0.01"))
            owner = owners[COL_USCITA_OWNER[col_idx]]

            # --- data ---
            data_eff = data_parsed or ultima_data
            data_stimata = data_parsed is None
            if data_eff is None:
                data_eff = dt.date(2022, 10, 1)
            note_extra = " · DATA STIMATA" if data_stimata else ""
            if data_stimata:
                warnings.append(f"riga {n}: «{descr}» senza data nel foglio → stimata {data_eff}")

            # --- IMU: anticipata da Bruna per conto di Fabio ---
            riferimento_quota = None
            if is_imu:
                categoria = cat_imu
                m = re.search(r"\b(fabio|sandro|bruna)\b", descr.lower())
                if m:
                    kw = {"fabio": "Fabio", "sandro": "Alessandro", "bruna": "Bruna"}[m.group(1)]
                    rif = owners[kw]
                    if rif != owner:
                        riferimento_quota = rif
            else:
                categoria = cat_arredo

            marker = f"[conti2023#{n}]"
            note = f"Importato da Contabilità.xlsx «conti 2023» riga {n}.{note_extra} {marker}"
            descrizione = descr[:300] or f"(riga {n})"

            if dry_run:
                self.stdout.write(
                    f"  riga {n:>3} | {data_eff} | {owner_kw(owner):<10} -{importo:>8}€ | "
                    f"{categoria.codice:<18} | {descrizione[:40]}"
                )
                creati += 1
                tot_importato += importo
                continue

            obj = Expense.objects.filter(note__contains=marker).first()
            defaults = dict(
                data=data_eff,
                category=categoria,
                importo=importo,
                descrizione=descrizione,
                anticipata_da_owner=owner,
                ripartibile_su_inquilini=False,
                riferimento_quota_owner=riferimento_quota,
                note=note,
            )
            if obj:
                for k, v in defaults.items():
                    setattr(obj, k, v)
                obj.save()
                aggiornati += 1
            else:
                Expense.objects.create(**defaults)
                creati += 1
            tot_importato += importo

        return {
            "creati": creati,
            "aggiornati": aggiornati,
            "tot_importato": tot_importato,
            "skip_buckets": skip_buckets,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _categoria(codice, nome, dry_run):
        from billing.models import ExpenseCategory

        cat = ExpenseCategory.objects.filter(codice=codice).first()
        if cat:
            return cat
        if dry_run:
            return ExpenseCategory(codice=codice, nome=nome, ripartibile_inquilini=False)
        return ExpenseCategory.objects.create(
            codice=codice, nome=nome, ripartibile_inquilini=False
        )

    @staticmethod
    def _owner(keyword):
        from properties.models import OwnerProfile

        for o in OwnerProfile.objects.all():
            if keyword.lower() in str(o).lower():
                return o
        raise CommandError(f"OwnerProfile per «{keyword}» non trovato.")

    @staticmethod
    def _num(v):
        """Importo della cella: numero o stringa numerica (anche con virgola)."""
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v) or None
        if isinstance(v, str):
            s = v.strip().replace(".", "").replace(",", ".") if "," in v else v.strip()
            try:
                return float(s) or None
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_data(d):
        """Parsing best-effort delle date del foglio (formati eterogenei)."""
        if isinstance(d, dt.datetime):
            return d.date()
        if isinstance(d, dt.date):
            return d
        if d is None:
            return None
        s = str(d).strip()
        # gg/mm/aaaa (anche con doppi separatori e refusi: 25/1/0123, 4/7//23)
        m = re.match(r"(\d{1,2})/+(\d{1,2})/+(\d{2,4})", s)
        if m:
            g, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3)[-2:])
            try:
                return dt.date(2000 + y, mo, g)
            except ValueError:
                return None
        # gg:mm:aa — data digitata come orario (01:11:22, 05:01:23)
        m = re.match(r"(\d{2}):(\d{2}):(\d{2})$", s)
        if m:
            g, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                return dt.date(2000 + y, mo, g)
            except ValueError:
                return None
        return None

    # ------------------------------------------------------------------
    def _report(self, s: dict):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("=== Import spese proprietari «conti 2023» ==="))
        self.stdout.write(
            f"  Expense create: {s['creati']}, aggiornate: {s['aggiornati']}, "
            f"totale importato: {s['tot_importato']}€"
        )
        if s["skip_buckets"]:
            self.stdout.write("  Righe saltate (per fase/tipo):")
            for k, v in sorted(s["skip_buckets"].items()):
                self.stdout.write(f"      {v:>3} × {k}")
        for w in s["warnings"]:
            self.stdout.write(self.style.WARNING(f"  ⚠ {w}"))


def owner_kw(owner):
    s = str(owner)
    return s.split()[0]
