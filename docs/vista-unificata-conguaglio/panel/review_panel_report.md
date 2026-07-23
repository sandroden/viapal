# Review Panel Report — Vista unificata "Conguaglio fratelli"

**Oggetto:** `docs/vista-unificata-conguaglio/DESIGN.md` + `mockup.html` (design, non codice di produzione)
**Data:** 2026-07-05
**Panel:** 4 reviewer (Algebra Hawk · Architettura/Backend · Fratello non-contabile «Fabio» · Devil's Advocate) + sintesi giudice
**Modalità:** Assessment/Design review — la domanda guida era *«i due piani separati + il nuovo prospetto sono davvero comprensibili a un fratello non contabile, o inducono in errore?»*
**Verdetto:** **REVISIONE MAGGIORE** — contenuto analitico da **conservare**, contenitore (terza pagina + mix anno/live) da **sostituire**. Punteggio medio finale **5,5/10**.

> Nota di processo: 2 reviewer sono falliti a vuoto al primo lancio (0 tool-call, un system-reminder "plan mode" iniettato nel subagente) e sono stati ri-dispatchati con successo. Dibattito: 1 round completo, tutti e 4 hanno aggiornato la posizione. Nessuna analisi live dell'app (screenshot #3 ancora pendenti sul login).

---

## Executive summary

Il design fa **una cosa giusta e una sbagliata**, ed entrambe in modo netto.

- **Giusto — l'analisi (§2).** Il ponte tra *utile di competenza* («quanto ho guadagnato») e *cassa/dare-avere* («quanto ho in mano / quanto devo versare») è corretto al centesimo e verificato riga-per-riga contro `saldi_live.py`. L'identità `conguaglio_cassa = −saldi_live.totale` e la nozione di *scarto di timing* sono contabilmente solide. Questo insight **va mostrato** da qualche parte: è esattamente ciò che oggi manca ai fratelli.
- **Sbagliato — la confezione.** Mette nella stessa riga grandezze **per-anno solare** (utile, cassa netta) e un numero **live sul periodo aperto** (`−saldi_live.totale`, che porta con sé baseline settlement, BT inter-owner, e la causale DEPOSITO). L'esempio del mockup sceglie numeri in cui i due coincidono, e così **nasconde** il difetto strutturale che il design stesso dichiara. Su soldi veri, da telefono, il conguaglio annuale mostrato può **non coincidere** con il bonifico chiesto sotto → rischio di versare l'importo sbagliato.

**Convergenza indipendente** (segnale forte, non concordato): tutti e 4 i reviewer, da angoli diversi, colpiscono lo stesso nodo — il **mismatch di periodo anno-vs-live** — e nel dibattito **nessuno difende la terza pagina dedicata**.

---

## Score summary

| Reviewer | Lente | Iniziale | Finale | Δ | Perché è cambiato |
|---|---|---:|---:|---:|---|
| Algebra Hawk | correttezza matematica | 8,5 | **7,0** | −1,5 | Concede che il mismatch di periodo è **P0 strutturale** (non P1) e trova un buco nella propria analisi (causale DEPOSITO non filtrata). |
| Architettura/Backend | coerenza dati/API | 6,5 | **5,5** | −1,0 | La sua stessa toppa («saldi_live period-aware») si rivela cara/rischiosa; la terza pagina è dannosa, non solo subottimale. |
| Fabio (non-contabile) | comprensibilità | 4 | **5,0** | +1,0 | Il dibattito porta la cura giusta (numero dove già guardo), ma il design as-is resta un rebus. |
| Devil's Advocate | esistenza/valore | 4 | **4,5** | +0,5 | Concede che l'insight è oro, ma la critica alla confezione regge ed è rafforzata dalla convergenza. |

---

## Consensus points (confermati dal giudice)

1. **L'analisi §2 è corretta e preziosa** — va preservata e mostrata una volta sola, senza reintrodurre la confusione cassa/competenza.
2. **Il numero azionabile esiste già** in `/p/saldi-fratelli` (`−saldi_live.totale` + piano di rientro). Il valore incrementale del design è *affiancargli l'utile di competenza*, non ricrearlo.
3. **Niente terza pagina.** Aggiungere un terzo posto dove guardare peggiora il problema «due posti + sottrazione a mente» che il design dice di risolvere.
4. **Il segno va reso a prova di fretta**: verbo + colore («RICEVI 5.999 €» / «VERSA …»), non numeri con segno controintuitivo (negativo = ricevo).
5. **«Scarto di timing» è gergo**: se mostrato, va detto in italiano semplice («ricavi maturati ma non ancora incassati»), come contesto, non come colonna in prima pagina.

---

## Disputa principale e ruling

**Poli:** Algebra/Architettura → *«recuperabile, sistemare lo scoping»* · Devil/Fabio → *«non costruire la pagina così com'è»*.

**Ruling del giudice:** **contenuto RECUPERABILE, contenitore da SOSTITUIRE.** La disputa si è risolta in convergenza durante il dibattito: al termine anche Algebra e Architettura propendono per collocare il numero nelle pagine esistenti. Il design non è da buttare (l'algebra è oro) né da implementare così com'è (indurrebbe in errore). È una **riprogettazione della UI/scoping**, non una riscrittura dell'analisi.

---

## Action items

### P0 — bloccanti (design difettoso as-written, radicato in un vincolo di codice reale)
1. **[P0] Risolvere il mismatch anno-vs-live.** `calcola_saldi_correnti` prende solo `at_date` e lavora sul periodo aperto (dall'ultimo `OwnerSettlement` a oggi): `?anno=YYYY` su un anno **chiuso** restituisce il numero della finestra sbagliata. → Regola: il numero **azionabile** (bonifici) è sempre quello di cassa **live** sul periodo aperto; gli anni chiusi si mostrano **read-only da snapshot `OwnerSettlement`**, non ricalcolati. Non tentare di rendere `saldi_live` period-aware (impone il ricalcolo di tutta la storia + fragilità sugli orfani → costo/rischio alto, tocca invarianti noti: guardia allocations, sbilancio reale).
2. **[P0] Non stampare la formula piana in riga.** L'azionabile è `−saldi_live.totale` (opaco): include baseline settlement, BT inter-owner e `riferimento_quota_owner`. La formula scritta `cassa_netta − q·utile_cassa` è **falsa** quando quei termini non sono nulli (es. caso Bruna paga IMU di Fabio).
3. **[P0-UX] Il «mio numero» in cima.** L'utente deve atterrare su un blocco grande e personale — «Fabio: RICEVI 5.999,10 €» — non su 3 KPI dell'immobile + tabella dei tre da cui cercarsi la riga.

### P1 — seri
4. **[P1] Allineare gli universi-sorgente.** `utile_cassa` (ContoEconomico, tutti i record) e `cassa_netta` (bilancio_proprietari, solo attribuiti); `saldi_live` **non filtra** la causale DEPOSITO mentre `bilancio_proprietari` la esclude → con orfani/depositi lo zero-sum salta in silenzio. Riusare `verifica_quadratura` ed esporre il banner (come in SaldiFratelli).
5. **[P1] Togliere `conguaglio_competenza` dal payload azionabile** (o marcarlo inequivocabilmente non-bonificabile): è a somma non-zero, qualcuno lo userebbe per bonificare.
6. **[P1] Mobile.** Nel mockup la colonna Conguaglio esce dallo schermo (`min-width: 640px`): su una PWA è dove l'utente la userà.

### P2 — minori
7. **[P2]** `scarto_timing ≠ −non_incassato` in presenza di incassi cross-anno: non equipararli.
8. **[P2]** Riuso serializer sovrastimato: `fratelli[]` richiede un serializer nuovo, non solo quelli di `saldi_live`.
9. **[P2]** Refactor `calcola_blocchi(anno)` fattibile ma deve restituire anche `non_incassato`/insoluti per il tooltip.

---

## Raccomandazione operativa (sintesi delle alternative emerse)

Al posto della terza pagina, **due interventi coordinati sulle pagine esistenti**:

- **In `/p/saldi-fratelli`** (dove i bonifici già vivono): resta la fonte del numero **azionabile** di cassa live + piano di rientro. Aggiungere solo il «mio numero» in evidenza (verbo+colore) se non già così.
- **In `/p/conto-economico`**, card «Utile pro-quota»: aggiungere un **box di riconciliazione per l'anno selezionato** (selettore anno nativo, non mente) — «hai *maturato* X (competenza) · in mano ne hai Y · la differenza Z arriverà quando gli inquilini pagano» — con **deep-link** «→ quanto devi versare/ricevere adesso» verso SaldiFratelli. Niente colonna «scarto di timing»: diventa una frase.

Questo conserva l'insight §2 (mostrato **una volta**, nel posto giusto: la competenza vive in ContoEconomico, la cassa in SaldiFratelli), elimina il mix anno/live nello stesso numero, e non aggiunge un terzo luogo.

**Must-have di Fabio (in ordine):** 1) il mio numero in cima (italiano+verbo+colore); 2) un solo numero azionabile senza contraddizione anno-vs-live; 3) il resto come contesto/frase, funzionante su telefono.

---

## Scope & limiti

- Recensito: il **design** e il **mockup statico**. NON valutati: comportamento runtime, dati di produzione, e la resa reale delle pagine esistenti (screenshot #3 pendenti sul login proprietario).
- Limite strutturale: i 4 reviewer condividono lo stesso modello base → possibile bias correlato. La convergenza va letta con questa cautela, ma è mitigata dal fatto che ciascuno è arrivato al nodo per una strada diversa (matematica / dati / UX / valore).
- Etichette: [EXISTING] = vincolo già nel codice · [PLAN_RISK] = rischio in implementazione. I P0 1-2 sono design-flaw radicati in vincoli EXISTING di `saldi_live`.

## Materiale (state files)

`docs/vista-unificata-conguaglio/panel/state/` — per ogni reviewer: `*_phase3.md` (review indipendente) + `*_debate.md` (posizione post-dibattito).
