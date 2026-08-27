#!/usr/bin/env bash
# Gestione della campagna: login, prova, loop.
set -euo pipefail

PROFILO="${BOT_PROFILO:-$HOME/.viapal-bot/fb-profile}"
CONFIG="${BOT_CONFIG:-$HOME/.viapal-bot/config.toml}"
DB="${BOT_DB:-$HOME/.viapal-bot/campagna.db}"
UA_HEADED="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"

aiuto() {
    cat <<'TXT'
campagna.sh — bot affitti, gruppo Facebook Monza/Brianza

USO
    ./campagna.sh <comando>

COMANDI
    login       apre Facebook in finestra vera: ti logghi a mano e chiudi
    stato       dice se la sessione regge ancora (a freddo, come nel loop)
    prova       un giro a secco: stampa i messaggi invece di notificarli
    loop        il giro vero ogni 20-30 minuti, finché non lo fermi
    azzera      cancella il database di campagna (fine campagna / ripartenza)
    pulisci     cancella dalla chat Telegram i messaggi mandati dal bot (max 48h)
    -h          questo testo

ORDINE DI UNA CAMPAGNA NUOVA
    1. aggiorna le stanze in ~/.viapal-bot/config.toml
    2. ./campagna.sh azzera
    3. ./campagna.sh login      (e chiudi la finestra quando hai finito)
    4. ./campagna.sh prova      (controlla che trovi post e classifichi bene)
    5. ./campagna.sh loop       dentro un tmux

Il bot non invia niente: prepara i testi, li mandi tu.
TXT
}

chiudi_browser() { agent-browser close >/dev/null 2>&1 || true; sleep 2; }

login() {
    chiudi_browser
    echo "Si apre Facebook: fai il login a mano, poi torna qui e premi invio."
    agent-browser --profile "$PROFILO" --headed open https://www.facebook.com/
    read -r -p "Fatto? [invio] "
    chiudi_browser   # Chrome tiene un lock sul profilo: il loop non parte finché è aperto
    stato
}

stato() {
    chiudi_browser
    agent-browser --profile "$PROFILO" --user-agent "$UA_HEADED" \
        open https://www.facebook.com/ >/dev/null 2>&1
    sleep 4
    local esito
    esito=$(agent-browser --profile "$PROFILO" --user-agent "$UA_HEADED" --json \
        eval 'document.cookie.match(/c_user=/) ? "dentro" : "fuori"' 2>/dev/null | grep -o 'dentro\|fuori' | head -1)
    chiudi_browser
    if [ "$esito" = "dentro" ]; then
        echo "✓ sessione valida"
    else
        echo "✗ sessione scaduta: rifai ./campagna.sh login"
        return 1
    fi
}

prova() { chiudi_browser; uv run python -m bot.main --once --dry-run --ignora-orario -v; }

loop() {
    chiudi_browser
    echo "loop avviato — Ctrl-C per fermare"
    while true; do
        uv run python -m bot.main --once || echo "giro fallito, riprovo al prossimo"
        local attesa=$((1200 + RANDOM % 600))   # 20-30 min, ritmo irregolare
        echo "--- prossimo giro fra $((attesa / 60)) minuti ---"
        sleep "$attesa"
    done
}

pulisci_telegram() {
    uv run python -c "
import sys; sys.path.insert(0, 'src')
from bot.config import carica
from bot.notifier import Notifier
c = carica('$CONFIG')
n = Notifier(c.telegram_token, c.telegram_chat_id)
print(f'cancellati {n.svuota_chat()} messaggi')
print('quelli più vecchi di 48 ore non si possono cancellare via API:')
print('svuota la chat dal telefono (menu della chat -> Elimina chat).')
"
}

azzera() {
    rm -f "$DB"
    echo "database di campagna cancellato: $DB"
}

case "${1:--h}" in
    login)  login ;;
    stato)  stato ;;
    prova)  prova ;;
    loop)   loop ;;
    azzera) azzera ;;
    pulisci) pulisci_telegram ;;
    -h|--help|aiuto) aiuto ;;
    *) echo "comando sconosciuto: $1"; echo; aiuto; exit 1 ;;
esac
