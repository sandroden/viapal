#!/usr/bin/env bash
# Scena 03 — utenze: bollette lette dall'AI, ripartizione per giorni di
# presenza, avviso email pronto, andamento dei costi.
#
# Mese: luglio 2026, chiuso e inviato. Agosto ha tutti a 31 giorni; luglio ha
# Hamza entrato a fine mese (10 giorni, quota ridotta), che racconta il
# pro-rata meglio di qualsiasi didascalia. Nessun salvataggio: si naviga solo
# tra i passi del wizard (il bottone "Invia di nuovo" non si tocca).
set -euo pipefail

aiuto() {
  cat <<EOF
Uso: $0 [-h]  — gira la scena 03 (richiede just demo attivo)
Variabili: CDP_PORTA (default della lib), CLIP (nome clip, default 03-utenze)
EOF
}

# Cursore su un elemento dato da un'espressione JS.
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

# Riga (o cella n) della tabella di ripartizione per un inquilino.
_cella() { printf "[...document.querySelectorAll('tr')].find(t => t.textContent.includes('%s')).querySelectorAll('td')[%s]" "$1" "$2"; }
_riga_avviso() { printf "[...document.querySelectorAll('.row-name')].find(e => e.textContent.includes('%s'))" "$1"; }

prepara_luglio() {
  apri /p/utenze
  $AB wait 1500 >/dev/null
  # Settembre (corrente) → agosto → luglio, fuori registrazione
  $AB click 'button[aria-label="Mese precedente"]' >/dev/null
  $AB wait 1500 >/dev/null
  $AB click 'button[aria-label="Mese precedente"]' >/dev/null
  $AB wait 2500 >/dev/null
  $AB eval "document.querySelector('h1').textContent" | grep -q luglio \
    || { echo "non sono su luglio" >&2; return 1; }
  # cursore parcheggiato in alto a destra, lontano dalle bollette
  $AB mouse move 1500 120 >/dev/null
}

main() {
  [ "${1:-}" = "-h" ] && { aiuto; return; }
  source "$(dirname "$0")/../lib.sh"
  trap chiudi_chrome EXIT
  avvia_chrome
  accedi massimo
  prepara_luglio
  pausa 1

  ciak "${CLIP:-03-utenze}"
  pausa 0.5
  # Passo 1 — le bollette lette in automatico (didascalia 1)
  punta '.strip-title'
  pausa 1.6
  punta '.imp-val' 1
  pausa 0.8
  # Passo 2 — ripartizione per giorni di presenza (didascalia 2)
  clicca_testo 'Ripartizione' button
  pausa 0.6
  punta_js "$(_cella 'Hamza Tazi' 1)"
  pausa 1.8
  punta '.pie-wrap svg'
  pausa 0.6
  # Passo 3 — l'avviso di ciascuno (didascalia 3)
  clicca_testo 'Invio' button
  pausa 0.4
  clicca_js "$(_riga_avviso 'Camila Luisa Restrepo')"
  pausa 0.2
  clicca_js "$(_riga_avviso 'Hamza Tazi')"
  pausa 0.4
  punta_frase 'Giorni di presenza nel periodo: 10'
  pausa 2
  # Tab Andamento
  clicca_testo 'Andamento' .vp-screen-tab
  pausa 0.8
  punta '.insight-title'
  pausa 0.8
  punta_js "[...document.querySelectorAll('svg')].filter(s => s.getBoundingClientRect().width > 200)[0]"
  pausa 1.6
  stop
}
main "$@"
