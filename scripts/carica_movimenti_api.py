# /// script
# dependencies = ["requests"]
# ///
"""Carica un CSV di movimenti bancari nel DB viapal **via API** (idempotente).

Il CSV deve avere le colonne del formato `movimenti-sandro*.csv`:

    data,data_valuta,importo_signed,descrizione,fonte

(`data_valuta` e `fonte` sono ignorate; `importo_signed` ha già il segno:
positivo = entrata, negativo = uscita — coerente con BankTransaction).

Chiama POST /api/v1/bank-transactions/bulk-import/ con HTTP Basic.
È idempotente: rilanciarlo non crea duplicati. Se una riga combacia
(conto, data, importo) con una BankTransaction inserita a mano, la
descrizione della banca diventa quella ufficiale e la precedente viene
preservata in `note` come riga "Precedente: …".

Di default applica un **filtro pertinenza affitto**: tiene solo i
bonifici in ENTRATA e le USCITE verso le utenze gas/luce, scartando
ciò che matcha la regex `--escludi` (default GSE|Cernusco|carburanti).
Usa `--dump-esclusi scarti.csv` per vedere cosa viene tolto e
raffinare `--escludi`; `--no-filtro` carica tutto.

Uso (locale, anteprima filtro senza scrivere):
  uv run scripts/carica_movimenti_api.py \\
      --csv dati/movimenti-sandro-storico-2022-2023.csv \\
      --owner-account 14 --base-url http://localhost:8000 \\
      --dry-run --dump-esclusi /tmp/scarti.csv

Uso (locale):
  uv run scripts/carica_movimenti_api.py \\
      --csv dati/movimenti-sandro-storico-2022-2023.csv \\
      --owner-account 14 --base-url http://localhost:8000 --dry-run

Online (quando pronto, conto Sandro/Alessandro = 14):
  uv run scripts/carica_movimenti_api.py \\
      --csv dati/movimenti-sandro-storico-2022-2023.csv \\
      --owner-account 14 --base-url https://viapal.e-den.it
"""
import argparse
import csv
import re
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation

import requests

# --- Filtro pertinenza affitto (default, raffinabili da CLI) -------------
# Teniamo SOLO:
#   • ENTRATE che sono bonifici  (affitti / quote utenze versate dagli inquilini)
#   • USCITE verso le utenze gas/luce (addebiti al fornitore energia)
# e scartiamo comunque ciò che matcha PATTERN_ESCLUDI.
PATTERN_BONIFICO = r"BON\.DA|BONIFICO"
# Fornitori energia dell'IMMOBILE affittato. NB: E.ON è il fornitore
# personale di Sandro (casa sua), non dell'immobile → escluso più sotto.
PATTERN_UTENZE = (
    r"ENEL ENERGIA|ENEL ?ENERGIA|EDISON|PLENITUDE|"
    r"ACEA ENERGIA|A2A ENERGIA|\bIREN\b|SORGENIA|HERA COMM|SERVIZIO ELETTRICO"
)
# Esclusioni: GSE (incentivi fotovoltaico) e Cernusco (contributo affido) non
# c'entrano con l'affitto; FUEL/PETROL/DISTRIBUTORE sono carburante; RIVOLTA
# (Rivolta Adriana) è donazione di famiglia; E.ON ENERGIA è l'utenza personale
# di Sandro, non dell'immobile.
PATTERN_ESCLUDI = (
    r"GSE|GESTORE DEI SERVIZI ENERGETICI|CERNUSCO|FUEL|PETROL|DISTRIBUTORE|"
    r"RIVOLTA|E\.?\s?ON ENERGIA"
)


def filtra(mov: dict, pat_bonifico, pat_utenze, pat_escludi) -> tuple[bool, str]:
    """Ritorna (tieni, motivo). ``motivo`` spiega perché è scartato/tenuto."""
    descr = mov["descrizione"]
    importo = Decimal(mov["importo"])
    if pat_escludi.search(descr):
        return False, "escluso (pattern esclusione)"
    if importo > 0:
        if pat_bonifico.search(descr):
            return True, "tenuto: bonifico in entrata"
        return False, "scartato: entrata non-bonifico"
    if importo < 0:
        if pat_utenze.search(descr):
            return True, "tenuto: uscita utenza energia"
        return False, "scartato: uscita non-utenza"
    return False, "scartato: importo zero"


