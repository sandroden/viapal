# Viapal — Piano di sviluppo

> Gestionale (PWA) per l'affitto a stanze di un appartamento di 180 m² in Via Palestrina (Monza), gestito dai 3 fratelli proprietari (Sandro, Bruna, Fabio). Sostituisce la gestione attuale frammentata (Google Docs + foglio Excel + bonifici + ricevute via WhatsApp).
>
> Documento di riferimento per qualsiasi sessione di lavoro futura. Le decisioni di prodotto vivono qui; le decisioni operative correnti vivono nella memoria persistente Claude (`~/.claude/projects/-home-sandro-src-siti-sandro-viapal/memory/`).

## 1. Cos'è Viapal

Una PWA che permette di gestire affitti, bollette, conguagli, spese e contabilità interna tra fratelli per un appartamento con 5 stanze affittate singolarmente sotto un **contratto unico** (asseverato, cedolare 10% — Monza ha contratti concordati/calmierati).

Tre cose che deve fare meglio del foglio Excel:
1. Mostrare a colpo d'occhio chi ha pagato cosa, e chi è in ritardo
2. Far dichiarare il pagamento direttamente all'inquilino dal cellulare ("Ho pagato")
3. Calcolare e inviare i 5 conguagli mensili in pochi click

Viapal **non** è un gestionale immobiliare professionale. È uno strumento familiare per una situazione specifica con regole specifiche. Tono e identità visiva esplicitamente "domestico/familiare" (direzione "Materica"), non "gestionale aziendale".

## 2. Utenti e ruoli

### Proprietari (3)
- **Sandro Dentella** — sviluppatore, gestisce la parte tecnica e operativa
- **Bruna** — sorella, gestione operativa principale (paga F24, riceve gran parte dei bonifici, anticipa spese, paga IMU/cedolare anche di Fabio)
- **Fabio** — fratello, vive in barca, **non partecipa attivamente** alla gestione. Ha debiti pregressi verso Sandro e Bruna. Possibile uscita dalla proprietà in futuro.

### Inquilini (5 attuali)
Mariasevera, Davide, Diana, Arun, Eshani. Anche stranieri ma di permanenza stabile e italofoni.

### Ruoli applicativi
- `proprietari` — gruppo Django, accesso area `/p/*`, dashboard, configurazione, conti
- `inquilini` — gruppo Django, accesso area `/i/*`, vede solo i propri dati
- (eventuale `commercialista` come read-only futuro)

## 3. Decisioni di dominio (le regole non ovvie)

### Quote di proprietà versionate
Oggi 1/3 ognuno. Quando Fabio cederà la quota, le quote cambieranno. Modello: `OwnershipShare(owner, valid_from, valid_to, quota)`. La somma deve fare 1.0 in ogni momento (vincolo di `clean()`).

### Contratto unico, cessioni come gap di assignment
Esiste un solo `Contract` (settembre 2024, asseverato 10%). I subentri inquilini **non sono nuovi contratti**, sono **cessioni** legalmente registrate presso AdE. Modello: chiusura di `RoomAssignment` uscente + apertura nuovo `RoomAssignment` per stessa stanza, con `data_atto_cessione` valorizzata. Possono esserci gap = settimane di stanza vuota (rare, <2 sett/anno per max 1-2 stanze).

### TARI come costo annuale spalmato
TARI ~€510/anno pagata da Sandro/Bruna con F24. **Non arriva come bolletta**. Modellata come `AnnualUtilityCost(voce='TARI', anno, importo, valid_from, valid_to)`. Ogni `UtilityChargePeriod` la include come quota proporzionale: `importo × giorni_periodo / 365`. Trattata esattamente come luce/gas, ripartita pro-rata sui giorni di presenza. Si inserisce **una sola volta all'anno** (al pagamento F24).

### Pro-rata-giorni come unico criterio in pratica
Il modello permette `a_testa | per_stanza | pro_rata_giorni`, ma in pratica si usa **sempre `pro_rata_giorni`**. Formula:

```
costo_giorno_persona = totale_periodo / Σ(giorni_presenza_di_tutti_gli_inquilini_nel_periodo)
quota_inquilino = costo_giorno_persona × giorni_presenza_dell_inquilino
```

