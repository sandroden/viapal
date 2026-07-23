# Reviewer "Architettura/Backend" — Round di dibattito

Reazione alle posizioni di ALGEBRA (8.5), DEVIL (4), FABIO (4) dopo la mia
fase 3 (6.5). Codice riletto: `saldi_live.py` per intero.

---

## Dove convergiamo (e cosa cambia per me)

Le quattro review, per strade diverse, colpiscono **lo stesso nervo**: la riga
vuole essere "anno" e "live" insieme.

- Il mio F1/F3/F5 = "due basi temporali nella stessa formula, riconciliano solo
  nel caso degenere".
- Algebra F4 = "due finestre diverse (anno solare vs periodo aperto), l'esempio
  §3.1 le maschera".
- Devil F4 = "il selettore-anno guida l'header ma NON il piano di rientro:
  controllo che mente".

Sono la stessa cosa vista da tre angoli. Algebra dà la prova numerica che le due
finestre non torneranno; Devil dà la conseguenza UX (un controllo placebo); io
davo la lettura architetturale. **Questa convergenza tripla è, per me, il fatto
più solido del panel** e va pesata più di qualsiasi punteggio singolo.

Il Devil mi costringe a un aggiornamento onesto. La mia fase 3 concludeva
"spezzare in due blocchi + `saldi_live` period-aware **su una pagina nuova**". Il
Devil dimostra (F1, verificato: `ProprietarioSaldiFratelli.vue` mostra già
`s.totale` e il piano "Chi deve a chi") che il blocco live **azionabile esiste
già interamente in SaldiFratelli**. Quindi il mio "due blocchi" è corretto, ma il
contenitore che immaginavo (pagina dedicata) è sbagliato: i due blocchi devono
mappare sulle **due pagine che già esistono**, non fondersi in una terza. Cedo
terreno al Devil sul contenitore; mantengo la mia diagnosi sui dati.

---

## Risposte alle domande

### Q1 — Rendere `saldi_live` period-aware: contenuto o tocca un invariante?

**Più costoso e rischioso di come l'avevo prezzato in fase 3. Ridimensiono la mia
stessa raccomandazione.**

Il write-invariant "guardia allocations" **non** è in gioco: `saldi_live` è
read-only, non persiste nulla (docstring `:1-8`), quindi zero rischio di
sovrascrivere Receivable con allocations vive. Anche lo "sbilancio reale" è
modulo separato (tenant-level). Su questo fronte il rischio di regressione da
scritture è nullo.

Il problema vero è **la baseline**, ed è strutturale:

- `calcola_saldi_correnti(at_date)` NON è per-anno per costruzione. È
  "baseline dell'ultimo `OwnerSettlement` chiuso ≤ at_date + movimenti del solo
  periodo aperto" (`:96-105`, `:113-114`). La baseline è uno **snapshot** che
  esiste **solo alle date di settlement** (`:74-78`).
- Per un "conguaglio del solo 2024" servirebbe una baseline allo stato al
  31/12/2023. Quella baseline **non esiste** salvo che ci sia un settlement
  esattamente a quel confine. Aggiungere un parametro `periodo_da` in modo naïf
  darebbe numeri **sbagliati**: `_ultimo_settlement` prenderebbe l'ultimo
  settlement ≤ `at_date` (fine), non ≤ inizio periodo.
- Renderlo corretto per un anno arbitrario impone di **ricalcolare una baseline
  sintetica** = cumulato da inizio-storia a `periodo_da−1`. È esattamente il
  ricalcolo su tutta la storia che l'ottimizzazione baseline-da-settlement
  nasceva per **evitare** (docstring `:4-6`: "eviterebbe rumore"), e **rieredita
  la fragilità orfani/quadratura** (`verifica_quadratura`) sull'intera storia,
  non più solo sul periodo aperto.

