#!/usr/bin/env bash
# Scena 10 — cerca inquilini: i contatti dai gruppi Facebook e da Subito,
# ognuno con il riassunto, poi le statistiche per canale.
# Didascalia: "I contatti da Facebook e Subito, già riassunti."
set -euo pipefail

aiuto() {
  cat <<EOF
Uso: $0 [-h]
  Gira la scena 10 in public/clips/10-cerca-inquilini.mp4.
  Richiede just demo attivo. CDP_PORTA (default 9343) sceglie il Chrome.
  Sola lettura. Nelle statistiche nasconde le righe dei gruppi Facebook che
  hanno per nome solo l'ID numerico ("gruppo 1206..."): nel db demo manca
  group_label e a schermo sembrano un errore.
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

# Nasconde, anche dopo la navigazione interna, le righe "gruppo <solo cifre>".
nascondi_gruppi_numerici() {
  $AB eval "(() => {
    const nascondi = () => document.querySelectorAll('.vp-lst__gruppo').forEach((li) => {
      const n = li.querySelector('.vp-lst__gruppo-nome');
      if (n && /^gruppo [0-9]+$/.test(n.textContent.trim())) li.style.display = 'none';
    });
    new MutationObserver(nascondi).observe(document.body, { childList: true, subtree: true });
    nascondi(); return 1; })()" >/dev/null
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
  # passaggio a vuoto sulle statistiche: scalda le API
  apri /p/cerca-inquilini/statistiche
  attendi_testo 'Subito.it'
  apri /p/cerca-inquilini
  attendi_testo 'Lo contatto io'
  nascondi_gruppi_numerici
  pausa 1.5
  ciak 10-cerca-inquilini
  T0=$(date +%s.%N)
  # il riassunto del post, sotto il nome
  punta '.vp-lead__motivo' 0
  segna 'riassunto del contatto (didascalia)'
  pausa 2.3
  # statistiche per canale
  clicca_testo 'Statistiche' 'a'
  attendi_testo 'Statistiche per canale'
  segna 'statistiche per canale'
  pausa 0.4
  punta_testo 'Subito.it'
  pausa 1.8
  segna 'fine'
  stop
}

main "$@"
