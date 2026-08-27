# Bot di monitoraggio gruppo Facebook affitti — Monza/Brianza

## Contesto e natura del progetto

**Non è un servizio, è uno strumento da campagna.** Ci sono 5 stanze in gestione; in questo
momento 3 sono libere. L'obiettivo è riempirle in una decina di giorni, dopodiché il bot
va in cantina per mesi, fino alla prossima finestra di sfitto.

Questo detta tutte le scelte tecniche che seguono: si ottimizza per **tempo di scrittura
basso** e **tempo di riattivazione basso**, non per robustezza a lungo termine. Un
componente che si rompe dopo sei mesi di inattività non è un bug: è il comportamento
atteso, e va messo in conto un'ora di sistemazione all'inizio di ogni campagna.

Corollari: niente systemd, niente job di retention, niente monitoraggio, nessun requisito
di sessione persistente per settimane.

## Obiettivo

Automatizzare la parte di **lettura e filtraggio** del gruppo, per individuare rapidamente
i post di chi cerca una stanza in zona Monza e ricevere una notifica con il messaggio di
risposta già pronto.

Oggi il lavoro è manuale: ~2 ore di scroll per ~10 contatti utili, con il filtro che si
allenta a fine serata (finisce che si scrive anche a chi cerca monolocali). Il tasso di
risposta sui contatti pertinenti è ~25%: il canale funziona, il collo di bottiglia è
**trovare i post**.

Target: da ~12 minuti a lead a ~15 secondi a lead.

## Non obiettivi (vincoli duri)

- **Nessun invio automatico di messaggi.** Il bot notifica e prepara il testo; l'invio
  resta un'azione manuale su Messenger. È il vincolo che tiene il progetto fuori dai
  pattern antispam di Meta e dai ban di gruppo.
- **Nessuna pubblicazione automatica** di post o commenti.
- **Nessuna anagrafica.** I dati dei post servono solo a deduplicare entro la campagna.
  A campagna chiusa si cancella il database, punto.
- Nessun uso di API Meta: la Groups API è stata rimossa nell'aprile 2024, non esiste una
  via ufficiale. Si opera dentro la propria sessione browser autenticata.

## Stack

- Python 3.12+, dipendenze con `uv`
- **agent-browser** per il pilotaggio del browser (già in uso, CLI Rust + daemon Node
  sopra Playwright). Non serve scendere a Playwright diretto: è lo stesso motore.
- SQLite per lo stato di campagna (dedup)
- Anthropic SDK per classificazione e composizione
- Pydantic per l'output strutturato
- Telegram Bot API (`httpx`) per le notifiche

## Architettura

Loop di polling in un singolo processo. Quattro stadi:

```
scraper → classifier → composer → notifier
             ↓
          SQLite (dedup di campagna)
```

### 1. Scraper (agent-browser)

- Sessione agent-browser dedicata (`--session affitti`) per isolare cookie e auth.
  Login manuale all'inizio della campagna; **non** si assume che sopravviva ai mesi di
  cantina — rifare il login è parte della checklist di riattivazione.
- **Headless di default.** Il Chrome headless moderno è sufficientemente vicino a quello
  headed, e i segnali che fanno scattare i checkpoint di Facebook sono altri (cambio IP o
  geolocalizzazione, ritmo delle *azioni*, fingerprint di dispositivo nuovo). Uno scroll in
  sola lettura ogni 25 minuti da IP residenziale stabile è un profilo tranquillo.
  Tenere comunque un flag `headed = false` in configurazione, da ribaltare se compaiono
  checkpoint.
- URL con ordinamento cronologico obbligatorio:
  `https://www.facebook.com/groups/{GROUP_ID}?sorting_setting=CHRONOLOGICAL`
  Senza questo parametro Facebook ripropone i post "rilevanti" e i nuovi si perdono.