Default in tutti i form, mai cambiato. Lascio gli altri criteri configurabili per non chiudere porte.

### Bollette luce/gas: niente pro-rata fra mesi
Bolletta a cavallo (es. 15 mar - 15 apr) viene caricata interamente sul mese principale (default = mese di scadenza, modificabile manualmente). "Smoothing statistico" — chi è penalizzato un mese sarà avvantaggiato un altro. Convenzione esplicitamente accettata.

### Pagamenti di aggiustamento all'ingresso/uscita
Quando un inquilino entra o esce a metà mese, il wizard offre due scelte:
- (a) pagare ogni mese il giorno di ingresso (mesi sempre interi)
- (b) allinearsi al giorno standard del mese (es. 1) con un primo pagamento parziale `canone × giorni / giorni_nel_mese`

`RentPayment` ha periodo esplicito `competenza_da/a` per gestirlo. Speculare in uscita (rimborso pro-rata via `ExtraCharge` negativo o decurtato dalla cauzione).

Convenzione pro-rata: **giorni effettivi del mese di calendario** (luglio=31, febbraio=28).

### Cauzione: restituita e re-incassata
Alla cessione, la cauzione del cedente gli viene restituita e una nuova viene incassata dal cessionario. NO trasferimento "a caldo". Campi `deposito_versato`, `deposito_restituito`, `data_restituzione_deposito` su `RoomAssignment`.

### Solleciti configurabili
Modello `ReminderRule(applicabile_a, giorni_offset, canale, destinatario, template)`. Default:

**Affitto** (scadenza legale = `giorno_pagamento + 5gg`):
- Promemoria pre-scadenza: -1 giorno
- 1° sollecito morbido: +2 giorni
- 2° sollecito: +9 giorni (push + email)
- 3° sollecito + escalation owner: +15 giorni

**Conguagli utenze** (scadenza = `data_invio + 5gg`):
- Notifica all'invio: 0
- Promemoria: +5 giorni
- 1° sollecito: +10 giorni
- 2° sollecito + escalation: +20 giorni

**Quiet hours 22-8**: push notturne accodate alla mattina. Niente throttling/dedup (volumi bassi non lo richiedono — ~10 pagamenti/mese).

### IBAN a turno
I bonifici inquilini arrivano sul conto di un solo fratello per volta (prevalenza Bruna). Modello `OwnerBankAccount` + campi `incassato_da_owner`, `bank_account_destinazione` su `RentPayment` e `UtilityCharge`. Generano `OwnerLedgerEntry` per quel fratello specifico, che il modulo "Conti tra fratelli" usa per calcolare i giroconti di pareggio.

### Due livelli contabili
**Livello A — "Ufficiale Viapal"**: incassi affitti, spese immobile, ripartizione per quote attive, distribuzione utili. Trasparente, esportabile per commercialista.

**Livello B — "Partitario bilaterale"**: prestiti personali tra fratelli, anticipi su quote IMU/cedolare di Fabio (Bruna paga per lui), trattenute concordate (€100/mese che Bruna trattiene su distribuzione a Fabio per restituire debiti). **Pagina dedicata per ogni coppia** (Bruna↔Fabio, Sandro↔Fabio).

I due livelli si parlano in 2 punti di contatto:
1. `Expense` con `riferimento_quota_owner` valorizzato → entry automatica nel partitario (es. "Bruna paga IMU di Fabio €450" → debito di Fabio +€450)
2. `WithholdingRule` attiva → trattenuta automatica sui giroconti (es. distribuzione di €800 da Bruna a Fabio → bonifico effettivo €700 + entry restituzione €100 nel partitario)

## 4. Modello dati

### Persone & quote
- `User` — auth Django
- `OwnerProfile` (3) — codice fiscale, IBAN personali, contatti
- `OwnershipShare` — quota versionata `(owner, valid_from, valid_to, quota)`
- `TenantProfile` (N attuali + storici) — anagrafica, contatti, `giorno_pagamento_affitto`, `frequenza_conguagli`, `note_pagamento`

