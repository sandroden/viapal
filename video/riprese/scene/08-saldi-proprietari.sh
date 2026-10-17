#!/usr/bin/env bash
# Scena 08 — saldi tra proprietari: chi ha anticipato cosa, chi deve a chi.
# Didascalia: "Più proprietari? Chi ha anticipato cosa, e chi deve a chi."
set -euo pipefail

aiuto() {
  cat <<EOF
Uso: $0 [-h]
  Gira la scena 08 in public/clips/08-saldi-proprietari.mp4.
  Richiede just demo attivo. CDP_PORTA (default 9343) sceglie il Chrome.
  Sola lettura: nessun clic su "Registra bonifico" o "Chiudi periodo".
EOF
}

# Attende (max ~6 s) che un elemento visibile contenga il testo: dopo una
# navigazione la pagina carica i dati in modo asincrono.
attendi_testo() {
  local i
  for i in $(seq 30); do
    [ "$($AB eval "$(_js_testo "$1" "${2:-*}") ? 1 : 0")" = "1" ] && return 0
    sleep 0.2
  done
  echo "attesa scaduta: $1" >&2
}

# Nasconde le sezioni sotto "Chi deve a chi" (settlement, BT inter-owner,
# movimenti bilaterali): gergo tecnico in inglese che nel video distrae.
nascondi_sezioni_tecniche() {
  $AB eval "document.querySelectorAll('.vp-saldi__sezione').forEach((s, i) => { if (i >= 2) s.style.display = 'none'; }); 1" >/dev/null
}

# Tempo trascorso dal ciak, per collocare le didascalie al montaggio.
segna() { echo "  t=$(awk "BEGIN{printf \"%.1f\", $(date +%s.%N) - $T0}") s  $1" >&2; }

main() {
  [ "${1:-}" = "-h" ] && { aiuto; return; }
  export CDP_PORTA="${CDP_PORTA:-9343}"
  source "$(dirname "$0")/../lib.sh"
  trap chiudi_chrome EXIT
  avvia_chrome
  accedi massimo
  apri /p/saldi-proprietari
  attendi_testo 'Tocca per registrarlo'
  nascondi_sezioni_tecniche
  pausa 1.5
  ciak 08-saldi-proprietari
  T0=$(date +%s.%N)
  pausa 0.3
  # un saldo per proprietario
  punta '.vp-saldi__totale' 0
  segna 'saldi per proprietario (didascalia)'
  pausa 0.7
  punta '.vp-saldi__totale' 2
  pausa 0.2
  punta_testo 'di cui anticipi di tasca propria'
  segna 'anticipi di tasca propria'
  pausa 0.8
  # i bonifici minimi per pareggiare
  punta '.vp-saldi__rientro-riga' 0
  segna 'chi deve a chi'
  pausa 2.4
  segna 'fine'
  stop
}

main "$@"
