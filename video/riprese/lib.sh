#!/usr/bin/env bash
# Funzioni comuni per le riprese del video demo.
#
# Chrome headless 1920x1080 su porta CDP dedicata, pilotato da agent-browser
# (`connect`), registrato da registra.mjs (screencast CDP a 30 fps: il
# `record` di agent-browser esce a 10 fps). Si usa con `source lib.sh` dagli
# script delle scene; richiede `just demo` attivo (frontend :9022).
# CDP_PORTA diversa per ogni scena consente di girarne più d'una in parallelo.

RIPRESE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIP_DIR="$(cd "$RIPRESE_DIR/.." && pwd)/public/clips"
CDP_PORTA="${CDP_PORTA:-9333}"
BASE_URL="${BASE_URL:-http://localhost:9022}"
PROFILO="$RIPRESE_DIR/.profilo-chrome-$CDP_PORTA"
AB="agent-browser --session riprese-$CDP_PORTA"

aiuto_lib() {
  cat <<EOF
Funzioni (source lib.sh):
  avvia_chrome              Chrome headless 1920x1080 con CDP su :\$CDP_PORTA
  chiudi_chrome             ferma registrazione, Chrome e sessione agent-browser
  accedi <utente> [pwd]     login nel frontend demo (pwd default demo2026);
                            IMMOBILE=<id> sceglie l'immobile (default 1)
  apri <percorso>           apre \$BASE_URL<percorso> e prepara la scena
  prepara                   inietta cursore finto e CSS di scena
  ciak <nome>               avvia la registrazione in public/clips/<nome>.mp4
  stop                      ferma la registrazione corrente
  punta <css> [n]           porta il cursore sull'n-esimo (da 0) elemento css
  punta_testo <testo> [css] cursore sull'elemento più interno che contiene testo
  clicca <css> [n]          punta, attende la planata, clicca
  clicca_testo <testo> [css]
  scrivi <testo>            digita carattere per carattere nel campo a fuoco
  scorri <px> [durata_ms]   scroll morbido del contenitore principale
  pausa <secondi>
  attendi_testo <testo>     attende che il testo compaia nella pagina
EOF
}

avvia_chrome() {
  mkdir -p "$PROFILO" "$CLIP_DIR"
  google-chrome --headless=new --user-data-dir="$PROFILO" --no-first-run \
    --no-default-browser-check --remote-debugging-port="$CDP_PORTA" \
    --window-size=1920,1080 --hide-scrollbars --lang=it-IT \
    --disable-features=Translate about:blank >/dev/null 2>&1 &
  CHROME_PID=$!
  for _ in $(seq 50); do
    curl -s "http://127.0.0.1:$CDP_PORTA/json/version" >/dev/null && break
    sleep 0.1
  done
  $AB connect "$CDP_PORTA" >/dev/null
  $AB set viewport 1920 1080 >/dev/null
  _scena_persistente
}

# Reinietta scena.js a ogni caricamento completo (login, impersonation,
# cambio immobile ricaricano l'app): un processo node resta collegato via
# CDP con addScriptToEvaluateOnNewDocument, che vale finché la sessione
# vive. Il cursore riparte dall'ultima posizione (sessionStorage).
_scena_persistente() {
  SCENA_JS="if (window.top === window) addEventListener('DOMContentLoaded', () => {
    $(cat "$RIPRESE_DIR/scena.js");
    const c = document.getElementById('__cursore');
    const p = JSON.parse(sessionStorage.getItem('__punto') || 'null');
    if (c && p) {
      c.style.transition = 'none';
      c.style.transform = 'translate(' + (p[0] - 4) + 'px, ' + (p[1] - 2) + 'px)';
      requestAnimationFrame(() => requestAnimationFrame(() => { c.style.transition = ''; }));
    }
    addEventListener('mousemove', (e) => sessionStorage.setItem('__punto', JSON.stringify([e.clientX, e.clientY])), true);
  });" CDP_PORTA="$CDP_PORTA" node --input-type=module -e '
    const t = (await (await fetch(`http://127.0.0.1:${process.env.CDP_PORTA}/json`)).json())
      .find((x) => x.type === "page" && !x.url.startsWith("devtools://"));
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    await new Promise((ok) => (ws.onopen = ok));
    ws.send(JSON.stringify({ id: 1, method: "Page.enable" }));
    ws.send(JSON.stringify({ id: 2, method: "Page.addScriptToEvaluateOnNewDocument",
      params: { source: process.env.SCENA_JS } }));
    process.on("SIGTERM", () => { ws.close(); process.exit(0); });
    setInterval(() => {}, 1e6);' &
  INIT_PID=$!
  sleep 0.5
}

chiudi_chrome() {
  [ -n "${REC_PID:-}" ] && kill -TERM "$REC_PID" 2>/dev/null && wait "$REC_PID" 2>/dev/null
  [ -n "${INIT_PID:-}" ] && kill -TERM "$INIT_PID" 2>/dev/null
  # Chrome chiuso di colpo perde le ultime scritture di localStorage
  sleep 1
  $AB close >/dev/null 2>&1 || true
  [ -n "${CHROME_PID:-}" ] && kill "$CHROME_PID" 2>/dev/null
  return 0
}

