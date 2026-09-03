---
description: Un giro del bot affitti — legge il gruppo Facebook, classifica i post e notifica i lead su Telegram
---

Fai un giro del bot affitti **delegandolo per intero a un subagente**. Questo
comando gira in loop ogni 25 minuti nella stessa sessione: niente di quello che
serve al giro (i post, i prompt, i messaggi composti) deve passare dal tuo
contesto. Tu lanci l'agente e riporti la sua riga, nient'altro.

Lancia **un solo** agente con lo strumento Agent, così:

- `subagent_type`: `general-purpose` (non `fork`: erediterebbe tutto il
  contesto, che è esattamente quello che vogliamo evitare)
- `model`: `sonnet` — classificare basterebbe Haiku, ma lo stesso agente
  scrive anche i messaggi che Sandro manda a persone vere
- `description`: `Giro bot affitti`
- `prompt`:

> Leggi il file `bot/comandi/giro.md` con Read ed esegui la procedura che
> descrive, alla lettera e per intero: estrazione, classificazione,
> composizione, notifica. I file che nomina comandano sulle tue idee. La tua
> risposta finale è una riga sola, come dice il passo 4.

Aspetta il risultato dell'agente: non lanciarne un secondo, non leggere tu
`/tmp/affitti-post.json` né i prompt in `bot/src/bot/`, non rifare la
classificazione. Quando la riga arriva, riferiscila così com'è; se l'agente
è fallito, riferisci l'errore in una riga e fermati. Non insistere: se
Facebook ha cambiato qualcosa va guardato a mano.

Non mandare mai messaggi su Facebook e non commentare: il bot prepara i testi,
li invia Sandro a mano.
