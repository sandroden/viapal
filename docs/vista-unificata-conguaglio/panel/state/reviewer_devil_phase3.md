# Reviewer "Devil's Advocate" — fase 3

Panel adversariale sul DESIGN `vista-unificata-conguaglio`. Ruolo: sfida radicale
della premessa. Ragionamento analogico. Non difendo il design: cerco il caso in
cui NON va costruito, o va costruito diversamente.

Tag: `[EXISTING]` = fatto verificato nel codice/design attuale;
`[PLAN_RISK]` = rischio del piano proposto.

---

## Punteggio

**4 / 10** — quanto è giustificato costruire QUESTO design così com'è.

Il calo non nasce dalla matematica (§2 è corretta e onesta) ma dalla **forma**
scelta: una terza pagina dedicata che duplica il piano di rientro live già
presente in SaldiFratelli, guidata da un selettore-anno che NON muove l'unico
numero azionabile, e che spedisce due colonne non-azionabili (`scarto_timing`,
`conguaglio_competenza`) la cui unica funzione è tenere in piedi l'accostamento
di due basi contabili che il progetto ha deliberatamente separato. Il valore
incrementale reale (mettere l'utile di competenza accanto alla cassa netta) vale
1 colonna o 1 box, non 1 pagina + 1 store + 1 endpoint.

---

## Findings

### F1 — [P0][EXISTING] L'unico numero azionabile ESISTE GIÀ, per intero, in SaldiFratelli

Il design ammette tre volte (§2.6, §5.2, §8) che l'unica colonna che genera
bonifici è il **conguaglio di cassa** `= −saldi_live.totale`. Ma:

- `saldi_live.totale(o)` per owner è **già mostrato** in
  `ProprietarioSaldiFratelli.vue` come `s.totale` nella card per fratello
  (righe 103-106), con classe pos/neg.
- il **piano di rientro** (chi versa a chi) è **già una sezione intera** della
  stessa pagina — "Chi deve a chi", righe 181-210, alimentata da
  `store.pianoRientro` = `calcola_piano_rientro`.

Quindi il numero azionabile e la sua azione (i bonifici) sono **già entrambi**
in SaldiFratelli. Il conguaglio di cassa è `s.totale` a segno invertito: la
stessa card lo dice già. **Il nuovo prospetto non aggiunge NESSUNA informazione
azionabile nuova.** §2.3 lo dice a chiare lettere: «Sono la stessa grandezza, a
segno opposto». Un design che riscrive `−saldi_live.totale` in una pagina nuova
sta re-etichettando un numero esistente, non colmando un gap operativo.

Valore incrementale netto della vista, rispetto alle due pagine esistenti =
**vedere l'utile di competenza pro-quota accanto alla cassa netta**. È il solo
delta. E anche quello è già a un clic: ContoEconomico → card "Utile pro-quota".

### F2 — [P0][PLAN_RISK] Una terza pagina PEGGIORA il problema che dichiara di risolvere

Il gap dichiarato (§1) è: «il fratello consulta **due pagine** e fa la
sottrazione a mente». La cura proposta introduce una **terza** pagina. Ora i
numeri owner-level di denaro vivono in **tre** posti:

1. `ContoEconomico` → "Utile pro-quota" per fratello (cassa/competenza), righe
   142-161 — con già il cross-link «il dare/avere è in Saldi fratelli» (149).
2. `SaldiFratelli` → `s.totale` per fratello + piano di rientro.
3. `Conguaglio` (nuova) → utile competenza + cassa netta + conguaglio + piano.

Il problema non era "manca un posto"; era "sono in due posti diversi". La
soluzione idiomatica a "due posti" è **uno**, non **tre**. Analogia: un utente
che si lamenta di dover aprire due tab non è aiutato da una terza tab che
riassume le prime due — deve ancora decidere quale delle tre è la verità, e ora
ha una superficie in più da tenere sincronizzata mentalmente.

### F3 — [P1][PLAN_RISK] Il piano di rientro viene DUPLICATO alla lettera in due pagine

§3.2 e §5.2 sono espliciti: il piano della nuova vista **è** `calcola_piano_rientro`
sui saldi live — cioè **lo stesso identico output** già renderizzato in
SaldiFratelli (righe 181-210). Non "simile": lo stesso, live, non annuale
(§5.2: «non ricalcolare un piano annuale ad hoc»).

Due pagine che mostrano lo **stesso** elenco di bonifici, ma incorniciato una
volta come "saldi alla data" e una come "conguaglio <anno>", è una violazione di
single-source-of-truth a livello di UX. Anche se il codice riusa la funzione (e
quindi i numeri coincidono per costruzione), **la cornice diverge**: il fratello
può leggere «Alessandro → Fabio 5.999,10» in due pagine con due titoli diversi e
concludere che siano **due obbligazioni diverse** (una "di cassa" e una "del
2026"), e bonificare due volte, o non capire perché cambiando anno l'elenco non
cambia (→ F4). Il progetto ha già pagato il prezzo di superfici che sembravano
indipendenti e andavano riconciliate a mano (cfr. memoria
`viapal_paginazione_cap_silenzioso`, `viapal_sbilancio_reale`).

### F4 — [P1][PLAN_RISK] Il selettore-anno è un controllo che mente

§4 giustifica la pagina separata proprio sul **modello temporale diverso**:
SaldiFratelli è "a una data / periodo aperto", il conguaglio è "per anno
solare", e mescolarli «costringerebbe a convivere due selettori temporali
incompatibili». Ma poi §5.2 e §7.4 stabiliscono che l'unica parte azionabile —
il piano di rientro — **deve** restare quella **live** del periodo aperto (che
§7.4 avverte «può includere anni non ancora chiusi»), **non** quella dell'anno
selezionato.

Risultato: la pagina ha un selettore "Anno" in testa (mockup righe 120-124) che
guida l'header di competenza ma **non** guida il piano di rientro sotto. L'utente
cambia anno → l'unico numero su cui può agire **non cambia**. È esattamente
l'incompatibilità dei due modelli temporali che §4 usava per giustificare la
separazione — solo che ora vive **dentro** la pagina nuova invece che tra due
pagine. Il design ha spostato il problema, non risolto. Un controllo che appare
pilotare l'output azionabile ma non lo fa è un anti-pattern noto (controlli che
mentono / "placebo control").

### F5 — [P1][PLAN_RISK] "Scarto di timing" è una toppa concettuale, non una feature

§8 è autoincriminante: «lo scarto di timing è la riga che tiene onesta la
tabella». Cioè: la colonna non esiste perché un fratello ne ha bisogno, ma
perché **senza di essa la tabella non quadra** una volta che si è deciso di
mettere competenza e cassa sulla stessa riga. È l'artefatto ad avere bisogno
della colonna, non l'utente. Un proprietario reale che vuole sapere «quanto
verso» guarda una cella (conguaglio di cassa) e ignora `q_o·(utile_cassa −
utile_comp)`.

Il tell diagnostico: si sta introducendo **una grandezza in più** pur di far
convivere due basi contabili che il progetto ha faticato a separare (§2.6 cita
`viapal_sbilancio_reale`, `viapal_credito_pagamento_unico`). La domanda radicale
non è "come etichettiamo lo scarto", ma "**perché** accostiamo competenza e cassa
sulla stessa riga?". Se la risposta è "così il fratello vede il contesto", allora
il contesto sta bene come **testo/box** ("hai maturato 10.002, ne hai in mano
20.000, quindi devi versare"), non come colonna riconciliativa che richiede una
seconda colonna correttiva.

### F6 — [P2][PLAN_RISK] `conguaglio_competenza` nel JSON: un numero che si spedisce e si vieta di usare

§5.3 mette in risposta `conguaglio_competenza` (non zero-sum) e §8 impone «NON
usare l'utile di competenza per generare i bonifici». Si sta serializzando, in
un prodotto la cui intera storia-memoria è "non confondere cassa e competenza",
un campo chiamato `conguaglio_*` che **non va azionato**, accanto a un altro
`conguaglio_*` che **va** azionato. Ogni consumer futuro dell'endpoint (o un FE
frettoloso) è a un errore di distrazione dal bonificare il numero sbagliato. La
mitigazione proposta ("il FE lo nasconde in un tooltip") conferma che il campo
non serve: se va nascosto, perché esporlo.

### F7 — [P3][EXISTING] Il cross-link — cioè l'alternativa più economica — il design lo prevede già come contorno

§4 (righe 212-214) aggiunge comunque i cross-link «→ Conguaglio annuale» da
ContoEconomico e SaldiFratelli, e nota che le due pagine **già si linkano a
vicenda**. Cioè il design riconosce che il collante leggero (link) è utile e va
fatto **in ogni caso**. Ma allora buona parte del gap "sottrazione a mente" è
già attaccabile con il collante leggero + una frase calcolata, senza la pagina.
Il design non confronta mai questa alternativa (§4 dichiara esplicitamente
"scelta unica, non elenco di opzioni") — che è precisamente il punto cieco di un
design che parte dalla conclusione "serve una pagina".

---

## Alternative (mandato §4.4)

### Alt-A — Una colonna in SaldiFratelli
Aggiungere alla card per fratello (o a una tabellina) la voce **"Utile spettante
(competenza) <anno>"** accanto a `s.totale`, con una riga "→ quindi versi/ricevi
`−s.totale`".
- **Pro**: zero nuove pagine; riusa il piano di rientro già lì; il numero
  azionabile e la sua spettanza sullo **stesso** schermo; nessun selettore-anno
  che mente (l'anno di competenza è un dato di contesto, non un controllo).
- **Contro**: la card mostra un numero annuale (competenza) accanto a uno
  "alla data" (saldo). È il clash temporale di §4 — ma è **lo stesso clash** che
  la pagina nuova ha internamente (F4), risolto qui con una label onesta
  ("utile maturato nell'anno") invece che con un selettore illusorio.

### Alt-B — Un box nella card "Utile pro-quota" di ContoEconomico
Dove il numero di competenza **già vive** (righe 142-161), aggiungere per il
fratello loggato una frase calcolata: «Spettante 10.002 · in mano 20.000 →
**conguaglio +10.998 (versi)**, dettaglio bonifici in
[Saldi fratelli](/p/saldi-fratelli)».
- **Pro**: il ponte esattamente dove nasce l'ambiguità; una frase, non una
  pagina; deep-link al piano esistente; niente `scarto_timing` esposto.
- **Contro**: restano due pagine (ma è **intrinseco**: i movimenti di denaro
  vivono in SaldiFratelli, il P&L in ContoEconomico; nessuna terza pagina lo
  cambia). Non mostra tutti e tre i fratelli sullo stesso schermo.

### Alt-C — Solo collante: cross-link + una riga per pagina
Il minimo del design (§4, righe 212-214) **senza** la pagina: link bidirezionali
già previsti + una frase-riepilogo calcolata su ciascuna delle due pagine.
- **Pro**: costo quasi nullo, nessun endpoint nuovo, nessuna superficie da
  mantenere; attacca direttamente il "salto a mente".
- **Contro**: i due numeri non sono sullo stesso pixel; per il fratello che
  vuole "una schermata" può non bastare. Ma è il **controllo giusto da provare
  per primo** prima di costruire: se basta, si è risparmiata una pagina.

### Alt-D (scartare) — Grafico invece di tabella
Un waterfall "spettante → cassa netta → conguaglio" per fratello.
- **Pro**: comunica il flusso a colpo d'occhio.
- **Contro**: peggiora la precisione (servono euro esatti per bonificare);
  aumenta il codice; non risolve né F3 né F4. Sconsigliata.

**Ranking del reviewer**: C (prova prima) → B → A → design as-is → D.

---

## Pattern di fallimento noto (mandato §4.5)

**"Unify two views into a third view".** È il pattern classico di
proliferazione-dashboard / violazione single-source-of-truth. Il fallimento
tipico non è matematico (i numeri, riusando le funzioni, coincidono) ma
**cognitivo**: la stessa grandezza mostrata in due cornici diverse genera nel
lettore l'ipotesi che siano due grandezze diverse (F3), e un controllo che non
pilota l'output azionabile insegna all'utente a diffidare dei controlli (F4).
Aggiungere una vista "riassuntiva" a fronte di "due posti da guardare" è la mossa
che *sembra* semplificare e invece aggiunge una superficie di sincronizzazione
in più — nel gestionale reale la superficie in più è poi la cosa che va
riconciliata a mano (precedenti interni citati: `viapal_paginazione_cap_silenzioso`,
`viapal_sbilancio_reale`). La contromisura standard è: **non creare la terza
superficie; portare il dato mancante nella superficie dove l'utente già decide**
(Alt-A/B), o collegarle meglio (Alt-C).

Nota di equità: il **contenuto analitico** del design (§2, la derivazione
cassa vs competenza, lo zero-sum, la regola «derivare da `saldi_live`, non
ricostruire» in §7.3/§8) è solido e va **conservato** — è la parte di valore.
La critica è alla **confezione** (pagina dedicata + selettore + colonne
riconciliative), non alla contabilità.

---

## Verdetto

La matematica è giusta ma la pagina è la risposta sbagliata alla domanda giusta:
il numero azionabile è già tutto in SaldiFratelli, e una terza pagina con un
selettore-anno che non muove i bonifici aggiunge un terzo posto da guardare al
problema "due posti da guardare" — prima di costruirla, provare Alt-C/B (una
frase + link) e portare l'utile di competenza dentro SaldiFratelli.
