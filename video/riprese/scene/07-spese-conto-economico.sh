#!/usr/bin/env bash
# Scena 07 — spese (grafico per anno, dialog Aggiungi annullato) e conto
# economico: lettura per cassa, poi per competenza, occupazione camere.
# Didascalia: "Spese e conto economico, per cassa o per competenza."
set -euo pipefail

aiuto() {
  cat <<EOF
Uso: $0 [-h]
  Gira la scena 07 in public/clips/07-spese-conto-economico.mp4.
  Richiede just demo attivo. CDP_PORTA (default 9343) sceglie il Chrome.
  Nessun salvataggio: il dialog "Aggiungi spesa" si chiude con Annulla.
EOF
}

# Scroll morbido del contenuto del dialog aperto, fino in fondo (Annulla sta
# sotto la piega; il dialog è persistente e non si chiude con Esc).
scorri_dialog() {
  local ms="${1:-900}"
  $AB eval "(() => {
    const el = document.querySelector('.q-dialog .q-card');
    if (!el) return 0;
    const da = el.scrollTop, a = el.scrollHeight - el.clientHeight, t0 = performance.now();
    const passo = (t) => { const k = Math.min((t - t0) / $ms, 1);
      el.scrollTop = da + (a - da) * (k < .5 ? 2*k*k : 1 - (-2*k + 2)**2 / 2);
      if (k < 1) requestAnimationFrame(passo); };
    requestAnimationFrame(passo); return 1; })()" >/dev/null
  sleep "$(awk "BEGIN{print $ms/1000 + 0.2}")"
}

# Attende (max ~6 s) che un elemento visibile contenga il testo: dopo una
# navigazione interna la pagina carica i dati in modo asincrono.
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
  accedi massimo
  # passaggio a vuoto sul conto economico: scalda le API, così in ripresa
  # la pagina non resta vuota mentre carica
  apri /p/conto-economico
  attendi_testo 'Utile 2026'
  apri /p/spese
  attendi_testo '12,3k'
  pausa 1.5
  ciak 07-spese-conto-economico
  T0=$(date +%s.%N)
  pausa 0.3
  # grafico per anno e tabella per categoria
  punta_testo '12,3k'
  segna 'grafico spese per anno'
  pausa 1.2
  # Aggiungi spesa: si mostra il form e si annulla
  clicca_testo 'Aggiungi' '.q-btn'
  segna 'dialog Aggiungi spesa'
  pausa 1
  scorri_dialog 700
  clicca_testo 'Annulla' '.q-dialog .q-btn'
  pausa 0.2
  # conto economico: cassa → competenza
  clicca_testo 'Conto economico' '.vp-drawer__item'
  attendi_testo 'Utile 2026'
  segna 'conto economico (cassa)'
  pausa 1.3
  clicca_testo 'Competenza' '.q-btn'
  segna 'competenza (didascalia)'
  pausa 2.5
  punta_testo 'Camera 3'
  segna 'occupazione camere'
  pausa 2
  segna 'fine'
  stop
}

main "$@"
