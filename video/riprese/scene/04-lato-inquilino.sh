#!/usr/bin/env bash
# Scena 04 — lato inquilino: dalla scheda di Diego Palmieri "Vedi come questo
# inquilino" → home inquilino → Paga con bonifico (QR) → Utenze → Torna a te.
#
# Viewport 1280x720: l'area inquilino è impaginata per telefono e a 1920 resta
# una colonna di testo minuto in mezzo al vuoto; a 1280 la colonna riempie il
# quadro e in montaggio si scala a 1920 (x1,5). La clip esce quindi 1280x720.
#
# Impersonation e "Torna a te" fanno un hard reload: la reiniezione di
# scena.js della lib (avvia_chrome) rimette cursore e CSS di scena.
# Nessun salvataggio: si apre il QR e lo si chiude con Esc.
set -euo pipefail
aiuto() {
  cat <<EOT
Uso: $0 [-h]  — gira la scena 04 in public/clips/04-lato-inquilino.mp4 (1280x720)
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
  $AB set viewport 1280 720 >/dev/null
  accedi massimo
  rinvia_banner
  apri '/p/inquilini/64?anno=2026'            # Diego Palmieri, Casa dei Tigli
  $AB wait --text "Profilo & contratto" >/dev/null
  $AB mouse move 900 420 >/dev/null
  pausa 1.5
  ciak 04-lato-inquilino
  clicca '[aria-label="Vedi come questo inquilino"]'
  $AB wait --text "Paga con bonifico" >/dev/null
  pausa 0.3
  punta_testo 'Utenze agosto 2026'
  pausa 2.2                                   # didascalia: quanto deve
  clicca_testo 'Paga con bonifico' 'button'
  pausa 2.6                                   # QR in primo piano
  $AB press Escape >/dev/null
  pausa 0.2
  clicca_testo 'Utenze' '.q-tab'
  $AB wait --text "Dettaglio delle utenze" >/dev/null
  pausa 1
  scorri 330 1200
  pausa 1
  # Durante l'impersonation l'app scorda l'immobile scelto e al ritorno
  # ripiegherebbe sul predefinito (Casa dei Gelsomini): lo si riallinea.
  $AB eval "localStorage.setItem('vp-property-id', '${IMMOBILE:-1}')" >/dev/null
  scorri -330 900                             # la barra di impersonation scorre con la pagina
  clicca_testo 'Torna a te' 'button'
  $AB wait --fn "location.pathname === '/p/'" >/dev/null
  $AB wait --load networkidle >/dev/null 2>&1 || true
  pausa 1.5
  stop
}
main "$@"
