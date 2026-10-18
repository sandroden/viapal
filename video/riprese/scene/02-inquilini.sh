#!/usr/bin/env bash
# Scena 02 — inquilini: elenco → scheda di Diego Palmieri (Casa dei Tigli) →
# pagamenti, profilo & contratto, documenti con anteprima dell'atto.
# Nessun salvataggio: solo navigazione tra le schede.
set -euo pipefail
aiuto() {
  cat <<EOT
Uso: $0 [-h]  — gira la scena 02 in public/clips/02-inquilini.mp4
Richiede just demo attivo. Chrome su CDP_PORTA (default qui 9341).
EOT
}

# Il banner "Accendi le notifiche" (.vp-inst-banner) non è coperto da
# scena.js: lo si rinvia come farebbe il suo pulsante di chiusura, che scrive
# solo una preferenza del browser.
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
  apri /p/inquilini
  $AB wait --text "Diego Palmieri" >/dev/null
  $AB mouse move 1150 640 >/dev/null        # cursore già in campo al ciak
  pausa 1.5
  ciak 02-inquilini
  pausa 0.2
  clicca_testo 'Diego Palmieri' 'td'
  $AB wait --text "Profilo & contratto" >/dev/null
  pausa 0.3
  # via dagli importi in alto: il cursore va sull'affitto ancora atteso
  punta_testo 'atteso' '.q-badge, .q-badge *, td span'
  pausa 2.2                                  # didascalia sulla scheda
  clicca_testo 'Profilo & contratto' '[role=tab]'
  pausa 1.3
  clicca_testo 'Documenti' '[role=tab]'
  pausa 0.6
  clicca_testo 'Atto di subentro nel contratto' '[role=button]'
  pausa 2.5
  stop
}
main "$@"
