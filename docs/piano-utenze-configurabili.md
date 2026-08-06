# Piano: utenze configurabili per immobile ("cosa ci sarà")

> Obiettivo: dichiarare **nella configurazione della casa** quali utenze esistono
> e chi le gestisce — es. la TARI c'è nella casa a stanze ma nell'appartamento è
> una questione dell'inquilino; l'acqua c'è nell'appartamento ma non è gestita
> nella casa a stanze. Da questa dichiarazione derivano la completezza del
> periodo, gli slot "mancante" del wizard e (in fase 2) le voci che entrano
> nella ripartizione.
>
> Documento di piano, non di implementazione. Scritto 2026-08-06.

## 0. Stato attuale (perché serve)

- La completezza è **hardcoded**: `_completezza` in `billing/views.py` richiede
  luce AND gas per ogni immobile, sempre; la TARI è mostrata ma non bloccante.
  Il frontend ha `attese: 3` fisso (`ProprietarioUtenze.vue`) e gli slot
  Luce/Gas/TARI cablati (`BollettaStep.vue`, `TIPI_UTENZA` in `format.ts`).
- Le voci ripartibili sono **globali**: `VOCI_FATTURABILI = ("luce", "gas")` in
  `billing/calc/utility.py:11`. `Prodotto.ACQUA` esiste nei choices ma una
  bolletta acqua **non entra mai** nel calcolo.
- Caso reale (2026-08-06): viapal (a stanze) = luce+gas+TARI gestite dalla
  proprietà; viapessi (appartamento, unità intera) = TARI intestata
  all'inquilino, e la bolletta **acqua** (Magis) è oggi registrata come
  `prodotto=gas` — è proprio questo che la fa entrare nel calcolo.
- Il "Procedi comunque" (ripartizione parziale forzata, feature 2026-08-06)
  copre bene gli **imprevisti** (bolletta in ritardo, cadenza bimestrale), ma
  l'assenza **strutturale** di una voce non dovrebbe richiedere una forzatura
  ogni mese: è configurazione, non eccezione.

## 1. Concetto

Per ogni immobile, per ogni voce (luce, gas, acqua, TARI) si dichiara una di:

| Gestione | Significato | Effetto |
|---|---|---|
| **Proprietà** | La proprietà riceve la bolletta e la ripartisce | La voce è **attesa**: concorre alla completezza e (voci a bolletta) alla ripartizione |
| **Inquilino** | Intestata/pagata direttamente dall'inquilino | Fuori dal flusso; documentata (nota informativa, in prospettiva anche lato inquilino) |
| *(nessuna riga)* | La voce non esiste per questa casa | Semplicemente non compare da nessuna parte |

## 2. Modello dati

`PropertyUtilityService` (app `billing`, accanto a `Supplier` e
`AnnualUtilityCost`):

- `property` FK → Property
- `voce` — choices condivise `luce | gas | acqua | tari`
- `gestione` — choices `proprieta | inquilino`
- `cadenza_attesa` — opzionale (`mensile | bimestrale | trimestrale | ...`),
  **solo informativa in v1** (vedi fase 3)
- `note` — es. "TARI intestata a Mehmet, la paga al Comune"
- unique `(property, voce)`

Perché righe e non booleani su `Property`: estensibile (nuove voci senza
migrazioni di schema), spazio per cadenza/note, admin inline naturale.

**Seed (data migration)**: per ogni Property esistente → `luce` e `gas` =
proprietà; `tari` = proprietà se esiste almeno un `AnnualUtilityCost` di quella
property. Poi a mano: viapessi → tari = inquilino (+ in fase 2: acqua =
proprietà).

**Fallback nel codice**: property senza alcuna riga → comportamento attuale
(attese luce+gas). Così fixture e test esistenti restano verdi e un immobile
nuovo funziona subito.

## 3. Backend