- Scroll incrementale finché non si incontrano N post consecutivi già visti (default 10).
- **Estrazione via `agent-browser eval`, non via `snapshot`.** Lo snapshot ad accessibility
  tree è progettato per far risparmiare contesto a un agente: filtra, compatta, privilegia
  gli elementi interattivi. Qui serve il contrario, cioè il testo integrale di ogni post.
  Con `eval` si esegue il JS di estrazione e torna JSON pulito, senza dipendere dai ref
  `@eN` (effimeri per snapshot, adatti a un loop agentico ma non a uno script
  deterministico).

  JS di estrazione, ancorato a `div[role="article"]` (ruolo ARIA, molto più stabile delle
  classi CSS che Facebook offusca e rigenera):

  ```js
  [...document.querySelectorAll('div[role="article"]')].map(a => ({
    text: a.innerText,
    permalink: a.querySelector('a[href*="/posts/"]')?.href ?? null,
    author: a.querySelector('h3 a, strong a')?.innerText ?? null,
    authorUrl: a.querySelector('h3 a, strong a')?.href ?? null,
  }))
  ```

- `post_id` per la dedup si ricava dal permalink (`/groups/{gid}/posts/{pid}/`).
- Se in un giro non si trova nessun `div[role="article"]`, non fallire in silenzio:
  notificare su Telegram che il markup è probabilmente cambiato.

### 2. Classifier

Una chiamata LLM per post, output strutturato:

```python
class PostAnalysis(BaseModel):
    intent: Literal["cerca", "offre", "altro"]
    tipo_immobile: Literal[
        "stanza_singola", "stanza_doppia", "posto_letto",
        "monolocale", "bilocale", "appartamento", "non_specificato"
    ]
    zona: str | None
    budget_max: int | None
    disponibile_da: str | None
    durata: str | None
    match: bool
    stanze_compatibili: list[str]   # id delle stanze libere che reggono i vincoli
    motivo: str
```

Regole di matching, esplicite nel prompt:

- `match = true` solo se `intent == "cerca"` **e** `tipo_immobile` è stanza/posto letto
- escludere monolocali, bilocali, appartamenti interi
- escludere zone incompatibili (raggio configurabile intorno a Monza)
- se il post dichiara un budget massimo, includere in `stanze_compatibili` solo le stanze
  libere entro quel budget; se nessuna regge, `match = false` con motivo esplicito
- in caso di ambiguità → `match = true`, con `motivo` che segnala il dubbio: meglio una
  notifica da scartare che un lead perso

Il prompt riceve **l'elenco delle stanze attualmente libere** da configurazione, non una
singola offerta.

### 3. Composer

Per i post con `match = true`, genera il messaggio adattato al singolo annuncio,
proponendo la stanza (o le stanze) in `stanze_compatibili`.

Vincoli sul prompt:

- non inventare **nessun** dettaglio non presente in configurazione (prezzo, metratura,
  spese, servizi): allucinare qui significa mentire a un potenziale inquilino
- se le stanze compatibili sono più di una, citarne al massimo due, la più adatta per prima
- massimo 4-5 righe, tono diretto, niente formule commerciali
- chiudere sempre con link al post FB dell'offerta + cellulare, da configurazione

### 4. Notifier

Un messaggio Telegram per match:

