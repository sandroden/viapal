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

# Identificazione prodotto: solo pattern contestuali specifici (la bolletta
# Enel/Acea menziona spesso anche l'altro servizio in testo informativo, per
# cui il match generico "GAS NATURALE" produrrebbe falsi positivi).
RX_PRODOTTO = [
    # Acea: "BOLLETTA PER LA FORNITURA DI GAS NATURALE" / "DI ENERGIA ELETTRICA"
    (re.compile(r"FORNITURA\s+DI\s+GAS\s+NATURALE", re.IGNORECASE), "gas"),
    (re.compile(r"FORNITURA\s+DI\s+ENERGIA\s+ELETTRICA", re.IGNORECASE), "luce"),
    # Enel: "spesa per il GAS NATURALE" / "spesa per l'ENERGIA ELETTRICA"
    (re.compile(r"spesa\s+per\s+\S+\s+GAS\s+NATURALE", re.IGNORECASE), "gas"),
    (re.compile(r"spesa\s+per\s+\S+\s+ENERGIA\s+ELETTRICA", re.IGNORECASE), "luce"),
    # Generici (acqua / idrico)
    (re.compile(r"FORNITURA\s+IDRICA", re.IGNORECASE), "acqua"),
    (re.compile(r"\b(servizio\s+idrico|fornitura\s+di\s+acqua)\b", re.IGNORECASE), "acqua"),
]

# Template Enel: "Periodo NOV. 2024 - DIC. 2024" (mesi italiani abbreviati).
MESI_IT_ABBR = {
    "GEN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAG": 5, "GIU": 6,
    "LUG": 7, "AGO": 8, "SET": 9, "OTT": 10, "NOV": 11, "DIC": 12,
}
RX_PERIODO_ENEL = re.compile(
    r"Periodo\s+([A-Z]{3})\.\s*(\d{4})\s*-\s*([A-Z]{3})\.\s*(\d{4})",
    re.IGNORECASE,
)
# Enel: "fattura elettronica n. 5203776675 del 11/01/2025"
RX_EMISSIONE_ENEL = re.compile(
    r"fattura\s+elettronica\s+n\.\s*\d+\s+del\s+(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
# Enel: dopo "Totale da pagare ... 284,56 €" arriva (entro ~400 caratteri,
# attraverso 2-3 righe vuote) il consumo: "844 kWh" / "39 Smc" / "25 mc".
RX_CONSUMO_ENEL = re.compile(
    r"Totale\s+da\s+pagare[^\n]+\n.{1,400}?(\d[\d\.]*)\s*(kWh|Smc|m³|mc)\b",
    re.IGNORECASE | re.DOTALL,
)


def _ultimo_giorno_mese(anno: int, mese: int) -> int:
    if mese == 12:
        return 31
    nxt = datetime.date(anno, mese + 1, 1)
    return (nxt - datetime.timedelta(days=1)).day


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
            capture_output=True, check=True, timeout=30,
            # encoding esplicito: pdftotext emette UTF-8 (€, m³). Senza, text=True
            # decodifica col locale del container (ASCII in prod) -> UnicodeDecodeError.
            encoding="utf-8", errors="replace",
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
        "prodotto": None,
    }
    m = RX_TOTALE.search(out) or RX_TOTALE_FALLBACK.search(out)
    if m:
        risultato["importo"] = _parse_importo(m.group(1))

    # Periodo: prima Acea (date numeriche), poi Enel (mesi testuali)
    m = RX_PERIODO.search(out)
    if m:
        risultato["periodo_da"] = _parse_data(m.group(1))
        risultato["periodo_a"] = _parse_data(m.group(2))
    else:
        m = RX_PERIODO_ENEL.search(out)
        if m:
            mese_da = MESI_IT_ABBR.get(m.group(1).upper())
            anno_da = int(m.group(2))
            mese_a = MESI_IT_ABBR.get(m.group(3).upper())
            anno_a = int(m.group(4))
            if mese_da and mese_a:
                risultato["periodo_da"] = datetime.date(anno_da, mese_da, 1)
                risultato["periodo_a"] = datetime.date(
                    anno_a, mese_a, _ultimo_giorno_mese(anno_a, mese_a)
                )

    # Data emissione: prima Acea, poi Enel
    m = RX_EMISSIONE.search(out)
    if m:
        risultato["data_emissione"] = _parse_data(m.group(1))
    else:
        m = RX_EMISSIONE_ENEL.search(out)
        if m:
            risultato["data_emissione"] = _parse_data(m.group(1))

    m = RX_NUM_FATTURA.search(out)
    if m:
        risultato["numero_fattura_reale"] = m.group(1)

    # Consumo: prima Acea, poi Enel (numero subito dopo "Totale da pagare X €")
    m = RX_CONSUMO.search(out)
    if m:
        risultato["consumo"] = _parse_importo(m.group(1))
    else:
        m = RX_CONSUMO_ENEL.search(out)
        if m:
            risultato["consumo"] = _parse_importo(m.group(1))

    for rx, nome in RX_FORNITORI:
        if rx.search(out):
            risultato["fornitore"] = nome
            break
    for rx, prod in RX_PRODOTTO:
        if rx.search(out):
            risultato["prodotto"] = prod
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
                        property=bill.immobile,
                        nome__iexact=dati["fornitore"],
                    ).first()
                    if not sup:
                        sup = Supplier.objects.create(
                            property=bill.immobile,
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
