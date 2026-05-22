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

# Marcatori di idempotenza nel campo note dei Receivable di fase 2.
MARKER_AFFITTO = "[conti2023-affitto]"
MARKER_CAUZIONE = "[conti2023-cauzione]"

# --- Fase 2: ricostruzione affitti mancanti di Maria Severa e Teo ---------
# Dovuto mensile = canone + quota condominio, letti dal foglio «conti 2023»
# (il foglio fa fede). Curato a mano riga per riga: affitto storico una tantum.
#   (tenant, anno, mese, dovuto, fonte righe foglio, nota)
AFFITTO_RICOSTRUITO = [
    ("Maria Severa", 2022, 10, "450", "riga 8",      "informale · 380 affitto + 70 condominio"),
    ("Maria Severa", 2022, 11, "450", "riga 5",      "informale · 380 + 70"),
    ("Maria Severa", 2022, 12, "450", "righe 26+27", "informale · 180+200 affitto + 70 condominio"),
    ("Maria Severa", 2023, 1,  "450", "riga 53",     "informale · 380 + 70 (pagato 28/01)"),
    ("Maria Severa", 2023, 2,  "450", "riga 35",     "informale · 380 + 70 (pagato 31/01, competenza febbraio)"),
    ("Maria Severa", 2023, 3,  "510", "righe 66+67", "transizione · 430 + 80 (condominio con TARI)"),
    ("Maria Severa", 2023, 4,  "510", "righe 79+80", "contrattualizzato · 430 + 80"),
    ("Maria Severa", 2023, 5,  "510", "righe 85+86", "contrattualizzato · 430 + 80"),
    ("Maria Severa", 2023, 6,  "510", "righe 101+102", "contrattualizzato · 430 + 80"),
    ("Maria Severa", 2023, 7,  "510", "righe 122+123", "contrattualizzato · 430 + 80"),
    ("Maria Severa", 2023, 8,  "510", "righe 131+132", "contrattualizzato · 430 + 80"),
    ("Teo",          2023, 4,  "600", "righe 82+84", "contrattualizzato · 530 + 70"),
    ("Teo",          2023, 5,  "600", "righe 92+93", "contrattualizzato · 530 + 70"),
    ("Teo",          2023, 6,  "600", "—",           "MESE ASSENTE DAL FOGLIO: ricostruito da canone 530 + 70 — DA VERIFICARE"),
    ("Teo",          2023, 7,  "600", "righe 124+125", "contrattualizzato · 530 + 70"),
    ("Teo",          2023, 8,  "600", "righe 133+134", "contrattualizzato · 530 + 70"),
    ("Alessandra",   2022, 10, "200", "riga 13",     "informale · 165 affitto + 35 condominio (mezzo mese, ingresso 15/10)"),
    ("Alessandra",   2022, 11, "400", "riga 11",     "informale · 330 + 70"),
    ("Alessandra",   2022, 12, "400", "riga 44",     "informale · 330 + 70 (pagato 13/01/2023)"),
]

# --- Fase 2: correzione cauzioni (il foglio fa fede) ----------------------
#   (tenant, importo_corretto, nota)
CAUZIONI_CORREZIONI = [
    ("Eugenia",  "530", "foglio riga 138"),
    ("Marianna", "600", "foglio righe 187+190 (acconto 400 + 200)"),
]

# --- Fase 2: correzione affitti già a sistema (il foglio fa fede) ----------
# I Receivable affitto Severa set-dic 2023 sono a 520 ma il foglio dice 500
# (430 + 70, c'è accordo di riduzione rispetto al canone ufficiale).
#   (tenant, anno, mese, importo_corretto, nota)
AFFITTO_CORREZIONI = [
    ("Maria Severa", 2023, 9,  "500", "foglio: 430 + 70 (accordo riduzione vs canone ufficiale)"),
    ("Maria Severa", 2023, 10, "500", "foglio: 430 + 70"),
    ("Maria Severa", 2023, 11, "500", "foglio: 430 + 70"),
    ("Maria Severa", 2023, 12, "500", "foglio: 430 + 70"),
]