- estratto del post (~300 caratteri)
- campi estratti (zona, budget, data) e stanze compatibili
- link al permalink
- messaggio proposto in blocco **monospace** (` ``` `): il tap su un blocco di codice
  copia il testo. Flusso: tap → apri post → incolla → invia.

## Schema dati

```sql
CREATE TABLE posts (
    post_id      TEXT PRIMARY KEY,
    author_name  TEXT,
    author_url   TEXT,
    text         TEXT,
    permalink    TEXT,
    seen_at      TIMESTAMP NOT NULL,
    analysis     TEXT,      -- JSON di PostAnalysis
    matched      BOOLEAN,
    notified_at  TIMESTAMP
);
CREATE INDEX idx_author ON posts(author_url);
```

- Dedup primaria su `post_id`, secondaria su `author_url` (evita di riscrivere a chi
  ripubblica lo stesso annuncio a distanza di giorni).
- Nessun job di purge: a fine campagna si cancella il file `.db`. Va messo in `.hgignore`.

## Gestione delle stanze

Le stanze libere stanno in configurazione. Quando una si affitta va tolta dal giro
**subito**, altrimenti il composer continua a proporla.

Meccanismo minimo: campo `libera = true/false` nel TOML, e la configurazione viene riletta
a ogni giro del loop (non caricata una volta all'avvio). Così basta editare il file e
salvare, senza riavviare niente. Se tutte le stanze risultano occupate, il bot logga e
va in pausa invece di notificare.

## Configurazione

File TOML unico, fuori dal repo, riletto a ogni ciclo:

```toml
[facebook]
group_id = "..."
poll_interval_minutes = 25
active_hours = [8, 23]
scroll_stop_after_seen = 10
headed = false
session = "affitti"

[[stanze]]
id = "palestrina-a"
libera = true
tipo = "singola"
prezzo = 0
disponibile_da = "..."
note = "..."

[[stanze]]
id = "palestrina-b"
libera = true
# ...

[contatto]
link_post_fb = "https://..."
cellulare = "..."

[matching]
zone_accettate = ["Monza", "Villasanta", "Brugherio", "..."]
escludi_tipologie = ["monolocale", "bilocale", "appartamento"]

[telegram]
bot_token = "..."
chat_id = "..."
```

## Esecuzione

**Deve girare su hardware domestico** (mini PC, Raspberry, NAS), uscendo dall'IP di casa.
La sessione Facebook esce abitualmente da un IP residenziale della zona: se comincia a
fare richieste da un datacenter, scatta un checkpoint di sicurezza e si finisce a rifare
login e verifiche a ogni giro. Questo vincolo resta valido anche in headless.

Per una campagna di dieci giorni non serve altro che un loop in un `tmux`:

```bash
while true; do
  uv run python -m bot.main --once
  sleep $((1200 + RANDOM % 600))   # 20-30 min con jitter
done
```

Niente systemd, niente unit da mantenere. Log su stdout, catturato da tmux.

## Criteri di completamento v1

Obiettivo realistico: mezza giornata di scrittura.

1. Login manuale nella sessione agent-browser, un giro che estrae i post correttamente
2. Dedup funzionante: il secondo giro non ripropone nulla del primo
3. Classificazione che scarta monolocali e post di chi offre
4. Matching sul budget che propone solo stanze compatibili
5. Notifica Telegram con messaggio copiabile in un tap
6. Nessuna funzione di invio automatico presente nel codice, nemmeno disattivata

## Checklist di riattivazione (per la prossima campagna, fra mesi)

Da eseguire in quest'ordine, prima di far girare il loop:

1. Aggiornare `[[stanze]]` con quelle effettivamente libere
2. Rifare login nella sessione agent-browser (assumere che sia scaduta)
3. Cancellare il vecchio `.db`
4. Verificare che `agent-browser eval` restituisca ancora post non vuoti — è il punto che
   si rompe per primo. Se il markup di Facebook è cambiato, l'unica cosa da sistemare
   dovrebbe essere il JS di estrazione, che per questo va tenuto **isolato in un solo
   modulo, ben commentato**.
5. Un giro a secco con le notifiche attive ma senza contattare nessuno, per controllare
   che la classificazione sia ancora sensata

Se il punto 4 richiede più di un'ora, valutare se conviene ancora rispetto al manuale.

## Note di manutenzione

Il punto fragile è il markup di Facebook, ed è l'unico. La scelta di estrarre `innerText`
grezzo e delegare tutto il resto all'LLM serve a ridurre la superficie di rottura: quando
si rompe, si rompe la *selezione dei contenitori*, non l'interpretazione dei dati.
Tenere il selettore in un unico punto, isolato e documentato.

Secondo punto di attenzione, minore: agent-browser è giovane e si muove in fretta. Fra una
campagna e l'altra è probabile che sia cambiato qualcosa nel CLI. Fissare la versione nel
progetto e annotarla, così alla riattivazione si sa da dove si riparte.
