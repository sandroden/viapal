#!/usr/bin/env bash
# Scena 12 — più immobili: dalla pagina Immobile di Casa dei Tigli (5 stanze)
# si passa a Casa dei Gelsomini (appartamento intero, ruolo Gestore) dal
# selettore in intestazione (l'app ricarica sulla dashboard), poi si apre
# "Nuova proprietà" con la scelta a stanze / appartamento intero, senza
# creare nulla.
# Didascalia: "A stanze o appartamento intero, anche più d'uno."
set -euo pipefail

aiuto() {
  cat <<EOF
Uso: $0 [-h]
  Gira la scena 12 in public/clips/12-piu-immobili.mp4.
  Richiede just demo attivo. CDP_PORTA (default 9343) sceglie il Chrome.
  Nessun salvataggio: il form "Nuova proprietà" si mostra e basta. Alla fine
  l'immobile del profilo torna a Casa dei Tigli (vp-property-id=1).
EOF
}

# Attende (max ~6 s) che un elemento visibile contenga il testo.
attendi_testo() {
  local i
  for i in $(seq 30); do
    [ "$($AB eval "$(_js_testo "$1" "${2:-*}") ? 1 : 0")" = "1" ] && return 0
    sleep 0.2
  done
  echo "attesa scaduta: $1" >&2
}

# Tempo trascorso dal ciak, per collocare le didascalie al montaggio.
segna() { echo "  t=$(awk "BEGIN{printf \"%.1f\", $(date +%s.%N) - $T0}") s  $1" >&2; }

main() {
  [ "${1:-}" = "-h" ] && { aiuto; return; }
  export CDP_PORTA="${CDP_PORTA:-9343}"
  source "$(dirname "$0")/../lib.sh"
  trap chiudi_chrome EXIT
  avvia_chrome
  IMMOBILE=1 accedi massimo
  # passaggio a vuoto su Gelsomini: scalda le API dell'altro immobile
  $AB eval "localStorage.setItem('vp-property-id', '2')" >/dev/null
  apri /p/impostazioni
  attendi_testo 'Appartamento'
  $AB eval "localStorage.setItem('vp-property-id', '1')" >/dev/null
  apri /p/impostazioni
  attendi_testo 'Camera 5'
  pausa 1.5
  ciak 12-piu-immobili
  T0=$(date +%s.%N)
  pausa 0.4
  # Casa dei Tigli (a stanze, elenco camere a destra) → cambio immobile
  clicca '.vp-property-switcher'
  segna 'menu immobili su Tigli a stanze'
  pausa 0.2
  clicca_testo 'Casa dei Gelsomini' '.q-menu .q-item *'
  # il cambio ricarica l'app sulla dashboard del nuovo immobile
  attendi_testo 'Serkan Demir'
  # dopo il ricaricamento il cursore va rimesso dov'era
  $AB mouse move $PUNTO >/dev/null
  segna 'Gelsomini: dashboard, ruolo Gestore'
  pausa 1
  # nuova proprietà: solo il form
  clicca '.vp-property-switcher'
  pausa 0.2
  clicca_testo 'Nuova proprietà' '.q-menu .q-item *'
  attendi_testo 'Come è affittato'
  segna 'nuova proprietà (didascalia)'
  punta_testo 'Appartamento intero (un unico contratto)'
  pausa 1.9
  segna 'fine'
  stop
  # l'immobile del profilo torna Casa dei Tigli per le altre riprese; la
  # pausa lascia a Chrome il tempo di scrivere il localStorage su disco
  # prima di essere chiuso
  $AB eval "localStorage.setItem('vp-property-id', '1')" >/dev/null
  apri /p/
  pausa 3
}

main "$@"
