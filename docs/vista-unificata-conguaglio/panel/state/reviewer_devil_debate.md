# Reviewer "Devil's Advocate" — ROUND DI DIBATTITO

Reazione alle posizioni dei colleghi (Algebra 8,5 · Architettura 6,5 ·
Fabio-non-contabile 4). La mia review di fase 3 chiudeva 4/10: la matematica
del §2 è giusta ma la **confezione** (terza pagina + selettore-anno + colonne
riconciliative) è la risposta sbagliata alla domanda giusta.

Il dibattito NON mi ha spostato di molto, ma mi ha stretto il perimetro: la mia
critica converge quasi letteralmente con Architettura e Fabio. Sotto, punto per
punto.

---

## Punto di convergenza: siamo d'accordo in tre su quattro

Questo è il dato saliente del round. Tolta Algebra (che valuta **solo** la
matematica e per statuto non giudica la confezione), gli altri due reviewer
"di prodotto" — Architettura e Fabio — arrivano, da porte opposte, alla **mia**
conclusione:

- **Architettura (F1, F5)**: «il design non ha risolto la scelta tra base
  "anno" e base "live"; le espone entrambe nella stessa riga con una formula
  che riconcilia solo nel caso degenere». È il mio F4 (il selettore-anno che
  mente) e il mio F3 (il piano duplicato) detti in linguaggio di dati anziché
  di UX. **Conferma esplicita** (F1 chiusa) che «i dati azionabili vivono già
  in SaldiFratelli».
- **Fabio (P0 "contraddizione tabella-annuale vs bonifico-live")**: la stessa
  cosa vista dal telefono — «quale dei due numeri aspetto sul conto?». È il mio
  F4 dal lato dell'utente.
- Entrambi indipendentemente segnalano il **foot-gun `conguaglio_competenza`**
  (mio F6, loro Fabio-P1/Arch-F9) e le **troppe colonne** (mio F5, Fabio-P1).

Tre reviewer su quattro, con metodi diversi (backward-reasoning architetturale,
cold-read non-contabile, analogia adversariale), colpiscono lo **stesso** punto:
la riga vuole essere insieme "anno" e "live" e non può. Questa non è una
coincidenza — è il segnale che il difetto è **strutturale**, non cosmetico.

---

## Q1 — Concedo che l'INSIGHT vada mostrato e critico solo la CONFEZIONE?

**Concedo — con una condizione, non incondizionatamente.**

Concedo il primo pezzo, e l'ho già scritto in fase 3 (nota di equità, righe
209-213: «il contenuto analitico del §2 è solido e va conservato — è la parte di
valore»). Su questo Algebra ha ragione e non c'è dibattito: la relazione
competenza-vs-cassa e lo zero-sum sono corretti e **un** posto dove vederli
migliora la comprensione del fratello che *vuole* capire perché "ho guadagnato
10.002 ma ne verso 10.998".

Ma il "da qualche parte" non è neutro, ed è qui che tengo il punto contro
Algebra. Algebra dice «il difetto è lo scoping di periodo, non la matematica» —
vero per la matematica, ma lo scoping di periodo **è** un difetto della
confezione: nasce dall'aver messo competenza (per-anno) e cassa (live) sulla
stessa riga con un selettore unico. Cambia il contenitore e il difetto di
scoping **evapora**: se l'utile di competenza è un box informativo accanto al
saldo live, non c'è nessun selettore-anno da riconciliare col piano live, e
quindi nessuno scarto di timing da esporre per "tenere onesta la tabella".

Quindi: **sì, la mia critica è alla confezione — ma la confezione genera il
difetto matematico-di-scoping che Algebra stessa segnala.** Non sono due
problemi separabili. Il §2 è vero; il §3/§4/§5 (tabella + selettore + shape) è
la parte che trasforma una verità in una superficie che non riconcilia.

**Dove NON concedo**: che l'utile di competenza *accanto* serva **al fratello
che vuole solo sapere quanto versare**. Per quel fratello (che è il 90% degli
accessi, cfr. Fabio-P0 "il mio numero") la competenza è rumore: guarda una
cella e bonifica. L'insight di competenza serve a un **secondo** bisogno
("perché quella cifra?"), legittimo ma minoritario, e per quello basta un box a
richiesta, non una pagina che lo mette in prima fila.

---

## Q2 — Quale UNA alternativa raccomando come sostituto concreto

**Box in ContoEconomico (la mia Alt-B), come mossa singola.** Se il team vuole
UNA cosa sola, è questa.

Ragionamento (allineato ad Architettura F1 e a Fabio P0):

- L'unico numero azionabile (`−saldi_live.totale`) e la sua azione (piano di
  rientro) **esistono già interi** in SaldiFratelli — confermato da
  Architettura. Lì non manca nulla di azionabile: al più manca una **label**
  ("questo è quanto versi/ricevi a oggi").
- L'unico *delta informativo* del design — l'utile di competenza pro-quota
  accanto alla cassa — nasce concettualmente in **ContoEconomico**, dove la card
  "Utile pro-quota" già vive (righe 142-161) e già ha un cross-link verso Saldi.
- Quindi il ponte va messo dove nasce l'ambiguità: nella card di ContoEconomico,
  una frase calcolata per il fratello loggato — «Spettante (competenza) 10.002 ·
  in mano (cassa) 20.000 → a oggi **versi ~10.998**, dettaglio e bonifici in
  [Saldi fratelli]». Deep-link al piano **live** esistente.

**Cosa perde rispetto al design:**
1. Non mostra i tre fratelli sullo stesso schermo (il design sì). Perdita reale
   ma minore: ogni fratello vede il **suo** esito, che è ciò che chiede (Fabio-P0).
