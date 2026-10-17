#!/usr/bin/env bash
# Scena 07 — notifiche: l'addebito che Karthik Pillai dichiara di aver pagato
# (stato "dichiarato", preparato da `cura_demo_video`) è nei ritardi come "Da
# confermare"; in montaggio ci cade sopra la notifica push simulata
# (componente NotificaPush). Poi Immobile → Avvisi (chi riceve l'avviso: menu
# aperto e chiuso con Esc), Area personale → "Notifiche su questo dispositivo"
# (l'interruttore si sfiora soltanto) e il registro degli inviati.
# Nessun salvataggio e nessun clic su Conferma/Rifiuta.
set -euo pipefail

aiuto() {
  cat <<EOT
Uso: $0 [-h]  — gira la scena 07 in public/clips/07-notifiche.mp4
Richiede just demo attivo e \`cura_demo_video\` già lanciato (addebito dichiarato).
Variabili: CDP_PORTA (default qui 9344), CLIP (default 07-notifiche)
EOT
}

# Riga dei ritardi con l'addebito dichiarato (chip "Da confermare")
_riga_dichiarata() {
  printf "[...document.querySelectorAll('tr')].find(r => r.textContent.includes('Da confermare'))"
}

ritardi() {
  punta_testo 'Da confermare'
  pausa 3.4                                   # notifica simulata + didascalia
  _muovi "$(_centro "[...$(_riga_dichiarata).querySelectorAll('button')].find(b => b.textContent.includes('Conferma'))")" Conferma
  pausa 1.0
}

chi_riceve() {
  clicca_testo 'Immobile' '.vp-drawer__item'
  attendi_testo 'Avvisa del pagamento dichiarato'
  pausa 0.6
  clicca '[data-testid="immobile-notifica_dichiarazioni"]'
  pausa 0.9
  punta_testo 'Solo chi riceve il bonifico' '.q-item'
  pausa 1.2
  $AB press Escape >/dev/null                 # menu chiuso, valore invariato
  pausa 0.4
}

dispositivo() {
  clicca_testo 'Massimo' '.q-btn'
  pausa 0.5
  clicca '[data-testid="menu-area-personale"]'
  attendi_testo 'Notifiche su questo dispositivo'
  pausa 0.3
  punta '.q-toggle'                           # solo sfiorato
  pausa 1.8
}

registro() {
  clicca_testo 'Notifiche addebiti' '.vp-drawer__item'
  attendi_testo 'Da inviare'
  pausa 0.4
  clicca_testo 'Inviati' '.vp-screen-tab'
  attendi_testo 'Riepilogo addebiti'
  pausa 0.3
  punta_testo 'Riepilogo addebiti'
  pausa 2.2
}

main() {
  [ "${1:-}" = "-h" ] && { aiuto; return; }
  export CDP_PORTA="${CDP_PORTA:-9344}"
  source "$(dirname "$0")/../lib.sh"
  trap chiudi_chrome EXIT
  avvia_chrome
  accedi massimo
  apri /p/ritardi
  attendi_testo 'Da confermare'
  $AB mouse move 1000 140 >/dev/null
  pausa 1

  ciak "${CLIP:-07-notifiche}"
  pausa 0.3
  ritardi
  chi_riceve
  dispositivo
  registro
  stop
}
main "$@"