### Immobile, contratto, occupazione
- `Room` (5) — anagrafica stanze (nome, superficie, foto)
- `Contract` (1) — il contratto unico, asseverazione, cedolare 10%
- `RoomAssignment` — periodo di occupazione di una stanza, `valid_from/valid_to`, `canone_mensile`, `deposito_versato/restituito`, `data_atto_cessione`

### Pagamenti affitti & bancario
- `RentPayment` — periodo esplicito `competenza_da/a`, `is_aggiustamento`, importo dovuto/pagato, stato, ricevuta opzionale, `incassato_da_owner`, `bank_account_destinazione`
- `OwnerBankAccount` — IBAN per ricevere
- `BankTransaction` — riga estratto conto importata, link a payment riconciliato

### Bollette e conguagli
- `UtilityBill` — bolletta del fornitore (luce, gas, ecc.) con periodo specifico, file PDF, `pagata_da_owner`
- `AnnualUtilityCost` — TARI o simili (costo annuale spalmato pro-rata-giorni)
- `UtilityChargePeriod` — periodo conguaglio (mensile o bimestrale), criterio ripartizione, stato `bozza|inviato`, eventuali `manual_totals` per import storico
- `UtilityCharge` — conguaglio per UN inquilino in UN periodo (importo totale, scadenza, stato, riconciliazione)
- `UtilityChargeLine` — riga di dettaglio (luce €27 + gas €22 + TARI €9), per trasparenza in PWA inquilino

### Spese e contabilità
- `ExpenseCategory` — manutenzione, IMU, TARI, condominio_ord, condominio_straord, assicurazione, ecc.
- `Expense` — `category`, importo, fornitore, `anticipata_da_owner`, `riferimento_quota_owner` (opzionale, attiva il flusso bilaterale), `ripartibile_su_inquilini`
- `ExtraCharge` — addebito/accredito una-tantum (es. conguaglio condominiale annuale, danno, rimborso). Importo signed (può essere negativo)
- `Supplier` — anagrafica fornitori
- `OwnerLedgerEntry` — partitario ufficiale tra fratelli (incassi, anticipi, distribuzioni)
- `OwnerSettlement` — chiusura periodica conti

### Partitario personale fratelli
- `InterOwnerLoan` — prestito personale aperto
- `InterOwnerEntry` — voce ledger bilaterale (coppia ordinata di owner, signed)
- `WithholdingRule` — regola di trattenuta automatica su distribuzioni

### Documenti
- `Document` — generico, con cartelle (path semplice) e tags

### Notifiche
- `PushSubscription` — registrazione device PWA (VAPID endpoint)
- `Notification` — log push inviate
- `MessageTemplate`, `ReminderRule` — solleciti configurabili

## 5. Stack tecnico e architettura

### Backend
- **Django 5.2** + Python 3.13
- **Package manager: `uv`** (no pip/poetry). Anche per virtualenv e dipendenze
- **Django REST Framework** per le API
- **PostgreSQL 16**
- **Redis + Celery** per task asincroni (solleciti, generazione PDF, OCR)
- **uwsgi** in produzione
- **Auth session-based** Django + dj-rest-auth (no JWT — Django non ha mai abbracciato JWT)
- **`jmb.jadmin`** per admin esteso (vedere convenzioni più avanti)
- **`jmb.filters`** per advanced-search dove utile
- **`thx.appy`** per generazione PDF (export commercialista, conguagli) via template ODT + Gotenberg
- **django-webpush** per notifiche push (VAPID)
- **Claude vision API** per OCR scontrini/ricevute (Fase 2)

### Frontend
- **Quasar 2** (Vue 3 Composition API + TypeScript strict)
- **Package manager: `bun`** (no npm/yarn/pnpm). Per dev server, build, install
- Vite, **Pinia**, Vue Router
- **PWA mode**: manifest, service worker, install prompt out-of-the-box
- vue-i18n (predisposto, solo italiano per ora)
- Design system in `design/project/tokens.css` da portare 1:1
- Logo PWA da `design/project/viapal-logo-intarsio.svg` (più 2 varianti da generare: maskable con padding 10%, monocroma silhouette per favicon ≤32px)

