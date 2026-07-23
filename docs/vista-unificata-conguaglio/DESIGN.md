# Vista unificata "Conguaglio fratelli"

Design (non implementazione). Documento di architettura per una nuova vista del
gestionale viapal che colleghi i due piani contabili oggi separati (utile
pro-quota di competenza vs dare/avere di cassa) in un unico prospetto per anno e
per fratello.

Autore: analisi architetturale. Data: 2026-07-05.

---

## 1. Problema e gap

Oggi il fratello proprietario deve consultare **due pagine diverse** e fare la
sottrazione a mente:

- **`/p/conto-economico`** (`ProprietarioContoEconomico.vue`, blocco "Utile
  pro-quota") gli dice **quanto ha guadagnato** per competenza: `quota × utile
  immobile`. Alimentato da `ContoEconomicoView` (`dashboard_views.py:656`,
  `utile_pro_quota` righe 753-765).
- **`/p/saldi-fratelli`** (`ProprietarioSaldiFratelli.vue`) gli dice il
  **dare/avere di cassa** e il piano di rientro (chi bonifica cosa a chi).
  Alimentato da `OwnerLedgerEntryViewSet.saldi_live` (`accounting/views.py:100`)
  → `saldi_live.calcola_saldi_correnti` / `verifica_quadratura` /
  `calcola_piano_rientro`.

Manca il **ponte**: un prospetto unico che, per un dato anno, risponda alla
domanda finale «ho maturato X di utile, ne ho già incassati Y di mia mano,
quindi devo VERSARE / RICEVERE Z», e agganci Z al piano di bonifici concreto.

---

## 2. Il cuore analitico: conguaglio vs `saldi_live`

Questa è la parte più delicata del design. La formula proposta nel brief va
**corretta nel segno e nella base contabile**, altrimenti rompe lo zero-sum e
mescola cassa e competenza. Segue la derivazione.

### 2.1 Notazione (per un dato periodo)

Per owner `o`, con quota `q_o` alla data di riferimento:

- `I_o` = incassato **di persona** = Σ `Receivable.importo_pagato` con
  `incassato_da_owner = o`, `stato = PAGATO`.
- `A_o` = anticipato **di persona** = Σ `Expense.importo` con
  `anticipata_da_owner = o`.
- `I_tot = Σ_o I_o`, `A_tot = Σ_o A_o`.
- `cassa_netta(o) = I_o − A_o` (quanto ha materialmente in mano dalla gestione).
- `utile_cassa = I_tot − A_tot` (utile immobile per **cassa**; coincide con
  `ContoEconomicoView.blocco_cassa.utile` a meno di receivable senza incassante
  o spese senza anticipante).
- `utile_comp` = utile immobile per **competenza**
  (`ContoEconomicoView.blocco_comp.utile`).

### 2.2 Che cosa calcola davvero `saldi_live`

Da `calcola_saldi_correnti` (`saldi_live.py:116-156`), ignorando per ora
baseline settlement, BT inter-owner e `riferimento_quota_owner`:

- contributo incassi per `o` = `q_o·I_tot − I_o`
  (dai propri incassi `−(1−q_o)·I_o`, dagli altrui `+q_o·(I_tot−I_o)`);
- contributo spese per `o` = `A_o − q_o·A_tot`
  (dai propri anticipi `+(1−q_o)·A_o`, dagli altrui `−q_o·(A_tot−A_o)`).

Sommando:

```
saldi_live.totale(o)  =  q_o·(I_tot − A_tot)  −  (I_o − A_o)
                      =  q_o·utile_cassa      −  cassa_netta(o)
```

Convenzione `saldi_live`: `totale > 0` ⇒ **creditore** (gli altri gli devono);
`totale < 0` ⇒ **debitore** (deve agli altri). Il `piano_rientro` fa pagare i
debitori (`totale < 0`) ai creditori (`totale > 0`).

### 2.3 Il conguaglio, definito bene

Definiamo il **conguaglio di cassa** come nel brief ma esplicitando la base:

```
conguaglio_cassa(o) = cassa_netta(o) − q_o·utile_cassa = − saldi_live.totale(o)
```

**Sono la stessa grandezza, a segno opposto.** `conguaglio_cassa > 0` ⇒
l'owner ha incassato **più** della sua fetta ⇒ **deve versare** ⇒ è lo stesso
`o` che in `saldi_live` è debitore (`totale < 0`). Per costruzione
`Σ_o conguaglio_cassa = 0` (esatto, salvo record orfani → §7).

### 2.4 Dove nasce la divergenza: competenza

Il brief propone `conguaglio(o) = cassa_netta(o) − q_o·utile_**competenza**`.
Sostituendo la base:

```
conguaglio_comp(o) = cassa_netta(o) − q_o·utile_comp
                   = conguaglio_cassa(o) + q_o·(utile_cassa − utile_comp)
```

Due conseguenze **critiche**, entrambe da gestire nel design:

1. **`conguaglio_comp` NON è a somma zero.**
   `Σ_o conguaglio_comp = utile_cassa − utile_comp ≠ 0` in generale.
   Il residuo `utile_cassa − utile_comp` è esattamente lo **scarto di timing**:
   ricavi maturati per competenza ma non ancora incassati per cassa
   (`non_incassato`/insoluti, utenze ribaltate su periodo bolletta diverso
   dalla data di pagamento). Le spese cadono per data in entrambe le letture
   (`ContoEconomicoView`), quindi si semplificano: lo scarto è tutto lato
   ricavi. Non appartiene come **debito di cassa** a nessuno: si riassorbe da
   solo quando i soldi entrano.

2. **Segno opposto rispetto a `saldi_live`** (già visto in §2.3), più il termine
   di timing `q_o·(utile_cassa − utile_comp)`.

### 2.5 Sintesi della relazione (una frase)

> Il conguaglio **di cassa** è l'opposto esatto del `totale` di `saldi_live`
> (stessa grandezza, segno invertito, somma zero, alimenta il piano di
> rientro); il conguaglio **di competenza** proposto nel brief è quello di cassa
> più la quota individuale dello scarto di timing `q_o·(utile_cassa −
> utile_comp)`, e per questo NON somma a zero e NON è direttamente bonificabile.

### 2.6 Conseguenza di design

La colonna **azionabile** (quella che genera i bonifici) deve essere il
conguaglio **di cassa** `= −saldi_live.totale`: è l'unico numero a somma zero e
l'unico denaro realmente trasferibile. L'utile di **competenza** va mostrato
come *contesto/spettanza* con una riga di riconciliazione esplicita "scarto di
timing", per non reintrodurre la confusione cassa/competenza che il progetto ha
già faticato a separare (cfr. memoria `viapal_sbilancio_reale`,
`viapal_credito_pagamento_unico`).

---

## 3. Il prospetto proposto

Una riga per fratello, colonne concettuali **da sinistra (competenza) a destra
(azione di cassa)**:

| Colonna | Significato | Fonte di calcolo |
|---|---|---|
| Fratello / quota | anagrafica + `q_o` alla data di rif. | `quote_attive_at` |
| **Utile spettante (competenza)** | `q_o × utile_comp` — quanto ha *guadagnato* | `blocco_comp.utile` |
| **Cassa netta incassata** | `I_o − A_o` — quanto ha *in mano* (incassato − anticipato) | Receivable/Expense per owner |
| _di cui incassato_ / _di cui anticipato_ | `I_o` / `A_o` (dettaglio espandibile) | idem |
| **Scarto di timing** | `q_o × (utile_cassa − utile_comp)` — sua fetta del non-ancora-incassato | derivato |
| **Conguaglio (di cassa)** | `cassa_netta − q_o·utile_cassa = −saldi_live.totale` → **versare (+) / ricevere (−)** | `saldi_live` |

Sotto la tabella, il **piano di rientro** (bonifici concreti debitore→creditore)
ripreso da `calcola_piano_rientro`.

### 3.1 Tabella d'esempio (numeri plausibili, coerenti, zero-sum)

Ipotesi immobile per l'anno:
`utile_competenza = 30 000,00 €`, `utile_cassa = 27 000,00 €`
(3 000 € maturati ma non ancora incassati). Quote: Alessandro 0,3334,
Bruna 0,3333, Fabio 0,3333. Cassa: `I_tot = 33 000`, `A_tot = 6 000`.

| Fratello | Quota | Utile spettante (comp.) | Incassato `I_o` | Anticipato `A_o` | Cassa netta | Scarto timing | **Conguaglio (cassa)** |
|---|---:|---:|---:|---:|---:|---:|---:|
| Alessandro | 0,3334 | 10 002,00 | 25 000,00 | 5 000,00 | 20 000,00 | −1 000,20 | **+10 998,20** (versa) |
| Bruna | 0,3333 | 9 999,00 | 5 000,00 | 1 000,00 | 4 000,00 | −999,90 | **−4 999,10** (riceve) |
| Fabio | 0,3333 | 9 999,00 | 3 000,00 | 0,00 | 3 000,00 | −999,90 | **−5 999,10** (riceve) |
| **Totale** | 1,0000 | **30 000,00** | 33 000,00 | 6 000,00 | 27 000,00 | **−3 000,00** | **0,00** |

Verifiche:
- `Σ cassa netta = 27 000 = utile_cassa` ✔
- `Σ conguaglio_cassa = +10 998,20 − 4 999,10 − 5 999,10 = 0,00` ✔ (zero-sum)
- `Σ scarto timing = −3 000,00 = utile_cassa − utile_comp` ✔ (il residuo NON
  bonificabile: quota di ricavi non ancora entrati)
- conguaglio_competenza (a titolo informativo, `cassa_netta − q·utile_comp`):
  Alessandro +9 998,00 / Bruna −5 999,00 / Fabio −6 999,00, somma −3 000,00 →
  **non** zero, per questo NON lo usiamo per i bonifici.

### 3.2 Piano di rientro (di cassa, azionabile)

Dal conguaglio_cassa: Alessandro debitore 10 998,20; Bruna e Fabio creditori.

| Da | A | Importo |
|---|---|---:|
| Alessandro | Fabio | 5 999,10 |
| Alessandro | Bruna | 4 999,10 |
| **Totale bonifici** | | **10 998,20** |

Coincide con l'output di `calcola_piano_rientro` sui saldi live (segni
invertiti). Una volta eseguiti, i bonifici vanno marcati inter-owner dalla
Riconciliazione: i saldi si riallineano da soli (invariante di
`viapal_guardia_allocations` / `viapal_riconciliazione_fe`).

---

## 4. Dove collocarla — raccomandazione

**Raccomando una nuova pagina dedicata `/p/conguaglio-fratelli`** (name
`p-conguaglio-fratelli`), non una sezione dentro le due esistenti.

Motivazione (scelta unica, non elenco di opzioni):

- **Modello temporale diverso.** `SaldiFratelli` ragiona *a una data* sul
  *periodo aperto* (dall'ultimo settlement chiuso a oggi) ed è già densa: 5
  sezioni + 2 dialog (chiusura, voci settlement). Il conguaglio è **per anno
  solare**. Incastrarlo lì costringerebbe a convivere due selettori temporali
  incompatibili (data vs anno) e sovraccaricherebbe una pagina già operativa.
- **Prospettiva diversa da ContoEconomico.** `ContoEconomico` è *property-
  centric* (P&L dell'immobile, doppia lettura cassa/competenza). Il conguaglio è
  *owner-centric* e per anno; il blocco "Utile pro-quota" lì presente è solo un
  di cui informativo.
- **È la pagina-risposta.** Il fratello ci atterra per sapere «quanto devo
  versare/ricevere per il <anno>». Merita un URL proprio, linkabile dalle due
  pagine esistenti (che già si linkano a vicenda: `ContoEconomico` rimanda a
  `SaldiFratelli` alle righe 148-149).

Cross-link da aggiungere (non invasivi): dal blocco "Utile pro-quota" di
`ContoEconomico` e dall'header di `SaldiFratelli`, un link "→ Conguaglio
annuale".

---

## 5. Backend — modifiche minime

Nuovo endpoint read-only, **massimo riuso** del calcolo esistente. Nessun nuovo
modello, nessuna migrazione, nessuna persistenza.

### 5.1 Firma

```
GET /api/v1/dashboard/conguaglio-fratelli/?anno=YYYY
Permission: IsProprietario
```

`anno` opzionale (default anno corrente), intero; 400 se non parseabile
(stessa validazione di `ContoEconomicoView`).

### 5.2 Riuso

- **Utile competenza/cassa**: estrarre da `ContoEconomicoView` la logica dei due
  blocchi in un helper condiviso (es. `billing/services/conto_economico.py:
  calcola_blocchi(anno) -> {cassa, competenza}`) e chiamarlo sia dalla vista
  esistente sia da questa. Evita di duplicare i loop ricavi cassa/competenza e
  la separazione ordinarie/straordinarie.
- **Cassa per owner** (`I_o`, `A_o`): stessa logica di `bilancio_proprietari`
  (`dashboard_views.py:392-430`) filtrata per anno — riusare o fattorizzare.
- **Quote**: `quote_attive_at(min(31/12/anno, oggi))` come già fa
  `utile_pro_quota` (coerenza col numero mostrato in ContoEconomico).
- **Azione (piano di rientro)**: **non** ricalcolare un piano annuale ad hoc.
  Riusare `calcola_saldi_correnti(oggi)` + `calcola_piano_rientro(...)` +
  `verifica_quadratura(...)`: il piano azionabile è quello del **periodo aperto
  live** (i soldi realmente dovuti ora), non del solo anno storico. La tabella
  di conguaglio annuale è riconciliazione/contesto; i bonifici restano quelli di
  cassa live. Esporre entrambi ed etichettarli chiaramente.

### 5.3 Shape JSON di risposta

```jsonc
{
  "anno": 2026,
  "immobile": {
    "utile_competenza": 30000.00,
    "utile_cassa": 27000.00,
    "scarto_timing": -3000.00,        // utile_cassa - utile_competenza
    "non_incassato": 3000.00          // eco da ContoEconomico, per il tooltip
  },
  "fratelli": [
    {
      "owner_id": 1,
      "nominativo": "Alessandro",
      "quota": 0.3334,
      "utile_spettante_competenza": 10002.00,
      "incassato": 25000.00,          // I_o
      "anticipato": 5000.00,          // A_o
      "cassa_netta": 20000.00,        // I_o - A_o
      "scarto_timing": -1000.20,      // q_o*(utile_cassa - utile_comp)
      "conguaglio_cassa": 10998.20,   // cassa_netta - q*utile_cassa = -saldi_live.totale
      "conguaglio_competenza": 9998.00, // informativo, NON zero-sum
      "verso": "versa"                // "versa" | "riceve" | "pari"
    }
    // ...
  ],
  "piano_rientro": [                    // di cassa, live, da saldi_live
    { "da": {"id":1,"nominativo":"Alessandro"}, "a": {"id":3,"nominativo":"Fabio"},  "importo": 5999.10 },
    { "da": {"id":1,"nominativo":"Alessandro"}, "a": {"id":2,"nominativo":"Bruna"},  "importo": 4999.10 }
  ],
  "quadratura": {                       // eco da verifica_quadratura
    "conguaglio_cassa_somma": 0.00,
    "quadra": true,
    "receivable_orfani": [],
    "expense_orfane": []
  }
}
```

Note:
- `conguaglio_cassa` a somma zero è la colonna azionabile; `conguaglio_competenza`
  è di cui informativo (il FE lo può nascondere in un tooltip/espansione).
- `piano_rientro` e `quadratura` sono l'eco della logica `saldi_live` già
  serializzata (`SaldoLiveSerializer`, `PianoRientroVoceSerializer`,
  `QuadraturaSerializer` riusabili).

---

## 6. Frontend — modifiche minime

- **Nuova pagina** `frontend/src/pages/ProprietarioConguaglioFratelli.vue` +
  route in `routes.ts` (accanto a `saldi-fratelli`/`conto-economico`, righe
  93-102).
- **Nuovo store** `stores/conguaglioFratelli.ts` con `fetchConguaglio(anno)`;
  oppure — se si vuole minimizzare — un'action nello store `contoEconomico`
  esistente. Raccomando store dedicato: la pagina è autonoma.
- Riuso composables esistenti: `useFormatoEuro`, `useFormatoData`,
  `useOwnersStore`. Riuso classi di stile `vp-mono`, `vp-saldi__pos/neg`,
  eyebrow/display già presenti (coerenza visiva con SaldiFratelli).
- Selettore **anno** (non data) in testa. Banner quadratura riusando lo stesso
  pattern di `ProprietarioSaldiFratelli.vue` (righe 30-80).
- Cross-link "→ Conguaglio annuale" da ContoEconomico e SaldiFratelli.

---

## 7. Edge case

1. **Quote cambiate a metà anno** (`OwnershipShare.valid_from/valid_to`).
   Sia `saldi_live` sia `utile_pro_quota` usano una quota **puntuale**
   (`quote_attive_at(data)`), non pesata sul tempo. Il conguaglio erediterà la
   stessa approssimazione: coerente con l'esistente, ma da **documentare in UI**
   ("quota alla data del <31/12 o oggi>"). Una ponderazione temporale sarebbe un
   miglioramento separato, da fare in `saldi_live` per non divergere.
2. **Spese straordinarie.** In cassa entrano in `A_o`/`A_tot` come le ordinarie
   (nessuna distinzione lato conguaglio). In competenza sono già dentro
   `utile_comp`. Mostrare eventualmente il di cui straordinario nel dettaglio,
   ma non cambia la matematica dello zero-sum.
3. **`riferimento_quota_owner`** (es. Bruna paga IMU di Fabio). `saldi_live` la
   tratta come credito intero verso il referente, **fuori pro-quota**
   (`saldi_live.py:138-149`). Se il conguaglio_cassa lo si prende come
   `−saldi_live.totale` questo è **già incluso** e coerente. Se invece si
   ricalcolasse `cassa_netta − q·utile_cassa` da zero, si perderebbe quel
   trattamento speciale e si romperebbe lo zero-sum. **Regola: derivare la
   colonna azionabile da `saldi_live`, non ricostruirla.** Le colonne di
   competenza (`I_o`, `A_o`) restano descrittive.
4. **Anni senza settlement di baseline.** `saldi_live` senza settlement chiusi
   considera l'intera storia (`_ultimo_settlement` → `periodo_da = None`). Il
   `piano_rientro` live coprirebbe più del singolo anno. Da chiarire in UI: "il
   conguaglio annuale è per competenza; i bonifici azzerano il dovuto **di cassa
   a oggi**" (che può includere anni non ancora chiusi). Se un anno è già chiuso
   con `OwnerSettlement`, quel conguaglio è storicizzato: mostrarlo read-only e
   segnalare "periodo chiuso".
5. **Arrotondamenti** (0,3334 / 0,3333 / 0,3333). `quote_attive_at`
   riproporziona se la somma ≠ 1 (owner.py:32-37). Per evitare drift, calcolare
   il conguaglio con `Decimal` e arrotondare **solo in output** (come già fa
   `saldi_live` con `quantize(0.01)` nel piano). Lo zero-sum va verificato dopo
   l'arrotondamento (il piano assorbe i centesimi residui sull'ultimo
   trasferimento, come già avviene).
6. **Receivable senza `incassato_da_owner` / Expense senza anticipante
   (orfani).** Falsano `I_tot`/`A_tot` in silenzio. Riusare
   `verifica_quadratura` ed esporre il banner: se ci sono orfani, il conguaglio
   di cassa **non** quadra ed è dichiarato tale, con link alla Riconciliazione
   (identico a SaldiFratelli).

---

## 8. Rischi e cosa NON fare

- **NON usare l'utile di competenza per generare i bonifici.** Romperebbe lo
  zero-sum (`Σ conguaglio_comp = utile_cassa − utile_comp ≠ 0`) e chiederebbe di
  bonificare denaro non ancora incassato. La colonna azionabile è di **cassa**.
- **NON ricostruire il conguaglio di cassa da zero** ignorando `saldi_live`:
  perderesti baseline settlement, BT inter-owner, `riferimento_quota_owner`,
  scoping periodo aperto. Derivalo da `saldi_live.totale` (segno invertito).
- **NON reintrodurre la confusione cassa/competenza.** Etichettare ogni numero
  con la sua base; tenere la competenza come "spettanza/contesto" e la cassa
  come "azione". Lo scarto di timing è la riga che tiene onesta la tabella.
- **NON persistere** questa vista: come `saldi_live`, è calcolata al volo. La
  storicizzazione passa solo da `OwnerSettlement` (chiusura periodo).
- **NON duplicare i loop di calcolo**: fattorizzare i blocchi di ContoEconomico
  e la logica bilancio-per-owner in helper condivisi, per non far divergere due
  definizioni di "utile".

---

## 9. Riepilogo relazione (per il commit message / PR)

```
conguaglio_cassa(o)  = cassa_netta(o) − q_o·utile_cassa = −saldi_live.totale(o)   [zero-sum, azionabile]
conguaglio_comp(o)   = conguaglio_cassa(o) + q_o·(utile_cassa − utile_comp)       [informativo, non zero-sum]
Σ conguaglio_comp    = utile_cassa − utile_comp = −scarto_timing_immobile
```
