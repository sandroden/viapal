---
description: Un giro del bot affitti — legge il gruppo Facebook, classifica i post e notifica i lead su Telegram
---

Fai un giro del bot affitti. La classificazione e la scrittura dei messaggi le
fai **tu**, non l'API: è il motivo per cui questo comando esiste al posto di
`./campagna.sh loop`.

## 1. Estrai i post

```bash
cd bot && uv run python -m bot.main --estrai /tmp/affitti-post.json
```

Il file contiene le stanze libere, le zone accettate e i post nuovi (già
deduplicati: chi è stato contattato o visto in un giro precedente non c'è).

Se torna **0 post nuovi**, fermati qui e dillo in una riga. È il caso normale
di un giro a vuoto, non un problema.

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

## 3. Manda le notifiche

Scrivi `/tmp/affitti-lead.json` in questa forma:

```json
{
  "lead": [
    {
      "post_id": "...", "permalink": "...", "author_name": "...",
      "author_url": "...", "text": "...",
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

Gli **scartati vanno inclusi tutti**, con post_id e author_url: è quello che
impedisce di rileggerli al giro dopo. Ometterli fa ricominciare da capo ogni
volta.

```bash
cd bot && uv run python -m bot.main --notifica /tmp/affitti-lead.json
```

## 4. Riferisci

Una riga sola: quanti post letti, quanti lead, i nomi. Niente altro — questo
comando gira in loop ogni 25 minuti e l'output si accumula.

Non mandare mai messaggi su Facebook e non commentare: il bot prepara i testi,
li invia Sandro a mano.