### Architettura applicativa
- **Un solo frontend Quasar**, due aree per ruolo:
  - `/p/*` proprietari (desktop-first, responsive su mobile)
  - `/i/*` inquilini (mobile-first, accessibile anche da desktop)
- Code-splitting per area: l'inquilino non scarica codice proprietari
- Login → redirect automatico in base al gruppo
- Permessi object-level (DRF permission classes + queryset filtering): inquilino vede solo i propri dati

### Repository
**Monorepo GitHub** (privato):

```
viapal/
├── PLAN.md                # questo file
├── README.md              # come avviare
├── design/                # bundle Claude Design (già presente)
├── backend/               # Django project (skill django-startproject)
├── frontend/              # Quasar project (skill quasar-startproject)
├── docker-compose.yml     # produzione
├── justfile               # comandi locali
└── .github/workflows/     # GitHub Actions
```

### Infrastruttura
- **Server Docker esistente** di Sandro (dominio reale da definire)
- **Traefik** come reverse proxy (HTTPS automatico)
- 2 immagini in produzione: `viapal-backend` (django+uwsgi), `viapal-frontend` (nginx serve build statico Quasar)
- Eventuale `gotenberg` se serve conversione ODT→PDF
- **CI/CD: GitHub Actions** (anche per testare integrazioni Claude su PR — `@claude` mentions, code review)
- **Dev locale: nessun docker** (postgres/redis come services di sistema, Django runserver/uwsgi nativo, Quasar dev server). Justfile per wrap comandi
- Riferimento monorepo: `~/src/siti/sandro/nicolas` (era GitLab, va riadattato)

### Database locale (già pronto)
- Cluster: **`dev`** PostgreSQL 16
- Host: `localhost`
- Porta: **`5434`**
- Database: **`viapal`**
- Utente: **`sandro`** (superuser)
- **TODO setup**: aggiungere riga in `~/.pgpass` (`localhost:5434:viapal:sandro:<password>`, chmod 600) oppure verificare `pg_hba.conf` del cluster dev per accesso `trust`/`peer`. Senza questo `psql -h localhost -p 5434 -U sandro -d viapal` chiede password.

## 6. Roadmap

### Fase 0 — Setup tecnico (~1 settimana)

**Obiettivo**: "hello world" deployato online, CI verde, login funzionante.

- Crea repo GitHub `viapal` (privato), monorepo
- Esegui skill `django-startproject` in `backend/`
- Esegui skill `quasar-startproject` in `frontend/`
- Adatta Dockerfile backend per build context monorepo (riferimento `nicolas`)
- Crea Dockerfile frontend (multi-stage node→nginx)
- `docker-compose.yml` produzione con label Traefik
- GitHub Actions: lint, test backend, build frontend, push immagini, deploy
- Setup ambiente locale (postgres systemd, redis systemd, .env)
- `justfile` con `just up`, `just test`, `just deploy`
- Primo deploy "hello world" sul server Docker
- Auth Django session + dj-rest-auth + endpoint `/api/auth/{login,logout,me}`
- Layout Quasar minimo + auth flow + redirect ruolo

**Criterio di "fatto"**: ti logghi su `https://viapal.tuodominio.it`, vedi pagina vuota giusta per il tuo ruolo, hai una PR mergeata via CI verde.

### Fase 1 — MVP funzionale (~5-6 settimane)

**Obiettivo**: sistema realmente usabile, lo affianchi al foglio Excel per qualche settimana, poi lo sostituisci.

**1.1 — Modello dati e admin** (settimana 1)
- Tutti i modelli Django con migrations
- Dati seed (te + Bruna + Fabio + 5 stanze + contratto + assignment correnti + AnnualUtilityCost TARI + RecurringUtilityCharge se restano altre voci fisse)
- **Admin Django con `jmb.jadmin` completo** (vedi convenzioni)
- DRF serializer + viewset + permission classes object-level