prepara() {
  $AB eval "$(cat "$RIPRESE_DIR/scena.js")" >/dev/null
}

apri() {
  $AB open "$BASE_URL$1" >/dev/null
  $AB wait --load networkidle >/dev/null 2>&1 || true
  prepara
}

accedi() {
  local utente="$1" pwd="${2:-demo2026}"
  # Il profilo Chrome è persistente: senza pulizia /login rimanderebbe
  # alla sessione del giro precedente e il campo password non comparirebbe.
  $AB cookies clear >/dev/null 2>&1 || true
  $AB open "$BASE_URL/login" >/dev/null
  $AB wait 'input[type=password]' >/dev/null
  $AB fill 'input[autocomplete=username], input[type=text]' "$utente" >/dev/null
  $AB fill 'input[type=password]' "$pwd" >/dev/null
  $AB press Enter >/dev/null
  $AB wait 1500 >/dev/null
  # Immobile mostrato: Casa dei Tigli (a stanze), salvo IMMOBILE=<id>
  $AB eval "localStorage.setItem('vp-property-id', '${IMMOBILE:-1}')" >/dev/null
}

ciak() {
  CLIP_CORRENTE="$CLIP_DIR/$1.mp4"
  # Mai lasciare in giro la clip di un giro precedente se questo fallisce
  rm -f "$CLIP_CORRENTE"
  node "$RIPRESE_DIR/registra.mjs" "$CDP_PORTA" "$CLIP_CORRENTE" 2>"$CLIP_CORRENTE.log" &
  REC_PID=$!
  sleep 0.8
}

stop() {
  # SIGTERM e non SIGINT: in uno script non interattivo i processi in
  # background ignorano SIGINT.
  kill -TERM "$REC_PID" 2>/dev/null
  wait "$REC_PID" 2>/dev/null || true
  REC_PID=
  echo "clip: $CLIP_CORRENTE ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$CLIP_CORRENTE") s)"
}

# Coordinate del centro dell'elemento, dopo averlo portato in vista se serve.
# $1 = espressione JS che restituisce l'elemento.
_centro() {
  $AB eval "(() => { const el = $1;
    if (!el) return 'ASSENTE';
    const r0 = el.getBoundingClientRect();
    if (r0.top < 70 || r0.bottom > innerHeight - 20) el.scrollIntoView({block: 'center', behavior: 'instant'});
    const r = el.getBoundingClientRect();
    return Math.round(r.left + r.width / 2) + ' ' + Math.round(r.top + r.height / 2); })()" | tr -d '"'
}

_muovi() {
  local xy="$1" cosa="$2"
  if [ "$xy" = "ASSENTE" ] || [ -z "$xy" ]; then
    echo "elemento non trovato: $cosa" >&2
    return 1
  fi
  # shellcheck disable=SC2086
  $AB mouse move $xy >/dev/null
  PUNTO="$xy"
  sleep 0.85
}

_js_css() { printf 'document.querySelectorAll(%s)[%s]' "$(_js_str "$1")" "${2:-0}"; }
_js_testo() {
  printf '[...document.querySelectorAll(%s)].filter(e => e.offsetParent !== null && e.textContent.includes(%s)).sort((a, b) => a.textContent.length - b.textContent.length)[0]' \
    "$(_js_str "${2:-*}")" "$(_js_str "$1")"
}
_js_str() { python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"; }

punta() { _muovi "$(_centro "$(_js_css "$1" "${2:-0}")")" "$1"; }
punta_testo() { _muovi "$(_centro "$(_js_testo "$1" "${2:-*}")")" "$1"; }

_premi() {
  $AB mouse down >/dev/null
  sleep 0.08
  $AB mouse up >/dev/null
  sleep 0.4
}

clicca() { punta "$@" && _premi; }
clicca_testo() { punta_testo "$@" && _premi; }

scrivi() {
  local testo="$1" i
  for ((i = 0; i < ${#testo}; i++)); do
    $AB keyboard type "${testo:i:1}" >/dev/null
  done
}

scorri() {
  local px="$1" ms="${2:-1200}"
  $AB eval "(() => {
    const el = [...document.querySelectorAll('.q-page-container, .scroll, main')]
      .find(e => e.scrollHeight > e.clientHeight + 10 && ['auto', 'scroll'].includes(getComputedStyle(e).overflowY))
      || document.scrollingElement;
    const da = el.scrollTop, a = da + $px, t0 = performance.now();
    const passo = (t) => { const k = Math.min((t - t0) / $ms, 1);
      el.scrollTop = da + (a - da) * (k < .5 ? 2*k*k : 1 - (-2*k + 2)**2 / 2);
      if (k < 1) requestAnimationFrame(passo); };
    requestAnimationFrame(passo); return 1; })()" >/dev/null
  sleep "$(awk "BEGIN{print $ms/1000 + 0.2}")"
}

pausa() { sleep "$1"; }

# Attende che un testo compaia: `apri` aspetta solo la rete ferma, ma le
# pagine caricano i dati dopo.
attendi_testo() { $AB wait --text "$1" >/dev/null; }

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  [ "${1:-}" = "-h" ] && { aiuto_lib; exit 0; }
  echo "Da usare con: source $0   (-h per l'elenco funzioni)"
fi
