# /// script
# ///
"""Parser nomi file bollette utenze Monza -> CSV.

Pattern atteso (tollerante alle varianti):
  utenze-mz-<tipo>-<YYYY>-<MM>--<importo>-<fornitore>.pdf
  utenze-mz-<tipo>-<YYYY>-<MM>=<importo>.pdf  (formato vecchio)
  utenze-mz-<tipo>-<YYYY>-<MM>-<fornitore>--<importo>.pdf

Tipo: gas | luce
Importo: arrotondato all'intero
Fornitore: enel | acea | wind | wind3 | edison | (mancante)

Uso:
  uv run scripts/parse_bollette.py -d dati/bollette/ -o dati/bollette.csv
"""
import argparse
import csv
import re
from pathlib import Path


# Catturo: tipo, anno, mese, [importo], [fornitore]
# Provo formati noti in cascata
RE_FORMATS = [
    # utenze-mz-luce-2025-04--273.pdf
    re.compile(r"^utenze-mz-(?P<tipo>luce|gas)-(?P<anno>\d{4})-(?P<mese>\d{1,2})--(?P<importo>\d+)(?:-(?P<fornitore>[a-z0-9]+))?\.pdf$"),
    # utenze-mz-luce_2025-05--156-wind3.pdf (con _ )
    re.compile(r"^utenze-mz-(?P<tipo>luce|gas)_(?P<anno>\d{4})-(?P<mese>\d{1,2})--(?P<importo>\d+)(?:-(?P<fornitore>[a-z0-9]+))?\.pdf$"),
    # utenze-mz-gas-2025-09-wind--22.pdf (fornitore prima importo)
    re.compile(r"^utenze-mz-(?P<tipo>luce|gas)-(?P<anno>\d{4})-(?P<mese>\d{1,2})-(?P<fornitore>[a-z0-9]+)--(?P<importo>\d+)\.pdf$"),
    # utenze-mz-enel-luce-2024-06=164.pdf (vecchio: fornitore-tipo-yyyy-mm=importo)
    re.compile(r"^utenze-mz-(?P<fornitore>[a-z0-9]+)-(?P<tipo>luce|gas)-(?P<anno>\d{4})-(?P<mese>\d{1,2})=(?P<importo>\d+)\.pdf$"),
    # utenze-mz-luce-2024-06--203-enel.pdf
    # gia coperto dal primo
    # utenze-mz-gas-2024-12.pdf (no importo, no fornitore) -> skip
    re.compile(r"^utenze-mz-(?P<tipo>luce|gas)-(?P<anno>\d{4})-(?P<mese>\d{1,2})\.pdf$"),
    # utenze-mz-gas-2024-02=68.pdf (vecchio: tipo-yyyy-mm=importo, no fornitore)
    re.compile(r"^utenze-mz-(?P<tipo>luce|gas)-(?P<anno>\d{4})-(?P<mese>\d{1,2})=(?P<importo>\d+)\.pdf$"),
    # utenze-mz-gas-enel-2023-09=51.pdf (vecchio: tipo-fornitore-yyyy-mm=importo)
    re.compile(r"^utenze-mz-(?P<tipo>luce|gas)-(?P<fornitore>[a-z0-9]+)-(?P<anno>\d{4})-(?P<mese>\d{1,2})=(?P<importo>\d+)\.pdf$"),
    # utenze-mz-luce-2024-1--230.pdf (mese 1 cifra)
    # gia coperto dal primo
    # utenze-mz-gas-2025-02--24-acea.pdf (gia coperto)
    # utenze-mz-2025-11--22-wind3.pdf (mancato il tipo: salta o classifica come "altro")
]


def parse_filename(fname: str) -> dict | None:
    for pat in RE_FORMATS:
        m = pat.match(fname)
        if m:
            d = m.groupdict()
            d.setdefault("importo", None)
            d.setdefault("fornitore", None)
            d["mese"] = int(d["mese"])
            d["anno"] = int(d["anno"])
            return d
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-d", "--dir", required=True, help="cartella con i PDF bollette")
    ap.add_argument("-o", "--out", required=True, help="CSV di output")
    args = ap.parse_args()

    src = Path(args.dir)
    righe = []
    skip = []
    for pdf in sorted(src.glob("utenze-mz-*.pdf")):
        d = parse_filename(pdf.name)
        if not d:
            skip.append(pdf.name)
            continue
        righe.append({
            "anno": d["anno"],
            "mese": d["mese"],
            "tipo": d["tipo"],
            "importo": d["importo"] or "",
            "fornitore": d["fornitore"] or "",
            "file": pdf.name,
        })

    righe.sort(key=lambda r: (r["anno"], r["mese"], r["tipo"]))

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["anno", "mese", "tipo", "importo", "fornitore", "file"])
        w.writeheader()
        w.writerows(righe)

    print(f"Parsate {len(righe)} bollette -> {args.out}")
    if skip:
        print(f"\n{len(skip)} file NON parsabili:")
        for n in skip:
            print(f"  - {n}")


if __name__ == "__main__":
    main()
