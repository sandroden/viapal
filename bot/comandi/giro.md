# Un giro del bot affitti

Questa è la procedura che esegue il **subagente** lanciato da `/affitti`
(`bot/comandi/affitti.md`). La classificazione e la scrittura dei messaggi le
fai **tu**, non l'API: è il motivo per cui questa procedura esiste al posto di
`./campagna.sh loop`. Lavori nella radice del repo viapal, dove sta `bot/`.

## 1. Estrai i post

```bash
cd bot && uv run python -m bot.main --estrai /tmp/affitti-post.json
```

Lancialo **in primo piano**, con timeout di 10 minuti (600000): dura uno o
due minuti, quattro o cinque nel primo giro dopo mezzogiorno, quando un
gruppo per giro si rilegge per intero (passaggio profondo). Non usare `run_in_background` né `TaskOutput`: in questa sessione
i task in background vengono uccisi alla fine del turno, e `TaskOutput` è
rimasto appeso per ore ignorando il suo timeout.

Il file contiene le stanze libere, le zone accettate e i post nuovi (già
deduplicati: chi è stato contattato o visto in un giro precedente non c'è).

Se torna **0 post nuovi**, fermati qui e rispondi con quella riga. È il caso normale
di un giro a vuoto, non un problema (il segnalibro di lettura in quel caso
avanza da solo, senza `--notifica`).

Se il comando fallisce con un errore di feed vuoto o markup cambiato, **non
insistere**: riferisci l'errore e fermati. Vuol dire che Facebook ha cambiato
qualcosa e va guardato a mano.

## 2. Classifica e componi

Leggi il JSON e applica le regole. Le regole vere stanno nei prompt, che sono
l'unica fonte: leggili prima di decidere, non andare a memoria.

- classificazione → `bot/src/bot/classifier.py`, costante `ISTRUZIONI`
- scrittura dei due messaggi → `bot/src/bot/composer.py`, costante `ISTRUZIONI`

In sintesi, ma **i file comandano**: tieni chi cerca una stanza (o "monolocale o
stanza") in zona compatibile; scarta chi offre, chi vuole solo appartamenti
interi, chi cerca dove il mercato costa meno di Monza, e chi ha animali. Il
budget indicato non è tassativo salvo che lo dichiari rigido. I messaggi non
fanno preventivi: incuriosiscono e portano al link, e possono usare solo i fatti
in `[casa]` del TOML — niente inventato, mai.

Se il post ha `"commento_senza_link": true`, quel gruppo **rifiuta i commenti
che contengono un link**: il commento pubblico non deve contenere nessun URL,
indirizzo web o nome di sito, e dice solo che hai scritto in privato e che lì
trova le foto. Il privato resta com'è, col link. Il testo esatto della regola è
`COMMENTO_SENZA_LINK` in `composer.py`.

## 3. Manda le notifiche

Scrivi `/tmp/affitti-lead.json` in questa forma:

```json
{
  "lead": [
    {
      "post_id": "...", "permalink": "...", "author_name": "...",
      "author_url": "...", "author_id": "...", "text": "...",
      "permalink_e_del_profilo": false, "group_id": "...",
      "zona": "Monza", "budget_max": 600, "disponibile_da": "settembre",
      "stanze_compatibili": ["camera-3"],
      "motivo": "una riga sul perché, la leggerà sul telefono",
      "commento_pubblico": "...", "privato": "..."
    }
  ],
  "scartati": [
    {"post_id": "...", "author_url": "...", "motivo": "offre, non cerca"}
  ]
}
```

Ricopia i campi dal JSON di partenza senza modificarli — in particolare
`author_id` e `permalink_e_del_profilo`, da cui dipendono i link della notifica
(`author_id` diventa il tap che apre la chat Messenger con quella persona), e
`group_id`, da cui la notifica capisce che quel commento va senza link.

Gli **scartati vanno inclusi tutti**, con post_id e author_url: è quello che
impedisce di rileggerli al giro dopo. Ometterli fa ricominciare da capo ogni
volta.

```bash
cd bot && uv run python -m bot.main --notifica /tmp/affitti-lead.json
```

Va lanciato anche con zero lead: oltre a registrare gli scarti, conferma il
segnalibro di lettura dei gruppi. Se salta, il giro dopo rilegge gli stessi
post.

## 4. Riferisci

La tua risposta finale è **una riga sola**: quanti post letti, quanti lead, i
nomi. Niente altro — è l'unica cosa che torna alla sessione principale, che
gira in loop ogni 25 minuti e deve restare leggera. Se qualcosa è fallito, la
riga dice cosa e a quale passo.

Non mandare mai messaggi su Facebook e non commentare: il bot prepara i testi,
li invia Sandro a mano.