**1.2 — Calcolo conguagli e Quadro annuale** (settimana 2)
- Funzione `calcola_conguaglio_periodo(period_id)` (passaggi: bills + annuali + Σ presenze + quote)
- Wizard "Nuovo periodo conguagli"
- Inserimento `UtilityBill` con upload PDF
- **Vista "Quadro conguagli annuale"** (riproduce il foglio Excel, export CSV/PDF)
- Action "Genera conguagli e invia" — un click crea i 5 `UtilityCharge` + manda push

**1.3 — Pagamenti affitto, wizard inquilini, cessioni** (settimana 3)
- Wizard "Nuovo inquilino" con scelta giorno_pagamento + opzionale aggiustamento
- Generazione automatica mensile `RentPayment` (Celery beat task)
- Wizard "Cessione" (chiusura assignment + apertura nuovo + restituzione/incasso depositi)
- Vista "Pagamenti affitti" matrice mese × inquilino con semaforo
- Inserimento manuale RentPayment per casi rari (contanti)

**1.4 — Frontend inquilino** (settimana 4)
- Layout mobile-first
- Home "DA PAGARE / DA RICEVERE" con card colorate (codice semaforo Materica)
- Bottone "Ho pagato" → form con causale e importo precompilati, foto opzionale
- Vista "Pagamenti" storico personale
- Vista "Conguaglio" con dettaglio TARI + luce + gas
- Vista "Profilo" sola lettura
- Ricezione push notification

**1.5 — Frontend proprietario + Vista Ritardi** (settimana 5)
- Dashboard rendita: KPI annuali, grafico mensile, prossime scadenze
- **Vista "Ritardi"** con codice colore semaforo (verde/miele/argilla in scala di gravità)
- Approvazione "Ho pagato" da mobile owner (push → 1 tap conferma)
- Quick-add `Expense` da mobile (foto opzionale, no OCR)
- Vista anagrafica inquilini + scheda contratto

**1.6 — Import storico e validazione** (settimana 6)
- Management command `import_history`:
  - CSV foglio Excel → `UtilityChargePeriod` + `UtilityCharge` storici (stato `pagato_storico`)
  - PDF bollette → `UtilityBill` collegate
  - CSV estratto conto → `BankTransaction` + matching automatico contro `RentPayment` storici
- Report di validazione: "totale storico atteso vs registrato" per inquilino, con tolleranza configurabile (~€5 per arrotondamenti TARI)
- Setup notifiche push base (subscribe API + 2 trigger: "ho pagato" + "conguaglio inviato")

**Criterio di "fatto"**: tu fai un mese di doppio Excel/Viapal con discrepanze a zero (o spiegate), gli inquilini hanno tutti accesso PWA, generi un conguaglio in 30 secondi.

### Fase 2 — Automazioni (~3-4 settimane)

- Engine solleciti automatici (`ReminderRule` configurabili + Celery beat + quiet hours 22-8)
- Conti tra fratelli ufficiali (`OwnerLedgerEntry` automatici + UI saldo triangolare + proposta giroconti)
- Partitario bilaterale (Bruna↔Fabio, Sandro↔Fabio) con `WithholdingRule` automatica
- Documenti — area completa (cartelle, drag&drop, ricerca, anteprima)
- Migrazione iniziale Google Docs (Google Drive API)
- OCR Claude vision per scontrini/ricevute (skill `claude-api` con prompt caching)
- API documento per uso Claude Code da casa Sandro (`POST /api/expenses`, `POST /api/utility-bills`)

**Criterio di "fatto"**: tempo dedicato al gestionale < 1h/mese, gli inquilini smettono di chiamare per chiedere "quanto devo?"

### Fase 3 — Estensioni on-demand

Da fare quando emerge il bisogno reale, non per principio:
- Manutenzioni / ticket completi (oggi rapporto amichevole)
- Letture contatori con OCR foto (solo luce se decidete di iniziare)
- Promemoria proattivi (scadenze IMU, "manca bolletta da X")
- Dashboard pluriennale con confronti anno-su-anno
- Export commercialista strutturato (modello redditi quote)
- Open Banking PSD2 (solo se import CSV diventa fastidio)
- Chat fratelli/inquilini in app
- i18n se entrano inquilini stranieri non italofoni
- Sentry per error tracking server e PWA

