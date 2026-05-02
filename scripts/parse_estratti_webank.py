# /// script
# dependencies = ["openpyxl"]
# ///
"""Parser estratti conto Webank PDF + xlsx -> CSV unico.

Estrae transazioni da:
- PDF Webank "Estratto conto_DD-MM-YYYY.pdf" (richiede pdftotext nel PATH)
- xlsx Webank "movimenti.xlsx" formato 7 colonne

Produce un CSV con colonne: data, data_valuta, importo_signed, descrizione, fonte
(importo_signed: positivo = entrata, negativo = uscita)

Uso:
  uv run scripts/parse_estratti_webank.py -d dati/ -o dati/movimenti-sandro.csv
"""
import argparse
import csv
import re
import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path


# Pattern riga PDF estratto Webank:
# "DD/MM/YY  DD/MM/YY  DD/MM/YY  [- importo]  [importo]  descrizione"
RE_RIGA = re.compile(
    r"^\s*"
    r"(\d{2}/\d{2}/\d{2})\s+"  # data contabile
    r"(\d{2}/\d{2}/\d{2})\s+"  # data valuta
    r"(\d{2}/\d{2}/\d{2})\s+"  # data operazione
    r"(.*)$"                    # resto: importi + descrizione
)
RE_IMPORTO = re.compile(r"-?\s?[\d.]+,\d{2}")


def parse_pdf(path: Path) -> list[dict]:
    txt = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True, capture_output=True, text=True
    ).stdout

    movimenti = []
    corrente = None
    for raw in txt.splitlines():
        m = RE_RIGA.match(raw)
        if m:
            data_c, _data_v, _data_op, resto = m.groups()
            # Estrai importi: 0, 1 o 2. Se 2, il primo (con o senza '-') e' uscita,
            # il secondo e' entrata. Se 1, decido dal contesto del segno.
            importi = RE_IMPORTO.findall(resto)
            descrizione = resto
            for imp in importi:
                descrizione = descrizione.replace(imp, "", 1)
            descrizione = descrizione.strip()
            if not importi:
                continue  # riga senza importi, salta
            # Heuristica: posizione dell'importo nel testo originale
            # In Webank: USCITE in colonna ~95, ENTRATE in colonna ~120 (dopo lo spazio)
            # Sempre l'ultimo importo e' quello "vero" della riga (primo solo se uscita)
            if len(importi) >= 2:
                # uscita + entrata sulla stessa riga e' improbabile — di solito
                # i due numeri sono "saldo" e "importo". Prendo l'ultimo.
                imp = importi[-1]
                segno = -1 if importi[0].startswith("-") else 1
            else:
                imp = importi[0]
                # decido segno da posizione: se nel testo l'importo e' preceduto
                # da '-' o sta in posizione "USCITE" (tipicamente prima di descrizione)
                segno = -1 if imp.lstrip().startswith("-") else 1
            valore = Decimal(imp.replace("-", "").replace(".", "").replace(",", ".").strip())
            corrente = {
                "data": datetime.strptime(data_c, "%d/%m/%y").date().isoformat(),
                "data_valuta": datetime.strptime(_data_v, "%d/%m/%y").date().isoformat(),
                "importo_signed": str(valore * segno),
                "descrizione": descrizione,
                "fonte": path.name,
            }
            movimenti.append(corrente)
        else:
            # Riga di continuazione descrizione (no data)
            stripped = raw.strip()
            if corrente and stripped and not RE_IMPORTO.search(stripped):
                corrente["descrizione"] = corrente["descrizione"] + " " + stripped
    return movimenti


def parse_xlsx(path: Path) -> list[dict]:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    movimenti = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        # Skip header (riga 1)
        for row in rows[1:]:
            if not row or not row[0]:
                continue
            data_c, data_v, importo, _div, descr, _stato, _canale = (row + (None,) * 7)[:7]
            if not data_c or importo is None:
                continue
            # data_c puo' essere stringa "DD/MM/YYYY" o datetime
            if isinstance(data_c, datetime):
                d = data_c.date().isoformat()
            elif hasattr(data_c, "isoformat"):
                d = data_c.isoformat()
            else:
                d = datetime.strptime(str(data_c), "%d/%m/%Y").date().isoformat()
            if isinstance(data_v, datetime):
                dv = data_v.date().isoformat()
            elif hasattr(data_v, "isoformat"):
                dv = data_v.isoformat()
            else:
                dv = datetime.strptime(str(data_v), "%d/%m/%Y").date().isoformat()
            # In xlsx l'importo e' float positivo: il segno e' implicito nel "Cont."
            # ma qui ho solo entrate (BON.DA = entrata) — se servisse parsare anche
            # le uscite serve guardare la colonna "Stato"
            movimenti.append({
                "data": d,
                "data_valuta": dv,
                "importo_signed": str(Decimal(str(importo))),
                "descrizione": str(descr or "").strip(),
                "fonte": path.name,
            })
    return movimenti


def parse_txt_appendix(path: Path) -> list[dict]:
    """Parse altri-conti-sandro.txt: TSV con
    data\tdata_valuta\timporto\tdivisa\tdescrizione\t..."""
    movimenti = []
    for raw in path.read_text().splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if len(parts) < 5:
            continue
        try:
            d = datetime.strptime(parts[0], "%d/%m/%Y").date().isoformat()
            dv = datetime.strptime(parts[1], "%d/%m/%Y").date().isoformat()
            importo = Decimal(parts[2].replace(",", "."))
            descr = parts[4].strip()
            movimenti.append({
                "data": d, "data_valuta": dv,
                "importo_signed": str(importo),
                "descrizione": descr, "fonte": path.name,
            })
        except (ValueError, IndexError):
            continue
    return movimenti


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-d", "--dir", required=True, help="cartella con i file da parsare")
    ap.add_argument("-o", "--out", required=True, help="CSV di output")
    args = ap.parse_args()

    src = Path(args.dir)
    movimenti = []

    for pdf in sorted(src.glob("Estratto conto_*.pdf")):
        n_prima = len(movimenti)
        movimenti.extend(parse_pdf(pdf))
        print(f"  PDF {pdf.name}: {len(movimenti) - n_prima} righe")

    for xlsx in sorted(src.glob("*.xlsx")):
        n_prima = len(movimenti)
        movimenti.extend(parse_xlsx(xlsx))
        print(f"  XLSX {xlsx.name}: {len(movimenti) - n_prima} righe")

    txt = src / "altri-conti-sandro.txt"
    if txt.exists():
        n_prima = len(movimenti)
        movimenti.extend(parse_txt_appendix(txt))
        print(f"  TXT {txt.name}: {len(movimenti) - n_prima} righe")

    # Dedup su (data, importo_signed, descrizione[:40])
    visti = set()
    unici = []
    for m in movimenti:
        k = (m["data"], m["importo_signed"], m["descrizione"][:40])
        if k in visti:
            continue
        visti.add(k)
        unici.append(m)

    unici.sort(key=lambda m: m["data"])

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["data", "data_valuta", "importo_signed", "descrizione", "fonte"])
        w.writeheader()
        w.writerows(unici)

    print(f"\nTotale righe: {len(movimenti)}, dedup: {len(unici)} -> {args.out}")
    if unici:
        print(f"Periodo: {unici[0]['data']} → {unici[-1]['data']}")


if __name__ == "__main__":
    main()
