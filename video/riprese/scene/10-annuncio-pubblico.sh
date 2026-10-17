#!/usr/bin/env bash
# Scena 10 — annuncio pubblico /g/casa-dei-tigli: copertina, planimetria con
# i numeri delle stanze, foto di una camera libera in grande.
# Didascalia: "Un annuncio pronto da condividere."
# Fuori campo per scelta: la sezione Posizione con mappa.jpg (mappa reale,
# non di Novara) e la modalità Modifica.
set -euo pipefail

SLUG="${SLUG:-casa-dei-tigli}"

aiuto() {
  cat <<EOF
Uso: $0 [-h]
  Gira la scena 10 in public/clips/10-annuncio-pubblico.mp4.
  Richiede just demo attivo. CDP_PORTA (default 9343) sceglie il Chrome,
  SLUG (default $SLUG) la galleria. Nessuna modifica alla galleria.
EOF
}

# Scroll morbido del documento fino a portare l'elemento css a ~70 px dal
# bordo alto (sotto la barra fissa dell'annuncio).
scorri_a() {
  local css="$1" ms="${2:-1500}" dy
  dy=$($AB eval "Math.round(document.querySelector($(_js_str "$css")).getBoundingClientRect().top - 70)")
  scorri "$dy" "$ms"
}

# Tutte le foto caricate, per non vedere riquadri vuoti in ripresa.
attendi_foto() {
  local i
  for i in $(seq 40); do
    [ "$($AB eval "[...document.images].every(i => i.complete) ? 1 : 0")" = "1" ] && return 0
    sleep 0.25
  done
  echo "foto non tutte caricate" >&2
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
  apri "/g/$SLUG"
  # le immagini fuori vista sono lazy: si scorre tutto a vuoto prima del ciak
  $AB eval "(async () => { for (let y = 0; y < document.body.scrollHeight; y += 700) {
    scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); } scrollTo(0, 0); return 1; })()" >/dev/null
  attendi_foto
  pausa 1.5
  ciak 10-annuncio-pubblico
  T0=$(date +%s.%N)
  # copertina
  punta_testo 'posti letto'
  segna 'copertina (didascalia)'
  pausa 1.8
  # planimetria con i numeri, poi la camera 5 libera
  scorri_a '#planimetria' 1500
  segna 'planimetria'
  punta '.legend-name' 4
  pausa 1
  scorri_a '#room-35' 1700
  segna 'camera 5'
  pausa 0.5
  clicca '#room-35 .imgslot-expand' 1
  segna 'foto in grande'
  pausa 1.6
  clicca_testo '✕' 'button'
  pausa 0.7
  segna 'fine'
  stop
}

main "$@"