## 7. Convenzioni di progetto

### Lingua
Tutto in italiano: UI, copy, log, descrizioni PR, commenti, identificatori se naturali. Nomi di modelli e classi Django in inglese (`OwnerProfile`, `RoomAssignment`), nomi di funzioni di dominio in italiano se più chiari (`calcola_conguaglio_periodo`, `genera_solleciti`).

### Design
**Materica** — toni terra/legno/salvia, tipografia umanista. Token in `design/project/tokens.css` da portare 1:1 nel frontend (variabili CSS). Logo `design/project/viapal-logo-intarsio.svg` (pappagallo nella casa, dall'intarsio del mobile reale dell'appartamento).

Tagline: **"Viapal — la casa, in tasca"**.

Tono copy: caldo e familiare. Esempio dalla chat di design: "Manca ancora la ricevuta di Marco". Mai legalese. Codice colore stato pagamenti:
- **Salvia** (verde) → tutto in regola
- **Miele** (giallo) → in scadenza nei prossimi 3-7 giorni
- **Argilla chiaro** (arancione) → ritardo 1-7 giorni
- **Argilla scuro** (rosso) → ritardo >7 giorni

### Admin Django
**Usare PIENAMENTE le feature di `jmb.jadmin`** — è una preferenza forte di Sandro per la leggibilità delle pagine admin:

- **Admin-tabs** (`AdminTabsMixin`) — organizzare i campi della change_form in tabs logiche. **Obbligatorio** per ogni model con più di 8-10 campi (`OwnerProfile`, `TenantProfile`, `RoomAssignment`, `Contract`, `Expense`, `UtilityChargePeriod`, ecc.). Le tabs raggruppano per affinità: "Anagrafica", "Contratto", "Pagamenti", "Documenti", ecc.
- **Ajax-inlines** (`AjaxInline`, `register_inline`) — per liste relazionate read-only con add/edit/delete in modal dialog. **Sostituire i classici `TabularInline`/`StackedInline`** che sono pesanti e poco leggibili. Es. nella scheda `RoomAssignment` un ajax-inline mostra i `RentPayment` collegati con possibilità di aprirli in modal.
- **Modal-edit** (`ModalEditMixin`) — per edit/delete in modal dalla changelist, evitando il viaggio alla change_form per modifiche piccole.
- Icone edit/delete (`get_edit_icon_iframe`, `get_delete_icon_iframe`) per UI pulita.

**`jmb.filters`** per advanced-search dove utile (`AdvancedSearchModelAdmin` con `advanced_search_fields`). Meno critico per il volume di Viapal, ma comodo su `RentPayment`, `BankTransaction`, `UtilityCharge`.

### Frontend
- **TypeScript strict**
- **Composition API** sempre (no Options API)
- **Pinia stores** per dominio (uno per Pagamenti, uno per Inquilini, ecc.)
- Componenti **Quasar nativi** prima di soluzioni custom
- Token CSS da `tokens.css`, non valori hard-coded
- Test manuale via skill `webapp-testing` quando serve

### Backend
- DRF generic viewset + permission classes object-level per "inquilino vede solo se stesso"
- Signal solo per side-effect evidenti (es. `Expense.save` con `riferimento_quota_owner` → genera `InterOwnerEntry`)
- Test pytest, focus su calcoli (formula pro-rata, generazione conguagli, matching bancario, distribuzione utili)
- Dipendenze gestite con `uv` (`uv add`, `uv sync`, `uv run pytest`)

### Validazione obbligatoria per ogni componente
Per ogni feature implementata, due livelli di verifica **non opzionali**:

1. **Test automatici** — pytest (backend), vitest se applicabile (frontend). Focus su calcoli e edge case (aggiustamenti pro-rata, periodi a cavallo, gap stanze vuote, distribuzione utili con quote versionate)
2. **Verifica funzionale via skill `agent-browser`** — apre il browser, naviga le pagine principali della feature, esegue il flusso utente (login, click, form submit), **salva screenshot** delle viste rilevanti per review

Gli screenshot vanno in `tests/screenshots/<feature>/<step>.png` e committati nel repo finché non si imposta storage esterno. Sono il modo principale per Sandro di verificare visualmente lo stato del lavoro fatto in autonomia.

