#!/usr/bin/env bash
# Scena 11 — documenti generati: scheda di Miriam Tosi (Casa dei Tigli)
# → tab Documenti → Genera → riepilogo dell'atto di subentro → Annulla.
# Nessun salvataggio: il riepilogo si chiude senza premere "Rigenera PDF".
set -euo pipefail
aiuto() {
  cat <<EOT
Uso: $0 [-h]  — gira la scena 11 in public/clips/11-documenti-generati.mp4
Richiede just demo attivo. Chrome su CDP_PORTA (default qui 9341).
EOT
}

# Il banner "Accendi le notifiche" (.vp-inst-banner) non è coperto da
# scena.js: lo si rinvia come farebbe il suo pulsante di chiusura.
rinvia_banner() {
  $AB eval "localStorage.setItem('vp-installa-rinviato', String(Date.now() + 365 * 864e5))" >/dev/null
}

main() {
  [ "${1:-}" = "-h" ] && { aiuto; return; }
  export CDP_PORTA="${CDP_PORTA:-9341}"
  source "$(dirname "$0")/../lib.sh"
  trap chiudi_chrome EXIT
  avvia_chrome
  accedi massimo
  rinvia_banner
  apri '/p/inquilini/70?anno=2026&tab=documenti'   # Miriam Tosi
  $AB wait --text "Profilo & contratto" >/dev/null
  $AB mouse move 1100 700 >/dev/null
  pausa 1.5
  ciak 11-documenti-generati
  pausa 0.3
  clicca_testo 'Genera' 'button'
  pausa 1.2                                   # le due voci: atto e cessione
  clicca '.vp-gsheet__voce' 0
  pausa 2.6                                   # didascalia sul riepilogo
  clicca_testo 'Annulla' 'button'
  pausa 1.2
  stop
}
main "$@"
