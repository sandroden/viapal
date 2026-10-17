#!/usr/bin/env bash
# Scena 01 — cruscotto del proprietario: indicatori dell'anno, ritardi, scadenze.
set -euo pipefail
aiuto() { echo "Uso: $0 [-h]  — gira la scena 01 (richiede just demo attivo)"; }
main() {
  [ "${1:-}" = "-h" ] && { aiuto; return; }
  source "$(dirname "$0")/../lib.sh"
  trap chiudi_chrome EXIT
  avvia_chrome
  accedi massimo
  apri /p/
  pausa 2
  ciak 01-cruscotto
  pausa 1.5
  punta '.vp-kpi' 0
  pausa 1.2
  punta '.vp-kpi' 1
  pausa 1
  punta '.vp-kpi' 2
  pausa 1.2
  scorri 600 1600
  pausa 2
  scorri 700 1600
  pausa 2.5
  stop
}
main "$@"
