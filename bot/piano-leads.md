# Piano — Lead su viapal: pagina web, multi-gruppo, pubblicazione

Estensione della [spec](spec.md): i lead trovati dal bot vengono registrati anche
su viapal via API, per lavorarli da una pagina web in due (Sandro + Bruna, che
non userebbe l'admin Django). Telegram resta il campanello immediato; la pagina
diventa lo stato condiviso: chi è stato contattato, da chi, com'è andata.

Principio invariato dalla spec: strumento da campagna, non servizio. A campagna
chiusa i dati si cancellano — anche sul server (vedi §6).

## 1. Architettura

```
scraper → classifier → composer → notifier (Telegram, invariato)
             ↓                        ↓
          SQLite ————— push ————→ viapal API → pagina /p/leads
        (dedup + coda)  (best-effort,           (stato condiviso,
                         idempotente)            lavoro in 2)
```

Proprietà dei campi, l'unica regola che non si può sbagliare:

- **il bot possiede** i dati di scoperta: testo, autore, permalink, analisi,
  messaggi proposti, gruppo, seen_at. L'upsert li aggiorna sempre.
- **gli umani possiedono** lo stato di lavorazione: stato, preso_da, note.
  L'upsert **non li tocca mai** — altrimenti il secondo passaggio dello scraper
  sullo stesso post azzererebbe il flag di chi ha già scritto.

Il push è best-effort: se viapal è giù il bot non si blocca e non perde nulla
(Telegram resta primario). Colonna `pushed_at` in SQLite; a ogni giro si
ripushano le righe `matched AND pushed_at IS NULL`. Con l'endpoint idempotente
il retry è gratis e il sistema si auto-ripara.

Si pushano **solo i lead match**, non gli scarti: la pagina serve a lavorare,
non a rivedere il classifier (per quello c'è il report dry-run). Meno dati di
terzi sul server = meno superficie GDPR.

## 2. Backend viapal — app `leads`

Nuova app `backend/apps/leads/` (accanto a accounting/billing/…).

### Modello `Lead`

```
identità:   post_id (unique), group_id, group_label
dal bot:    author_name, author_url, permalink, link_messenger,
            testo, analisi (JSONField: zona, budget_max, disponibile_da,
            stanze_compatibili, motivo),
            commento_proposto, privato_proposto, seen_at
umani:      stato ∈ {nuovo, contattato, risposto, scartato}  (estendibile)
            preso_da (FK User, null), preso_at, contattato_at, note
```

I due messaggi composti viaggiano nel payload: sono il cuore della pagina
(bottoni copia). Oggi SQLite salva solo l'analisi → vedi §3.

### Endpoint

- `POST /api/v1/leads/bulk-upsert/` — per il bot. HTTP Basic come il
  bulk-import movimenti (stesso pattern di `carica_movimenti_api.py`), con un
  utente dedicato `bot` nel gruppo proprietari. Idempotente su `post_id`,
  aggiorna solo i campi bot, risponde `{creati, aggiornati, invariati}`.
- `GET /api/v1/leads/?stato=&gruppo=` + `PATCH /api/v1/leads/<id>/` — per la
  pagina. Permesso: gruppo proprietari (pattern esistente). Il PATCH accetta
  **solo** i campi umani.
- "Presa in carico": `PATCH {preso_da: me}`; se già preso da un altro il FE lo
  mostra invece del bottone. A ~10 lead/sera non servono lock né realtime.
- `POST /api/v1/leads/chiudi-campagna/` — svuota la tabella (§6).

Admin changelist minimale comunque (per Sandro), più i test API
(ricordare `VIAPAL_DB_NAME` per i test in parallelo).

## 3. Bot — push e coda

- Nuovo modulo `api_push.py` (~60 righe): httpx, base_url + Basic auth da
  `config.toml` sezione `[api]` (url, user, password). Se la sezione manca, il
  push è disattivato e tutto funziona come oggi.
- SQLite: colonne nuove `pushed_at`, `commento`, `privato`, `group_id`,
  `group_label` (i messaggi servono in SQLite perché il retry di un giro
  successivo deve avere il payload completo). Migrazione: `ALTER TABLE ADD
  COLUMN` con try/ignora — o si ricrea il db, tanto è per-campagna.
- `main.py`: dopo il giro, push in blocco delle righe non ancora pushate.
  Errori → log + (se persistono per N giri) `notifier.allarme`.

## 4. Multi-gruppo

I dati cambiano poco, ma un punto è controintuitivo: **il group_id va preso dal
contesto dello scrape, non dal parsing del permalink** — il permalink si
smaschera solo con l'hover e a volte manca (vedi estrazione.py), il gruppo che
stiamo scrollando invece lo sappiamo sempre.

- Config: da `group_id` singolo a lista

  ```toml
  [[facebook.gruppi]]
  id = "123456"
  nome = "Affitti Monza e Brianza"
  ```

  retrocompatibile: se c'è ancora `group_id` scalare, diventa una lista da uno.
- `scraper.raccogli()` è già parametrico su `group_id`: il loop di `main`
  itera sui gruppi, il `Post` guadagna `group_id`/`group_label`.
- Dedup: `post_id` resta la chiave (gli id post di FB sono globali). La dedup
  secondaria per `author_url` diventa **cross-gruppo**, ed è un vantaggio:
  la stessa persona che posta in due gruppi riceve un solo contatto.
- Pagina e Telegram mostrano il gruppo solo se i gruppi configurati sono >1.

## 5. Pagina web — `ProprietarioLeads.vue` su `/p/leads`

Sezione Proprietari del menu (etichetta proposta: **"Cerca inquilini"** —
"lead" in menu non parla a Bruna). Mobile-first: si usa dal telefono, insieme
a Messenger.

Lista di card, default filtro `stato=nuovo`, ordinate per `seen_at` desc:

```
┌──────────────────────────────────────────┐
│ Maria R.  ·  📍 Monza  ·  💶 max 450     │
│ ➜ stanza S2, S4 — «cerca da ottobre…»    │
│ [testo del post, espandibile]            │
│                                          │
│ [Scrivi su Messenger]  [Apri il post]    │
│ [copia commento]  [copia privato]        │
│                                          │
│ (Lo prendo io) | Preso da Bruna 14:02    │
│ stato: nuovo → contattato → risposto     │
│        → scartato          [note…]       │
└──────────────────────────────────────────┘
```

- Bottoni copia con `navigator.clipboard` + feedback — sostituiscono il
  tap-che-copia di Telegram.
- Filtri: stato, gruppo (se >1), preso da.
- Refresh: bottone/pull, niente websocket. Il campanello per il nuovo lead
  resta Telegram; in seguito, volendo, Web Push (l'infrastruttura VAPID c'è
  già) — fase 2, non ora.

## 6. GDPR — chiusura campagna

Sul server finiscono dati di terzi (nomi, URL profilo FB, testi). La regola
della spec — "a campagna chiusa si cancella il db, punto" — deve seguire i
dati: l'azione **"chiudi campagna"** (endpoint + bottone in pagina, o command)
svuota `leads` così come si cancella il `.db` locale. Da annotare nel registro
trattamenti quando si farà (piano GDPR, fase registro).

## 7. Pubblicare i post

Contesto: la via ufficiale non esiste più (il permesso `publish_to_groups` è
morto anni fa, la Groups API nel 2024). Quello che il vecchio sito faceva era
quasi certamente lo **Share/Feed Dialog**: non un'API che pubblica, ma l'UI di
FB pre-compilata dove l'utente completa a mano. Quella strada esiste ancora ed
è la prima da usare. Tre livelli, in ordine di rischio:

### A. Condivisione assistita (zero rischio, subito)

Bottone "Condividi" nella galleria pubblica `/g/slug`: `navigator.share` su
mobile (apre lo share nativo → Facebook → "in un gruppo"), fallback
`sharer.php` su desktop. Le anteprime OG sono già pronte (commit recenti):
il post nel gruppo esce con foto e titolo. Costo: un'ora.

### B. Bump del proprio post (il vero rimedio al "si finisce in fondo")

Il post che affonda non si risolve ripubblicandolo (i duplicati li rimuovono
gli admin) ma **commentando il proprio post esistente**: l'attività recente lo
fa risalire nel feed "rilevanti", che è quello che vede la maggioranza.
Comando manuale `bot bump`: apre `link_post_fb` (già in config), scrive un
commento variato generato dal composer ("ancora libere la singola e la
doppia…"), e **si ferma prima dell'invio** per il click umano (headed).
Guardrail in config: cadenza minima (es. ≥48 h), mai dentro il loop.

### C. Post nuovo nel gruppo

Comando manuale `bot pubblica --gruppo X`: compone testo variato + link
galleria, riempie il composer del gruppo via agent-browser, si ferma prima di
"Pubblica" (flag `--invia` per chi vuole il submit automatico, sconsigliato
come default). Rischi da mettere in conto: le azioni di *scrittura* sono
quelle che l'antispam osserva davvero; molti gruppi hanno coda di approvazione
e regole sulla frequenza degli annunci; l'account che ripete lo stesso
annuncio rischia il ban dal gruppo prima che da FB. Mitigazioni: solo trigger
manuale, testo sempre diverso, cadenza minima per gruppo, mai schedulato.

**Fuori discussione**: repost automatico a orologio.

La spec va aggiornata: il vincolo "nessuna pubblicazione automatica" resta
valido per il **loop**; B e C sono azioni manuali assistite, fuori dal loop,
con conferma umana di default.

## 8. Ordine di lavoro

| # | Cosa | Stima |
|---|------|-------|
| 1 | Backend: app `leads`, modello, bulk-upsert, API FE, test | ½ giornata |
| 2 | Bot: `api_push.py`, colonne SQLite, push nel loop | 2 h |
| 3 | Pagina `/p/leads` + voce menu | ½ giornata |
| 4 | Condivisione assistita in galleria (7.A) | 1 h |
| 5 | Multi-gruppo (config lista + loop + campo gruppo) | 1–2 h |
| 6 | `bot bump` (7.B), poi eventualmente `bot pubblica` (7.C) | ½ giornata |

1–3 sono il cuore e vanno insieme (senza pagina il push non serve a niente);
4 è indipendente e immediato; 5 quando spunta un secondo gruppo utile;
6 per ultimo, quando il resto gira.