Quindi: **NON è un intervento contenuto** se si vuole il per-anno con baseline
corretta. È contenuto **solo** in due varianti degeneri:
1. limitarsi al periodo aperto corrente (che però *non è* un dato d'anno), oppure
2. anni chiusi = **read-only da snapshot `OwnerSettlement`**, nessun ricalcolo
   live; live solo per il periodo aperto.

Rischio sulle pagine esistenti: basso **a condizione** di non toccare il path di
default (firma `at_date`-only invariata, coperta da `test_saldi_live.py`). Ma
proprio perché il per-anno corretto costringe a ricalcolare la storia, la strada
pulita non è "period-aware saldi_live" — è la variante (2). **Correggo la mia
fase 3**: la raccomandazione F3/F5 "rendere saldi_live period-aware" va sostituita
con "anni chiusi read-only da settlement, live solo periodo aperto". Questo
avvicina la mia posizione a quella del Devil.

### Q2 — "Due blocchi" implica una pagina nuova? Collocazione più pulita.

**No, non la implica — e non deve.** I dati live vivono già in SaldiFratelli
(Devil F1, verificato). La collocazione architetturalmente più pulita mappa ogni
blocco sulla pagina dove la sua base temporale è **nativa**:

- **Blocco LIVE / azionabile** (conguaglio cassa = `−saldi_live.totale` + piano
  di rientro): **resta dov'è, in SaldiFratelli.** È l'unica fonte che produce
  bonifici e c'è già. Nessuna duplicazione.
- **Blocco COMPETENZA / anno** (utile spettante pro-quota): **in ContoEconomico**,
  che è già per-anno e ha già la card "Utile pro-quota". Lì il numero d'anno è
  nativo, il selettore-anno guida ciò che deve guidare, e nessun controllo mente.
- **Ponte**: una frase calcolata ("spettante X, in mano Y → versi/ricevi Z") +
  deep-link al piano già esistente. Devil Alt-B/Alt-C.

Questo è più pulito della mia proposta di fase 3 perché **preserva la single-
source-of-truth**: il numero azionabile e il piano restano in **un solo** posto
(SaldiFratelli), invece di essere ri-renderizzati in una terza cornice — che è
proprio il fallimento "Alessandro→Fabio 5.999,10 in due pagine con due titoli"
del Devil F3, e il precedente interno delle superfici da riconciliare a mano
(`viapal_paginazione_cap_silenzioso`, `viapal_sbilancio_reale`).

Concordo quindi con l'ossatura Alt-A/Alt-B del Devil. Un caveat verso il Devil:
la sua Alt-A (colonna competenza-anno **dentro** SaldiFratelli) reintroduce il
clash temporale nella pagina live — meglio Alt-B (competenza in ContoEconomico,
dove l'anno è nativo) + ponte. Su questo la collocazione pulita è la sua Alt-B,
non la sua Alt-A.

### Q3 — `conguaglio_competenza` nel payload: rischio bonifico? Rimuovere o etichettare?

**Rischio reale, e più che etichettare va RIMOSSO dal payload azionabile.** In
fase 3 (F9) avevo proposto di annidarlo sotto `informativo.`. Il Devil (F6) ha
ragione a spingere oltre: "se va nascosto, perché esporlo". Riconcilio così:

- Il foot-gun non è (solo) la posizione, è il **nome**. Un campo `conguaglio_*`
  accanto a un altro `conguaglio_*`, uno azionabile e uno no, in un prodotto la
  cui intera memoria è "non confondere cassa e competenza"
  (`viapal_sbilancio_reale`, `viapal_credito_pagamento_unico`), è un errore di
  distrazione dal bonifico sbagliato.
- La competenza **non è un conguaglio**: è un **utile maturato** (P&L). Quindi:
  (a) togliere del tutto il nome `conguaglio_competenza`; (b) esporre la
  competenza solo come `utile_spettante` **nella response di ContoEconomico**
  (dove già vive, per-anno), **non** come sibling di `piano_rientro`/conguaglio
  cassa.

Se il blocco competenza sta in ContoEconomico (Q2), il problema si dissolve da
solo: i due numeri non sono più nello stesso payload. **Rimozione dal payload
azionabile, non etichetta.**

### Q4 — RECUPERABILE con fix o SOSTITUIRE?

**Split netto: contenuto RECUPERABILE, contenitore da SOSTITUIRE.**

Su questo il panel è unanime, non solo io: il Devil dice esplicitamente
(nota di equità) che §2/derivazione/zero-sum/"derivare da `saldi_live`, non
ricostruire" vanno **conservati**; Algebra li valida a 8.5. Il valore è tutto
nell'analisi. Ciò che fallisce è il **veicolo** (pagina dedicata + selettore-anno
+ colonne riconciliative come `scarto_timing`).

Fix in ordine di priorità:

1. **Sostituire il contenitore.** Niente terza pagina. Blocco azionabile
   (conguaglio cassa + piano) resta in SaldiFratelli. Risolve i miei F1/F5 e i
   Devil F2/F3/F4 in un colpo. [P0]
2. **Competenza/anno in ContoEconomico** (card "Utile pro-quota", già esistente)
   + frase-ponte calcolata + deep-link. Il selettore-anno guida solo la
   competenza, che è la sua base nativa → non mente più. [P0]
3. **Anni chiusi read-only da snapshot `OwnerSettlement`; live solo periodo
   aperto.** Sostituisce il mio F3 "period-aware" (Q1: troppo costoso/rischioso
   per baseline+orfani). [P1]
4. **Rimuovere `conguaglio_competenza` dal payload azionabile** (Q3): la
   competenza esce solo come `utile_spettante` nella response di ContoEconomico.
   [P1]
5. **Allineare gli universi-sorgente** (mio F2 + Algebra F5): se un numero live è
   derivato, derivarlo da `saldi_live` in modo coerente (stesso filtro causale,
   gestione DEPOSITO esplicita); non mischiare `bilancio_proprietari` +
   `ContoEconomico`, universi diversi. [P2]
6. **Provare prima il collante leggero** (Devil Alt-C: cross-link + una frase),
   e costruire i blocchi solo se non basta. [P2]

Non "sostituire tutto": la contabilità è oro. Sostituire il **modo di
consegnarla**.

---

## Punteggio aggiornato

**6.5 → 5.5 / 10** (solidità architetturale del design *as-proposed*).

Motivazione dello spostamento verso il basso (di 1 punto):
- Il dibattito ha rivelato che **la mia stessa toppa di rescue** ("saldi_live
  period-aware") è **più costosa e rischiosa** di come l'avevo prezzata (Q1:
  costringe a ricalcolare la storia e rieredita la fragilità orfani). Un design
  la cui via di salvataggio è così cara vale meno del 6.5 che gli avevo dato.
- Il Devil ha reso concreto che il contenitore (terza pagina) è positivamente
  dannoso, non solo subottimale: duplica il piano già in SaldiFratelli e
  introduce il selettore-che-mente **dentro** la pagina. La convergenza tripla
  (io+Algebra+Devil) sul clash anno/live conferma che è un difetto di struttura,
  non un dettaglio.

Non scendo sotto 5.5 perché l'analisi contabile (§2, zero-sum, "derivare da
saldi_live") è solida e verificata — il design è recuperabile ricollocando i due
blocchi sulle pagine esistenti. Resto sopra il 4 del Devil perché il gap che il
design individua è **reale** (utile di competenza e cassa netta non sono affiancati
da nessuna parte oggi) e il suo contenuto analitico è la base giusta per colmarlo.

Posizione finale: **RECUPERABILE nel contenuto, SOSTITUIRE il contenitore.**
Blocco live/azionabile in SaldiFratelli (dov'è già), blocco competenza/anno in
ContoEconomico (dov'è nativo), ponte calcolato + deep-link. NO terza pagina, NO
`saldi_live` period-aware (anni chiusi = snapshot read-only), NO
`conguaglio_competenza` nel payload azionabile.