### Stile di lavoro autonomo
- **Delegare agli agenti** il più possibile (scaffolding, implementazione moduli grandi, validazione browser) per tenere libero il contesto principale
- In sessioni autonome procedere senza chiedere conferma per ogni step. Riservare le domande solo per scelte irreversibili o input richiesti (credenziali, dominio reale, deploy in produzione, push GitHub iniziale)

### Git/PR
- Branch `feat/*`, `fix/*`, `chore/*`
- Commit semantici brevi, in italiano OK
- PR via GitHub, review con `@claude` mention
- `main` sempre deployabile, deploy automatico via Actions

## 8. Glossario

- **Assignment** (`RoomAssignment`) — periodo di occupazione di una stanza da parte di un inquilino sotto il contratto unico. Una stanza ha N assignment nel tempo.
- **Cessione** — passaggio di un inquilino a un altro per la stessa stanza, registrato presso AdE. Modellata come chiusura+apertura di assignment con `data_atto_cessione`.
- **Conguaglio** — addebito mensile (o bimestrale) per le utenze, somma di luce + gas + TARI ripartito pro-rata sui giorni di presenza.
- **Aggiustamento** — pagamento parziale (pro-rata) all'ingresso o all'uscita a metà mese.
- **Partitario bilaterale** — contabilità personale tra due fratelli, separata dai conti ufficiali Viapal.
- **Materica** — direzione visiva del design (terra/legno/salvia, Source Serif 4 + Geist).
- **Quadro conguagli annuale** — vista tabellare riepilogativa (1 riga per periodo, colonne per inquilino), erede del foglio Excel storico.
- **Vista Ritardi** — dashboard proprietari con elenco pagamenti scaduti, codice colore semaforo.
- **Trattenuta** (`WithholdingRule`) — meccanismo automatico di decurtazione su una distribuzione tra fratelli, applicato come restituzione di debito personale.

---

## Riferimenti

- **Bundle Claude Design** (sorgente design system): `design/`
  - `design/README.md` — istruzioni handoff
  - `design/chats/chat1.md` — trascrizione iter design
  - `design/project/Viapal.html` — canvas principale
  - `design/project/tokens.css` — design system completo
  - `design/project/viapal-logo-intarsio.svg` — logo finale
- **Memoria persistente Claude** (decisioni correnti): `~/.claude/projects/-home-sandro-src-siti-sandro-viapal/memory/MEMORY.md`
- **Foglio Excel storico** (sorgente import): da fornire
- **Riferimento monorepo Sandro**: `~/src/siti/sandro/nicolas` (struttura simile, era GitLab → va riadattata per GitHub)
- **Skill da usare**:
  - `django-startproject` — scaffolding backend
  - `quasar-startproject` — scaffolding frontend
  - `jmb:jmb-jadmin` — admin extension (vedi convenzioni admin)
  - `jmb:jmb-filters` — advanced-search admin
  - `thx:thx-appy` — generazione PDF da template ODT
  - `claude-api` — wrapper Anthropic SDK per OCR (Fase 2)
  - `agent-browser` — validazione funzionale + screenshot per ogni feature
  - `webapp-testing` — test manuale UI alternativo (Playwright)
  - `thx:thx-generate-django-tests` — generazione test caratterizzazione

### Ambiente verificato (2026-05-02)

| Tool | Versione | Stato |
|---|---|---|
| uv | 0.8.18 | ✓ |
| bun | 1.1.45 | ✓ |
| node (fallback) | v22.17.1 | ✓ |
| gh | 2.45.0 | ✓ autenticato come `sandroden` |
| docker | 29.3.1 | ✓ |
| just | 1.46.0 | ✓ |
| redis | OK | ✓ risponde PING |
| postgres | cluster `dev` :5434 | ⚠ richiede password — vedi sezione Database |

---

*Documento creato dopo una sessione di pianificazione approfondita (2026-04-29 → 2026-05-02). Prima di iniziare lo sviluppo, leggere questo file insieme a `MEMORY.md` per il contesto completo.*
