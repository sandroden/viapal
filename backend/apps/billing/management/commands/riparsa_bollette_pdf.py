"""Riparsa i PDF delle UtilityBill già caricate ed estrae i metadati reali.

Il match con il record già esistente è il file_pdf stesso (ogni bolletta
ha già il PDF allegato). Da `pdftotext -layout` estraiamo:
- importo totale (con centesimi)
- periodo di fatturazione (periodo_da, periodo_a)
- data di emissione
- numero fattura reale (se presente)

Funziona oggi sui template "tipo Acea/Wind3" (italiani standard); per
template differenti il command logga "non riconosciuto" e salta.
"""
import datetime
import re
import subprocess
from decimal import Decimal

from django.core.management.base import BaseCommand

from billing.models import Supplier, UtilityBill

# "Totale da pagare\n\n  23,94 €"  oppure  "TOTALE DA PAGARE  23,94 €"
RX_TOTALE = re.compile(
    r"TOTALE\s+DA\s+PAGARE\s*[\n\s]+([\d\.]+,\d{2})\s*€",
    re.IGNORECASE,
)
RX_TOTALE_FALLBACK = re.compile(
    r"Totale\s+da\s+pagare\s*\n+\s*([\d\.]+,\d{2})\s*€",
    re.IGNORECASE,
)
# "Data di emissione   26/02/2026"
RX_EMISSIONE = re.compile(
    r"Data\s+di\s+emissione\s+(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
# "Periodo di fatturazione   01/01/2026 - 31/01/2026"
RX_PERIODO = re.compile(
    r"Periodo\s+di\s+fatturazione\s+(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
# "Numero fattura ... 822600506197"
RX_NUM_FATTURA = re.compile(
    r"Numero\s+fattura[^\n]*?(\d{8,})",
    re.IGNORECASE,
)
# "Consumo fatturato nel periodo di fatturazione   12 Smc" / "526 kWh" / "8 m³"
RX_CONSUMO = re.compile(
    r"Consumo\s+fatturato\s+nel\s+periodo[^\d]*?"
    r"([\d\.]+,?\d*)\s*(kWh|Smc|m³|mc)",
    re.IGNORECASE,
)

# Identificazione fornitore: pattern presenti sicuramente solo nella bolletta
# di un certo emettitore (in priorità decrescente, primo match vince).
RX_FORNITORI = [
    (re.compile(r"Acea\s+Energia\s+S\.p\.A\.", re.IGNORECASE), "Acea Energia"),
    (re.compile(r"\baceaenergia\.it\b", re.IGNORECASE), "Acea Energia"),
    (re.compile(r"WIND\s*TRE\s+ITALIA", re.IGNORECASE), "Wind Tre"),
    (re.compile(r"\bwindtre\b", re.IGNORECASE), "Wind Tre"),
    (re.compile(r"Enel\s+Energia\s+S\.p\.A\.", re.IGNORECASE), "Enel Energia"),
    (re.compile(r"Eni\s+Plenitude", re.IGNORECASE), "Eni Plenitude"),
    (re.compile(r"A2A\s+Energia", re.IGNORECASE), "A2A Energia"),
    (re.compile(r"BrianzAcque", re.IGNORECASE), "BrianzAcque"),
]


def _parse_data(s: str) -> datetime.date | None:
    try:
        return datetime.datetime.strptime(s, "%d/%m/%Y").date()
    except (TypeError, ValueError):
        return None


def _parse_importo(s: str) -> Decimal | None:
    if not s:
        return None
    norm = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(norm)
    except Exception:
        return None


def estrai_da_pdf(path: str) -> dict:
    """Estrae i campi noti dal PDF. Restituisce dict con chiavi
    'importo', 'data_emissione', 'periodo_da', 'periodo_a',
    'numero_fattura_reale'. Valori None se non trovati."""
    try:
        out = subprocess.run(
            ["pdftotext", "-layout", path, "-"],
            capture_output=True, text=True, check=True, timeout=30,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return {}

    risultato: dict = {
        "importo": None,
        "data_emissione": None,
        "periodo_da": None,
        "periodo_a": None,
        "numero_fattura_reale": None,
        "consumo": None,
        "fornitore": None,
    }
    m = RX_TOTALE.search(out) or RX_TOTALE_FALLBACK.search(out)
    if m:
        risultato["importo"] = _parse_importo(m.group(1))
    m = RX_EMISSIONE.search(out)
    if m:
        risultato["data_emissione"] = _parse_data(m.group(1))
    m = RX_PERIODO.search(out)
    if m:
        risultato["periodo_da"] = _parse_data(m.group(1))
        risultato["periodo_a"] = _parse_data(m.group(2))
    m = RX_NUM_FATTURA.search(out)
    if m:
        risultato["numero_fattura_reale"] = m.group(1)
    m = RX_CONSUMO.search(out)
    if m:
        risultato["consumo"] = _parse_importo(m.group(1))
    for rx, nome in RX_FORNITORI:
        if rx.search(out):
            risultato["fornitore"] = nome
            break
    return risultato


class Command(BaseCommand):
    help = (
        "Riparsa i PDF allegati alle UtilityBill ed aggiorna importo, "
        "periodo e data di emissione coi valori reali estratti."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--solo-id", type=int, default=None,
            help="Riparsa una sola bolletta (id)",
        )
        parser.add_argument(
            "--soglia-cent", type=int, default=50,
            help="Soglia in centesimi per segnalare diff importo (default 50)",
        )

    def handle(self, *args, **opts):
        qs = UtilityBill.objects.exclude(file_pdf="").filter(
            file_pdf__isnull=False
        )
        if opts["solo_id"]:
            qs = qs.filter(pk=opts["solo_id"])

        soglia_diff = Decimal(opts["soglia_cent"]) / Decimal(100)
        aggiornate = senza_match = uguali = errori = 0

        for bill in qs.select_related("supplier"):
            try:
                path = bill.file_pdf.path
            except (ValueError, NotImplementedError):
                continue
            dati = estrai_da_pdf(path)
            if not dati or dati.get("importo") is None:
                self.stdout.write(self.style.WARNING(
                    f"  ?  [{bill.id}] {bill.numero_fattura}: non riconosciuto"
                ))
                senza_match += 1
                continue

            modifiche: list[str] = []
            update_fields: list[str] = []

            if dati["importo"] != bill.importo_totale:
                diff = abs(dati["importo"] - bill.importo_totale)
                tag = "‼️" if diff >= soglia_diff else "·"
                modifiche.append(
                    f"{tag} importo {bill.importo_totale} → {dati['importo']}"
                )
                bill.importo_totale = dati["importo"]
                update_fields.append("importo_totale")
            if dati["periodo_da"] and dati["periodo_da"] != bill.periodo_da:
                modifiche.append(
                    f"periodo_da {bill.periodo_da} → {dati['periodo_da']}"
                )
                bill.periodo_da = dati["periodo_da"]
                update_fields.append("periodo_da")
            if dati["periodo_a"] and dati["periodo_a"] != bill.periodo_a:
                modifiche.append(
                    f"periodo_a {bill.periodo_a} → {dati['periodo_a']}"
                )
                bill.periodo_a = dati["periodo_a"]
                update_fields.append("periodo_a")
            if (
                dati["data_emissione"]
                and dati["data_emissione"] != bill.data_emissione
            ):
                modifiche.append(
                    f"emissione {bill.data_emissione} → {dati['data_emissione']}"
                )
                bill.data_emissione = dati["data_emissione"]
                update_fields.append("data_emissione")
            if dati["consumo"] is not None and dati["consumo"] != bill.consumo:
                modifiche.append(
                    f"consumo {bill.consumo} → {dati['consumo']}"
                )
                bill.consumo = dati["consumo"]
                update_fields.append("consumo")
            # Riassegna supplier solo se identificato dal PDF e diverso dall'attuale.
            if dati["fornitore"]:
                if (
                    not bill.supplier
                    or bill.supplier.nome.lower() != dati["fornitore"].lower()
                ):
                    sup = Supplier.objects.filter(
                        nome__iexact=dati["fornitore"]
                    ).first()
                    if not sup:
                        sup = Supplier.objects.create(
                            nome=dati["fornitore"],
                            tipo=Supplier.TipoFornitore.ALTRO,
                        )
                    if bill.supplier_id != sup.id:
                        modifiche.append(
                            f"supplier {bill.supplier.nome if bill.supplier else '—'} → {sup.nome}"
                        )
                        bill.supplier = sup
                        update_fields.append("supplier")

            if not modifiche:
                uguali += 1
                continue

            self.stdout.write(
                f"  → [{bill.id}] {bill.numero_fattura}: "
                + "; ".join(modifiche)
            )
            if not opts["dry_run"]:
                update_fields.append("updated_at")
                bill.save(update_fields=update_fields)
            aggiornate += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Aggiornate: {aggiornate}  Già OK: {uguali}  "
            f"Non riconosciute: {senza_match}  Errori: {errori}"
        ))
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("(dry-run: nessuna modifica scritta)"))
