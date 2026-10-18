#!/usr/bin/env bash
# Scena 06 — ritardi e solleciti: la lista di chi è in ritardo, poi la pagina
# Notifiche addebiti con l'anteprima del riepilogo email. Nessun invio: il
# bottone "Invia 2 riepiloghi" si sfiora soltanto.
set -euo pipefail

aiuto() {
  cat <<EOF
Uso: $0 [-h]  — gira la scena 06 (richiede just demo attivo)
Variabili: CDP_PORTA (default della lib), CLIP (default 06-ritardi-solleciti)
EOF
}

punta_js() { _muovi "$(_centro "$1")" "$1"; }
clicca_js() { punta_js "$1" && _premi; }

# Cursore subito a destra di una frase dentro un blocco di testo (es. il <pre>
# dell'email): l'elemento più interno sarebbe tutto il corpo del messaggio.
punta_frase() {
  local f; f="$(_js_str "$1")"
  _muovi "$($AB eval "(() => {
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) {
      const i = n.data.indexOf($f);
      if (i < 0 || n.parentElement.offsetParent === null) continue;
      const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + $f.length);
      const b = r.getBoundingClientRect();
      return Math.round(b.right + 14) + ' ' + Math.round(b.top + b.height / 2);
    }
    return 'ASSENTE'; })()" | tr -d '"')" "$1"
}

_riga_avviso() { printf "[...document.querySelectorAll('.row-name')].find(e => e.textContent.includes('%s'))" "$1"; }

main() {
  [ "${1:-}" = "-h" ] && { aiuto; return; }
  source "$(dirname "$0")/../lib.sh"
  trap chiudi_chrome EXIT
  avvia_chrome
  accedi massimo
  apri /p/ritardi
  $AB wait 2000 >/dev/null
  $AB mouse move 1000 140 >/dev/null
  pausa 1

  ciak "${CLIP:-06-ritardi-solleciti}"
  pausa 0.2
  # Chi è in ritardo (didascalia)
  punta_testo 'g di ritardo' 'td span, td div, .q-badge'
  pausa 1.8
  # Il sollecito pronto
  clicca_testo 'Notifiche addebiti' '.vp-drawer__item'
  pausa 0.8
  clicca_js "$(_riga_avviso 'Diego Palmieri')"
  pausa 0.4
  punta_frase 'scaduta il 27/07/2026 · 106,13 €'
  pausa 1.6
  punta_testo 'Invia 2 riepiloghi' button
  pausa 1.2
  stop
}
main "$@"