1. **Completezza dinamica** — `_completezza(period)`: le attese sono le voci
   `gestione=proprieta`; per le voci a bolletta (luce/gas/acqua) "presente" =
   bolletta in overlap col periodo, per la TARI = `AnnualUtilityCost` attivo
   (come oggi). `completo` = tutte le attese **a bolletta** presenti (la TARI
   annuale resta non bloccante). La response mantiene le chiavi attuali
   (`luce/gas/tari/completo`) e aggiunge `attese: ["luce", "gas", ...]` +
   eventuale `acqua`, così la UI diventa data-driven senza rompere nulla.
2. **Voci fatturabili per property** (fase 2) — `_attribuisci_bollette` filtra
   `prodotto__in` sulle voci a bolletta gestite dalla proprietà invece che su
   `VOCI_FATTURABILI` globale (che resta come fallback). Da qui l'acqua entra
   nella ripartizione dove configurata; i totali finiscono in `tot_altro`
   (nessuna migrazione necessaria; `tot_acqua` dedicato è opzionale).
3. **TARI = inquilino** — se configurata così ma esistono `AnnualUtilityCost`
   per la property: la voce non entra nel calcolo e l'admin segnala
   l'incoerenza (check/warning, non blocco).
4. **API** — CRUD `/api/v1/utenze-config/` filtrato per property di contesto,
   sul pattern di `/quote-condominio/`; lettura per tutti i membri, scrittura
   per i proprietari (stesse regole della membership).
5. **Etichette avvisi** — `VOCI_LABEL`/`VOCI_ORDINE` in `calc/avvisi.py:80` si
   estendono con `acqua`; i testi fissi che citano "luce, gas e TARI" derivano
   l'elenco dalle voci reali del dettaglio (altrimenti una voce nuova sparisce
   in silenzio dall'email).
6. **Serializer** — mappa prodotto→tipo fornitore (`serializers.py` ~288):
   aggiunta `acqua`.

## 4. Frontend

1. **Wizard data-driven** — slot "mancante", contatore `presenti/attese`,
   `mancantiTipi` e badge "N mancanti" derivati da `completezza.attese` del
   backend invece dei valori cablati. Il "Procedi comunque" resta, ma serve
   solo per gli imprevisti.
2. **Config UI** — pannello "Utenze della casa" nel tab `spese` di
   `/p/impostazioni` (dove già vivono fornitori e quote condominio;
   alternativa: tab dedicato — decisione aperta). Una riga per voce con select
   Proprietà / Inquilino / Non presente + note; il tab `tari` esistente resta
   per gli importi (`AnnualUtilityCost`).
3. **Acqua a pieno titolo** (fase 2) — icona goccia in `icons.ts`, entry
   `Acqua` in `UTILITY` (`format.ts`), `prodottoToTipo`, `ORDINE_VOCI` e la
   mappa `per: {Luce, Gas, TARI}` in `ProprietarioUtenze.vue` +
   `InquilinoUtenze.vue`. Il tab riepilogo "Bollette" è già pronto (colonne
   dai dati, ordinamento include già `acqua`).
4. **Lato inquilino** (nice-to-have, fase 3) — in `/i/utenze` nota "La TARI è
   intestata a te: la paghi direttamente al Comune" quando configurata
   `inquilino`.

## 5. Fasi

- **Fase 1 — configurazione e completezza.** Modello + seed + completezza
  dinamica + wizard data-driven + pannello config. Risultato: viapessi non
  mostra più la TARI tra le mancanti e non chiede forzature per assenze
  strutturali. Il **calcolo non cambia**.
- **Fase 2 — acqua di dominio.** Voci fatturabili per property + etichette
  email/UI + icona. Solo a questo punto la bolletta Magis si riclassifica
  `gas → acqua` (prima no: sparirebbe dal calcolo) e serve il template parser
  per il fornitore d'acqua.
- **Fase 2b — conguagli retroattivi.** Attribuzione v3 day-based con guardia
  temporale (sezione 8).
- **Fase 3 — rifiniture.** Warning incoerenze admin, nota lato inquilino,
  serie acqua nell'Andamento. (La cadenza attesa è stata scartata: si legge
  dalla bolletta, e per i mesi scoperti resta il "Procedi comunque".)

## 6. Decisioni prese (Sandro, 2026-08-06)