class Command(BaseCommand):
    help = "Importa le spese proprietari (tipo a + IMU) dal tab «conti 2023» di Contabilità.xlsx."

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", type=str, help="Percorso del file .xlsx")
        parser.add_argument("--tab", default="conti 2023", help="Nome del foglio (default: «conti 2023»).")
        parser.add_argument("--max-row", type=int, default=214,
                            help="Ultima riga del foglio da importare (default: 214).")
        parser.add_argument("--fase", choices=["1", "2", "all"], default="all",
                            help="1 = spese proprietari; 2 = affitti + cauzioni; all = entrambe.")
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

        fase = opts["fase"]
        summary1 = summary2 = None
        with transaction.atomic():
            if fase in ("1", "all"):
                summary1 = self._import(wb[tab], max_row=opts["max_row"], dry_run=dry_run)
            if fase in ("2", "all"):
                summary2 = self._fase2(dry_run=dry_run)
            if dry_run:
                self.stdout.write(self.style.WARNING("DRY-RUN: rollback transazione."))
                transaction.set_rollback(True)

        if summary1:
            self._report(summary1)
        if summary2:
            self._report_fase2(summary2)

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

    # ------------------------------------------------------------------
    # Fase 2 — affitti mancanti + correzione cauzioni
    # ------------------------------------------------------------------
    def _fase2(self, *, dry_run: bool) -> dict:
        import calendar
        from datetime import date

        from django.db.models import Q

        from billing.models import Receivable
        from properties.models import RoomAssignment, TenantProfile

        aff_rows: list[dict] = []
        corr_rows: list[dict] = []
        cau_rows: list[dict] = []
        warnings: list[str] = []

        # --- affitti ---
        for tenant_key, anno, mese, dovuto, fonte, nota in AFFITTO_RICOSTRUITO:
            tenant = TenantProfile.objects.filter(nominativo__icontains=tenant_key).first()
            if tenant is None:
                warnings.append(f"affitto {tenant_key} {anno}-{mese:02}: inquilino non trovato")
                continue
            comp_da = date(anno, mese, 1)
            comp_a = date(anno, mese, calendar.monthrange(anno, mese)[1])
            scadenza = date(anno, mese, 6)
            assignment = (
                RoomAssignment.objects.filter(tenant=tenant, valid_from__lte=comp_a)
                .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=comp_da))
                .order_by("-valid_from").first()
            )
            if assignment is None:
                warnings.append(
                    f"affitto {tenant_key} {anno}-{mese:02}: RoomAssignment mancante"
                )
                continue
            importo = Decimal(dovuto).quantize(Decimal("0.01"))
            existing = Receivable.objects.filter(
                causale="affitto", assignment=assignment,
                competenza_da=comp_da, competenza_a=comp_a,
            ).first()

            if existing and MARKER_AFFITTO not in (existing.note or ""):
                stato = "GIÀ PRESENTE (non importato da me) — non tocco"
            else:
                stato = "aggiorno" if existing else "creo"
                if not dry_run:
                    Receivable.objects.update_or_create(
                        causale="affitto", assignment=assignment,
                        competenza_da=comp_da, competenza_a=comp_a,
                        defaults=dict(
                            scadenza=scadenza,
                            importo_dovuto=importo,
                            note=f"Ricostruito da Contabilità.xlsx «conti 2023» "
                                 f"({fonte}). {nota} {MARKER_AFFITTO}",
                        ),
                    )
            aff_rows.append(dict(
                tenant=tenant_key, anno=anno, mese=mese, importo=importo,
                fonte=fonte, nota=nota, stato=stato,
            ))

        # --- correzione affitti già a sistema ---
        for tenant_key, anno, mese, importo_str, nota in AFFITTO_CORREZIONI:
            comp_da = date(anno, mese, 1)
            rec = Receivable.objects.filter(
                causale="affitto",
                assignment__tenant__nominativo__icontains=tenant_key,
                competenza_da=comp_da,
            ).first()
            if rec is None:
                warnings.append(
                    f"correzione affitto {tenant_key} {anno}-{mese:02}: Receivable non trovato"
                )
                continue
            nuovo = Decimal(importo_str).quantize(Decimal("0.01"))
            vecchio = rec.importo_dovuto
            corr_rows.append(dict(
                tenant=tenant_key, anno=anno, mese=mese,
                vecchio=vecchio, nuovo=nuovo, nota=nota, cambia=(vecchio != nuovo),
            ))
            if not dry_run and vecchio != nuovo:
                rec.importo_dovuto = nuovo
                if MARKER_AFFITTO not in (rec.note or ""):
                    rec.note = (rec.note + " " if rec.note else "") + (
                        f"Importo corretto da Contabilità.xlsx «conti 2023» "
                        f"({nota}); era {vecchio}. {MARKER_AFFITTO}"
                    )
                rec.save(update_fields=["importo_dovuto", "note"])

        # --- cauzioni ---
        for tenant_key, importo_str, nota in CAUZIONI_CORREZIONI:
            dep = (
                Receivable.objects.filter(
                    causale="deposito",
                    assignment__tenant__nominativo__icontains=tenant_key,
                    competenza_da__year__lte=2023,
                    importo_dovuto__gt=0,
                )
                .order_by("competenza_da").first()
            )
            if dep is None:
                warnings.append(f"cauzione {tenant_key}: Receivable deposito 2023 non trovato")
                continue
            nuovo = Decimal(importo_str).quantize(Decimal("0.01"))
            vecchio = dep.importo_dovuto
            cau_rows.append(dict(
                tenant=tenant_key, vecchio=vecchio, nuovo=nuovo, nota=nota,
                cambia=(vecchio != nuovo),
            ))
            if not dry_run and vecchio != nuovo:
                dep.importo_dovuto = nuovo
                if MARKER_CAUZIONE not in (dep.note or ""):
                    dep.note = (dep.note + " " if dep.note else "") + (
                        f"Importo corretto da Contabilità.xlsx «conti 2023» "
                        f"({nota}); era {vecchio}. {MARKER_CAUZIONE}"
                    )
                dep.save(update_fields=["importo_dovuto", "note"])

        return {"aff_rows": aff_rows, "corr_rows": corr_rows,
                "cau_rows": cau_rows, "warnings": warnings}

    # ------------------------------------------------------------------
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

    _MESI = ("", "gen", "feb", "mar", "apr", "mag", "giu",
             "lug", "ago", "set", "ott", "nov", "dic")

    def _report_fase2(self, s: dict):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            "=== Fase 2 — affitti ricostruiti «conti 2023» ==="))
        tenant_corrente = None
        tot = Decimal("0")
        for r in s["aff_rows"]:
            if r["tenant"] != tenant_corrente:
                tenant_corrente = r["tenant"]
                self.stdout.write(f"  {tenant_corrente}:")
            mese = f"{self._MESI[r['mese']]} {r['anno']}"
            self.stdout.write(
                f"      {mese:<9} {r['importo']:>8}€  [{r['stato']:<38}] "
                f"{r['fonte']:<16} — {r['nota']}"
            )
            if "creo" in r["stato"] or "aggiorno" in r["stato"]:
                tot += r["importo"]
        self.stdout.write(f"  Totale affitti creati/aggiornati: {tot}€")

        if s["corr_rows"]:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(
                "=== Fase 2 — correzione affitti già a sistema ==="))
            for r in s["corr_rows"]:
                mese = f"{self._MESI[r['mese']]} {r['anno']}"
                freccia = (f"{r['vecchio']} → {r['nuovo']}" if r["cambia"]
                           else f"{r['nuovo']} (invariato)")
                self.stdout.write(f"  {r['tenant']:<14} {mese:<9} {freccia:<18} — {r['nota']}")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("=== Fase 2 — cauzioni ==="))
        for r in s["cau_rows"]:
            freccia = f"{r['vecchio']} → {r['nuovo']}" if r["cambia"] else f"{r['nuovo']} (invariata)"
            self.stdout.write(f"  {r['tenant']:<10} {freccia:<20} — {r['nota']}")

        for w in s["warnings"]:
            self.stdout.write(self.style.WARNING(f"  ⚠ {w}"))


def owner_kw(owner):
    s = str(owner)
    return s.split()[0]