def leggi_csv(path: str) -> list[dict]:
    mov = []
    with open(path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            data = (row.get("data") or "").strip()
            if not data:
                continue
            try:
                imp = Decimal((row.get("importo_signed") or "").strip())
            except (InvalidOperation, AttributeError):
                print(f"  riga {i}: importo illeggibile, salto", file=sys.stderr)
                continue
            mov.append(
                {
                    "data": data,
                    "importo": str(imp),
                    "descrizione": (row.get("descrizione") or "").strip(),
                }
            )
    return mov


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--csv", required=True, help="Path al CSV dei movimenti.")
    ap.add_argument(
        "--owner-account",
        type=int,
        required=True,
        help="id OwnerBankAccount (es. 14 = Webank Sandro/Alessandro).",
    )
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="vicie")
    ap.add_argument(
        "--chunk", type=int, default=400, help="Righe per richiesta (default 400)."
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Il server calcola tutto ma fa rollback: non scrive nulla.",
    )
    ap.add_argument(
        "--no-filtro",
        action="store_true",
        help="Carica TUTTE le righe (disattiva il filtro pertinenza affitto).",
    )
    ap.add_argument(
        "--escludi",
        default=PATTERN_ESCLUDI,
        help=f"Regex (case-insensitive) di esclusione. Default: {PATTERN_ESCLUDI!r}",
    )
    ap.add_argument(
        "--pattern-utenze",
        default=PATTERN_UTENZE,
        help="Regex fornitori energia per le uscite da tenere.",
    )
    ap.add_argument(
        "--dump-esclusi",
        metavar="FILE.csv",
        help="Scrive le righe scartate (con motivo) per ispezione/raffinamento.",
    )
    args = ap.parse_args()

    mov = leggi_csv(args.csv)
    if not mov:
        print("Nessun movimento valido nel CSV.")
        return 1

    if not args.no_filtro:
        pat_b = re.compile(PATTERN_BONIFICO, re.I)
        pat_u = re.compile(args.pattern_utenze, re.I)
        pat_e = re.compile(args.escludi, re.I)
        tenuti, esclusi, motivi = [], [], Counter()
        for m in mov:
            ok, motivo = filtra(m, pat_b, pat_u, pat_e)
            motivi[motivo] += 1
            (tenuti if ok else esclusi).append({**m, "_motivo": motivo})
        print(f"\nFiltro pertinenza affitto ({len(mov)} righe lette):")
        for motivo, n in sorted(motivi.items(), key=lambda x: -x[1]):
            segno = "✓" if motivo.startswith("tenuto") else "✗"
            print(f"  {segno} {motivo}: {n}")
        print(f"  → {len(tenuti)} righe da caricare, {len(esclusi)} scartate")
        if args.dump_esclusi:
            with open(args.dump_esclusi, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(
                    f, fieldnames=["data", "importo", "descrizione", "_motivo"]
                )
                w.writeheader()
                w.writerows(esclusi)
            print(f"  scartate scritte in {args.dump_esclusi}")
        mov = [{k: v for k, v in m.items() if k != "_motivo"} for m in tenuti]
        if not mov:
            print("Nessuna riga supera il filtro.")
            return 1

    url = args.base_url.rstrip("/") + "/api/v1/bank-transactions/bulk-import/"
    print(
        f"{len(mov)} movimenti da {args.csv}\n"
        f"  → {url}  (account {args.owner_account}"
        f"{', DRY-RUN' if args.dry_run else ''})"
    )

    tot = {"creati": 0, "aggiornati": 0, "invariati": 0, "extra_db": 0}
    n_chunk = (len(mov) + args.chunk - 1) // args.chunk
    for ci, off in enumerate(range(0, len(mov), args.chunk), start=1):
        blob = mov[off : off + args.chunk]
        try:
            r = requests.post(
                url,
                json={
                    "owner_account": args.owner_account,
                    "dry_run": args.dry_run,
                    "movimenti": blob,
                },
                auth=(args.user, args.password),
                timeout=180,
            )
        except requests.RequestException as e:
            print(f"ERRORE di rete: {e}", file=sys.stderr)
            return 1
        if r.status_code != 200:
            print(f"ERRORE {r.status_code}: {r.text[:600]}", file=sys.stderr)
            return 1
        d = r.json()
        for k in tot:
            tot[k] += d.get(k, 0)
        print(
            f"  chunk {ci}/{n_chunk} ({len(blob)} righe): "
            f"creati +{d['creati']}  aggiornati ~{d['aggiornati']}  "
            f"invariati ={d['invariati']}  (extra_db {d['extra_db']})"
        )

    print(
        f"\nTOTALE: creati {tot['creati']}, aggiornati {tot['aggiornati']}, "
        f"invariati {tot['invariati']}, extra_db {tot['extra_db']}"
        + ("  [DRY-RUN: nulla scritto]" if args.dry_run else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