2. Non c'è la colonna `scarto_timing` esplicita. Non è una perdita: è il punto
   (mio F5) — lo scarto serviva a far quadrare la tabella, non all'utente.
3. Restano due pagine. Ma — come ho scritto in Alt-B — è **intrinseco**: i
   movimenti vivono in Saldi, il P&L in ContoEconomico; nessuna terza pagina lo
   cambia, anzi ne aggiunge una quarta cosa da guardare.

Perché B e non A (colonna in SaldiFratelli): A mette un numero **annuale**
(competenza) accanto a uno **live** (saldo) nella stessa card — reintroduce in
piccolo il clash temporale. B tiene la competenza nel suo habitat annuale
(ContoEconomico) e da lì punta al live. B è quella che sposa meglio la tesi di
Architettura F5 (separare le due basi in due blocchi/luoghi distinti).

Perché non il solo cross-link (Alt-C): resta il candidato "prova-prima" più
economico, ma Fabio ha ragione che un link nudo non dà "il mio numero". B
aggiunge la **frase calcolata** che C non ha, al costo di poche righe.

---

## Q3 — Se costruiscono comunque la pagina, il minimo per NON peggiorare

Se il verdetto del giudice è "si fa la pagina", ecco il floor perché non
aumenti la confusione. Recepisce Architettura-F5 e Fabio-P0/P1:

1. **Una sola base per l'azionabile: LIVE.** La pagina mostra `−saldi_live.totale`
   e il piano di rientro **del periodo aperto**, etichettato "dovuto a oggi".
   Niente selettore-anno che pilota l'azionabile (uccide il mio F4 e la P0 di
   Fabio).
2. **Il "mio numero" in cima, senza segno, parola+colore**: «Fabio — a oggi
   RICEVI 5.999 €» (Fabio-P0 segno + P0 mio-numero). I 3 KPI d'immobile sotto,
   più piccoli.
3. **Competenza = contesto, non colonna azionabile.** Utile di competenza e
   scarto di timing **fuori** dalla riga principale: in un box "perché questa
   cifra?" collassato / tooltip. Lo `scarto_timing` NON in prima pagina.
4. **`conguaglio_competenza` fuori dai sibling azionabili** nel JSON: annidato
   sotto `informativo`, mai colonna (mio F6, Arch-F9).
5. **Se proprio si tiene un selettore-anno**, esso pilota SOLO il blocco
   competenza/contesto, ed è **visivamente separato** dal blocco "dovuto a oggi"
   (Arch-F5, blocchi distinti), con una frase che avverte che i bonifici saldano
   anche anni aperti precedenti (Fabio-P0).

In una riga: **spezzare in due blocchi (live-azionabile in alto, competenza-
contesto in basso), un solo numero personale senza segno in cima, scarto e
conguaglio_competenza declassati a dettaglio.** Se il team fa questi cinque, la
pagina degrada da "peggiora" a "ridondante ma innocua".

---

## Q4 — Punteggio finale: resto a 4 o mi muovo?

**Mi muovo, ma di poco: 4 → 4,5.**

Perché mi muovo:
- Il dibattito ha **rafforzato**, non indebolito, la mia diagnosi centrale: due
  reviewer di prodotto indipendenti convergono sul difetto strutturale
  (anno-vs-live) e uno conferma che l'azionabile è già tutto in SaldiFratelli.
  Un difetto trovato da tre angolazioni merita mezzo punto in meno al design,
  non in più — ma ai fini del **mio** score misuro "quanto è giustificato
  costruire QUESTO design così com'è", e resta basso.
- Concedo però ad Algebra che il **valore analitico da preservare** è più alto
  di quanto un 4 secco suggerisca: c'è un insight reale (il ponte competenza-
  cassa) che una mia lettura troppo distruttiva rischiava di buttare col design.
  Riconoscere che quell'insight **va mostrato** (in Alt-B) alza di mezzo punto
  la mia stima del *nucleo salvabile*.

Perché NON mi muovo di più (resto lontano da Architettura 6,5 e Algebra 8,5):
- Architettura dà 6,5 sulla "solidità architetturale" e Algebra 8,5 sulla
  "matematica": stanno misurando **assi diversi dal mio**. Io misuro la
  giustificazione del **manufatto proposto**. Sugli assi loro sono d'accordo con
  loro (la matematica è 8,5, il refactor è fattibile). Ma il manufatto — pagina
  + selettore + colonne — resta la risposta sbagliata: aggiunge un terzo posto
  al problema "due posti", e la fix che tutti propongono (spezzare in due
  blocchi, rendere period-aware) **è di fatto ri-progettare la pagina**, non
  ritoccarla. Un design che per essere accettabile va riscritto nella sua forma
  non merita la sufficienza.
- Fabio resta a 4 e sul piano dell'esperienza utente ha ragione: da telefono,
  così com'è, si versa il numero sbagliato. Questo è un rischio **operativo su
  soldi veri**, non un fastidio estetico. Pesa verso il basso.

**4,5/10.** Il nucleo analitico è oro (concessione ad Algebra); la confezione
resta la mossa sbagliata (nessuno l'ha difesa: Architettura vuole spezzarla,
Fabio la trova illeggibile, Algebra non la giudica). Prima di costruire la
pagina, provare Alt-B.

---

## Posizione finale (sintesi)

L'analisi del §2 va conservata e mostrata — **una volta**, come box informativo
in ContoEconomico che ponte-linka al piano live di SaldiFratelli (Alt-B). La
terza pagina con selettore-anno non va costruita così: il round ha mostrato che
per renderla corretta va spezzata in due basi temporali — cioè riprogettata —
e che l'unico numero azionabile è già interamente in SaldiFratelli. Se il
giudice la impone comunque, floor obbligatorio: una base live, il mio numero
senza segno in cima, competenza e scarto declassati a contesto.
