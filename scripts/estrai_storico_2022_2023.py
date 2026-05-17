# /// script
# dependencies = []
# ///
"""STEP 1 import storico: estrae i movimenti dai nuovi estratti Webank
2022/2023 in un CSV separato, fermandosi dove inizia movimenti-sandro.csv
(dati completi dal 2024-01-01).

Riusa parse_pdf() di parse_estratti_webank.py.

Uso:
  uv run scripts/estrai_storico_2022_2023.py
"""
import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATI = ROOT / "dati"
CUTOFF = "2024-01-01"  # movimenti-sandro.csv ha dati completi da qui in poi
OUT = DATI / "movimenti-sandro-storico-2022-2023.csv"

# PDF storici nuovi (gli estratti trimestrali 2022 e 2023 coprono 2022-01 -> 2023-12)
PDF_STORICI = [
    "Estratto conto_31-03-2022.pdf",
    "Estratto conto_30-06-2022.pdf",
    "Estratto conto_30-09-2022.pdf",
    "Estratto conto_31-12-2022.pdf",
    "Estratto conto_31-03-2023.pdf",
    "Estratto conto_30-06-2023.pdf",
    "Estratto conto_30-09-2023.pdf",
    "Estratto conto_31-12-2023.pdf",
]

# Import parse_pdf dal parser esistente
spec = importlib.util.spec_from_file_location(
    "parse_estratti_webank", ROOT / "scripts" / "parse_estratti_webank.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# Marcatori del footer legale del PDF: la descrizione vera finisce qui.
# (l'ultima riga di ogni estratto altrimenti assorbe tutto il testo di chiusura)
RE_FOOTER = mod.re.compile(
    r"\s*(\*1 DATA CONTABILE|RIASSUNTO SCALARE|INDEX:;|"
    r"DATA CONTABILE: è il giorno)"
)


def pulisci_footer(m: dict) -> dict:
    m["descrizione"] = RE_FOOTER.split(m["descrizione"], maxsplit=1)[0].strip()
    return m


def main():
    movimenti = []
    for nome in PDF_STORICI:
        pdf = DATI / nome
        if not pdf.exists():
            print(f"  ATTENZIONE: manca {nome}")
            continue
        righe = [pulisci_footer(m) for m in mod.parse_pdf(pdf)]
        movimenti.extend(righe)
        print(f"  PDF {nome}: {len(righe)} righe")

    # Cutoff: tieni solo movimenti con data contabile < 2024-01-01
    prima = len(movimenti)
    movimenti = [m for m in movimenti if m["data"] < CUTOFF]
    print(f"\n  Cutoff {CUTOFF}: {prima} -> {len(movimenti)} righe (scartate {prima - len(movimenti)} del 2024+)")

    # Dedup su (data, importo_signed, descrizione[:40]) come nel parser principale
    visti = set()
    unici = []
    for m in movimenti:
        k = (m["data"], m["importo_signed"], m["descrizione"][:40])
        if k in visti:
            continue
        visti.add(k)
        unici.append(m)
    unici.sort(key=lambda m: m["data"])

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["data", "data_valuta", "importo_signed", "descrizione", "fonte"]
        )
        w.writeheader()
        w.writerows(unici)

    print(f"\nTotale: {len(movimenti)}, dedup: {len(unici)} -> {OUT}")
    if unici:
        print(f"Periodo: {unici[0]['data']} -> {unici[-1]['data']}")


if __name__ == "__main__":
    main()