1. **Collocazione UI**: dentro il tab `spese`.
2. **Permessi**: anche i **gestori** possono modificare la configurazione
   (non solo i proprietari).
3. **Fase 2 subito.** Attenzione: in un appartamento è normale che anche luce
   e gas siano intestate all'inquilino → **nessuna voce è obbligatoria**;
   luce/gas = proprietà è solo il default del seed, sempre modificabile.
4. **Niente cadenza attesa** (si legge dalla bolletta); il "Procedi comunque"
   resta per i mesi scoperti. In compenso serve la gestione dei **conguagli
   retroattivi** (sezione 8): un conguaglio che riprende mesi già addebitati
   non può andare perso.

## 8. Conguagli retroattivi (caso Edison)

Requisito (Sandro): se l'addebito di aprile è già stato emesso e a luglio
arriva un conguaglio che copre anche aprile, quell'importo **non può andare
perso**: va imputato tutto al primo mese dopo l'ultimo addebito creato.
Edison lo faceva *spesso*.

Stato attuale: dopo il redesign 2026-05-31 ("ogni bolletta ha il suo periodo",
niente ribaltamento) la quota che cade su mesi già emessi semplicemente non
viene addebitata a nessuno. C'è anche un difetto latente collegato: una
bolletta a cavallo di due mesi viene **pinnata per intero** dal primo periodo
che si emette (`consumed_ids` in `_attribuisci_bollette`) e quindi esclusa
dall'altro mese, la cui quota pro-rata va persa se i periodi non si emettono
nell'ordine giusto.

### Algoritmo di attribuzione v3 (day-based)

Per un periodo P in bozza, per ogni bolletta B:

1. **Quota propria**: pro-rata sui giorni di `B ∩ P` (come oggi).
2. **Giorni già coperti**: i giorni di B che cadono in periodi `inviato` non
   si contano mai come quota propria di P (sono congelati lì).
3. **Quota retroattiva**: i giorni di B che cadono in periodi `inviato` che
   NON hanno pinnato B **e** la cui emissione è precedente al caricamento
   della bolletta (`B.created > E.data_invio` — la guardia temporale) si
   ribaltano **tutti sul periodo target** = il primo periodo non emesso dopo
   la fine dell'ultimo periodo `inviato` della property. Se P è il target,
   P se li prende.
4. L'esclusione binaria `consumed_ids` viene sostituita dal conteggio per
   giorni: una bolletta pinnata da un periodo inviato resta conteggiabile
   negli altri mesi che copre (fix del difetto latente).
5. La modalità pinning manuale (M2M popolata a mano su un periodo) resta
   "verità manuale" e ha la precedenza, come oggi.

La **guardia temporale** è ciò che evita di resuscitare il bug "992 €"
(2026-05-31): le bollette storiche importate *prima* dell'emissione dei loro
periodi non ribaltano nulla; ribalta solo ciò che è arrivato *dopo* che il suo
mese era già stato addebitato (il conguaglio Edison).

Trasparenza: l'anteprima espone le quote retroattive (`arretrati`: bolletta,
periodo coperto, importo) e la UI le mostra nel passo Ripartizione, così il
totale "gonfiato" del mese target è spiegato.

Verifiche chiave nei test: somma delle quote sui periodi = importo ripartibile
della bolletta in ogni ordine di emissione; conguaglio retro → tutto sul
target; import storico → nessun ribaltamento; bolletta bimestrale emessa in
ordine inverso → nessuna perdita.

## 7. Impatti e rischi

- **Test esistenti**: verdi grazie al fallback (property senza config →
  luce+gas come oggi).
- **Periodi già emessi**: nessun ricalcolo retroattivo; pinning e guardia
  allocations invariati.
- **Riclassificazione Magis** (gas→acqua): solo dopo la fase 2 e con il
  periodo di giugno viapessi non ancora emesso, altrimenti la voce cambia nome
  tra addebito e bolletta.
- **Multiproprietà**: il modello è per-property by design, coerente con
  `docs/piano-multiproprieta.md`.
