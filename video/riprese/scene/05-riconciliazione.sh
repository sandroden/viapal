#!/usr/bin/env bash
# Scena 05 — riconciliazione: clic su un bonifico in entrata, gli addebiti
# dell'inquilino, la spunta e "residuo 0,00 €"; poi Annulla (nessun salvataggio).
#
# Immobile: Casa dei Gelsomini (IMMOBILE=2). Su Casa dei Tigli non c'è nel db
# demo una coppia bonifico/addebito dello stesso inquilino che chiuda a zero.
# Qui il bonifico Serkan Demir 1.134 € ha già 259 € sull'affitto di ottobre:
# cliccandolo il pannello mostra l'abbinamento esistente (niente avviso rosso
# "Cancella abbinamenti", che compare solo con pannello vuoto) e la spunta sul
# deposito da 875 € porta il residuo a 0,00.
set -euo pipefail

aiuto() {
  cat <<EOF
Uso: $0 [-h]  — gira la scena 05 (richiede just demo attivo)
Variabili: CDP_PORTA (default della lib), CLIP (default 05-riconciliazione),
           IMMOBILE (default 2, Casa dei Gelsomini)
EOF
}

punta_js() { _muovi "$(_centro "$1")" "$1"; }
clicca_js() { punta_js "$1" && _premi; }

# Voce della lista (bonifico o addebito) che contiene il testo
# Cursore con la punta appena sotto una frase, per non coprirla
punta_sotto() {
  local f; f="$(_js_str "$1")"
  _muovi "$($AB eval "(() => {
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) {
      const i = n.data.indexOf($f);
      if (i < 0 || n.parentElement.offsetParent === null) continue;
      const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + $f.length);
      const b = r.getBoundingClientRect();
      return Math.round(b.left + b.width / 2) + ' ' + Math.round(b.bottom + 4);
    }
    return 'ASSENTE'; })()" | tr -d '"')" "$1"
}

_voce() { printf "[...document.querySelectorAll('.vp-p-rec__item')].find(e => e.textContent.includes('%s'))" "$1"; }

main() {
  [ "${1:-}" = "-h" ] && { aiuto; return; }
  source "$(dirname "$0")/../lib.sh"
  trap chiudi_chrome EXIT
  export IMMOBILE="${IMMOBILE:-2}"
  avvia_chrome
  accedi massimo
  apri /p/riconciliazione
  $AB wait 2500 >/dev/null
  $AB eval "!!($(_voce 'Deposito Nov 2025'))" | grep -q true \
    || { echo "bonifico di Serkan non trovato" >&2; return 1; }
  $AB mouse move 700 200 >/dev/null
  pausa 1

  ciak "${CLIP:-05-riconciliazione}"
  pausa 0.8
  # Clic 1: il bonifico in entrata
  clicca_js "$(_voce 'Deposito Nov 2025').querySelector('.vp-p-rec__bt-importo')"
  pausa 1.2
  # gli addebiti si restringono all'inquilino dedotto dal bonifico
  punta_testo 'Inquilino:' '.vp-p-rec__col-meta'
  pausa 1.2
  # Clic 2: la spunta sul deposito
  clicca_js "$(_voce 'Deposito (versamento)').querySelector('.q-checkbox')"
  pausa 0.8
  # residuo 0,00 € (didascalia)
  punta_sotto 'residuo 0,00'
  pausa 2.8
  # Annulla: nulla viene salvato
  clicca_testo 'Annulla' '.vp-p-rec__pannello button'
  pausa 1.5
  stop
}
main "$@"
