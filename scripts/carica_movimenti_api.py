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
import sys
from decimal import Decimal, InvalidOperation

import requests


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
    args = ap.parse_args()

    mov = leggi_csv(args.csv)
    if not mov:
        print("Nessun movimento valido nel CSV.")
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
