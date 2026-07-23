# Reviewer "Correttezza/Algebra Hawk" — ROUND DI DIBATTITO

Review iniziale: 8.5/10 (solidità matematica). Reagisco alle tre posizioni
colleghe dopo aver ri-verificato il codice sui due punti che toccano la mia
algebra (`saldi_live.py:107-176`, `dashboard_views.py:44-55, 392-409`).

---

## Q1 — Il mio zero-sum §2.3 regge nel sistema reale (DEPOSITO + baseline)?

**CONCEDO in gran parte, con una precisazione tecnica che sposta la colpa dove va.**

Prima devo un'ammenda alla mia stessa F2: avevo elencato **due** termini omessi
dalla formula piana (`baseline_settlement`, `bt_inter_owner`). Ne mancava un
**terzo**, ed è quello di ARCHITETTURA F2, che ho ora verificato sul codice:
`rec_qs` in `calcola_saldi_correnti` (`saldi_live.py:107-114`) **non filtra la
causale** → include i Receivable `DEPOSITO`, mentre `bilancio_proprietari`
(`dashboard_views.py:395-396`) filtra `causale__in=CAUSALI_OPERATIVE` che
**esclude DEPOSITO** (commento `:45` esplicito). Quindi la mia
`cassa_netta = I_o − A_o` (universo operativo, no deposito) e la componente
incassi di `−saldi_live.totale` (universo con deposito) girano su insiemi
diversi. In questo dominio è il termine **più probabilmente ≠ 0**: i depositi
si incassano di continuo, i settlement sono rari. Il mio "caso pulito" è quindi
più stretto di quanto scritto: richiede *anche* nessun DEPOSITO pagato nel
periodo. **Ho sottopesato questo. Concedo.**

**Precisazione che contesto nella forma, non nella sostanza.** Ciò che si rompe
NON è la somma-zero della colonna live. Verifico algebricamente: per ogni
Receivable il contributo netto sui fratelli è
`−(1−q_inc)·I + Σ_{o≠inc} q_o·I = −I + q_inc·I + (1−q_inc)·I = 0`
**qualunque sia la causale**. Quindi DEPOSITO **non** perturba
`Σ(−saldi_live.totale) = 0`: la colonna live resta zero-sum e azionabile
(baseline snapshot somma a zero se il settlement era quadrato; le BT inter-owner
sono l'unico termine che può sbilanciare, e lì c'è `verifica_quadratura`).

Ciò che si rompe è la **riconciliazione ORIZZONTALE della riga**: la formula
stampata `cassa_netta − q·utile_cassa` **≠** `−saldi_live.totale` non appena
deposito/baseline/BT ≠ 0. Cioè: la mia identità §2.3 **come identità piana è
falsa nel sistema reale**; come descrizione dell'oggetto `saldi_live.totale`
regge. È esattamente ARCHITETTURA F1 ("la riga non chiude la propria
aritmetica") e ci concordo. La correzione richiesta: non stampare mai la
formula piana come derivazione del conguaglio; l'azionabile è l'oggetto opaco
`−saldi_live.totale` (che i tre termini li contiene già).

## Q2 — Il mismatch di periodo: ancora "solo" P1?

**NO. Lo promuovo a difetto strutturale (P0 per la colonna azionabile su anni
chiusi).** La mia F4 lo aveva già isolato come "il più insidioso", ma l'avevo
graduato P1 perché lo leggevo come tensione mascherata dall'esempio. ARCHITETTURA
F3 ha ragione sul salto di livello: ho verificato che `calcola_saldi_correnti`
accetta **solo `at_date`** e il `periodo_da` è imposto da `_ultimo_settlement`
(`:67-71`), non parametrizzabile. Non è imprecisione: per un anno **chiuso**,
`?anno=YYYY` restituirebbe il piano **live a oggi** del periodo aperto — un
numero di un altro periodo, etichettato con l'anno sbagliato. Un importo
azionabile che appartiene a una finestra diversa da quella mostrata non è "P1
mascherato dall'esempio": è **non azionabile per costruzione**. La firma va resa
period-aware, oppure la colonna azionabile va confinata al solo periodo aperto
corrente (anni chiusi read-only da snapshot `OwnerSettlement`). Concedo ad
ARCHITETTURA.

## Q3 — Verso il DEVIL: la mia §2 giustifica una pagina nuova?

**Do ragione al DEVIL, e c'è un'ironia: la mia stessa algebra indebolisce il
caso per la pagina nuova.** Avendo verificato che l'azionabile *è* esattamente
`−saldi_live.totale` (già esposto in `SaldiFratelli`) e che il `piano_rientro`
è già `calcola_piano_rientro` (già esposto), il mio §2 non produce **nessun
numero azionabile nuovo**. Produce una **decomposizione esplicativa**: perché
la cassa ≠ la tua quota di utile (lo `scarto_timing` = competenza non ancora
incassata + incassi cross-anno, cfr. mia F7). È valore **pedagogico/informativo,
non operativo**. Un valore reale — risponde alla domanda di Fabio "perché il mio
conguaglio di cassa non è la mia fetta di utile?" — ma non richiede una terza
superficie. Concordo col DEVIL: **esporre il ponte cassa↔competenza dove i
bonifici già vivono** (colonna/box in `SaldiFratelli`, o box in
`ContoEconomico`) domina l'aggiunta di una pagina. Rispondere a "due posti da
guardare" con un terzo posto è il difetto che il DEVIL nomina correttamente.

Non arrivo al suo 4/10 perché la matematica sottostante **è** corretta e il
ponte competenza ha valore genuino; ma il *contenitore* proposto (pagina nuova
per-anno) non è giustificato dalla mia analisi.

## Q4 — Recuperabile o da sostituire?

**RECUPERABILE come DATI/algebra; da SOSTITUIRE come framing ("pagina nuova
per-anno").** L'algebra non va buttata: le derivazioni §2.2/§2.4 restano
corrette e il ponte scarto_timing è utile. Va buttata la confezione. Fix in
ordine di priorità:

1. **(P0) Sciogliere il nodo periodo.** Colonna azionabile = **solo periodo
   aperto live**, nessun selettore anno su di essa; anni chiusi read-only da
   snapshot `OwnerSettlement`. (Alternativa più costosa: rendere `saldi_live`
   period-aware con `periodo_da/periodo_a`.) Senza questo, ogni anno ≠ periodo
   aperto è un numero sbagliato.
2. **(P0) Non stampare la formula piana come derivazione.** L'azionabile è
   `−saldi_live.totale` (opaco, include baseline+BT+**deposito**). Separare il
   blocco **competenza/anno** (informativo) dal blocco **conguaglio/live**
   (azionabile) — allineato ad ARCHITETTURA F5(B).
3. **(P1) Allineare gli universi-sorgente** (mia F5): non mescolare
   `ContoEconomico` (senza filtro causale/owner) con `bilancio_proprietari`
   (filtrato). O derivare tutto da `saldi_live`, o dichiarare esplicitamente
   dentro/fuori DEPOSITO e perché.
4. **(P1, DEVIL) Riconsiderare il contenitore.** Prima di costruire una pagina,
   valutare un box "conguaglio + perché (ponte competenza)" dentro
   `SaldiFratelli`. Probabile che domini per costo/beneficio.

---

## Punteggio aggiornato: 7.0 / 10 (era 8.5)

**Mi sposto, e dico perché — non per accodarmi.** La mia arma era la
"solidità matematica" e l'aritmetica che ho verificato **resta corretta** (non
ritratto una cella). Ma il dibattito ha esposto due cose che il mio 8.5
sottopesava:

1. **Un buco di completezza nella MIA review**: la mia F2 elencava 2 termini
   omessi dall'identità; ne mancava un terzo (DEPOSITO), che in questo dominio
   è il più probabilmente non-nullo. Il "caso pulito" in cui la mia identità
   vale è più raro di quanto avessi scritto → un 8.5 su un design il cui *punto
   di forza è quell'identità* era generoso.
2. **Il difetto di periodo è strutturale, non P1.** Un azionabile della finestra
   sbagliata non è imprecisione.

Non scendo al 4 del DEVIL/FABIO perché l'algebra è genuinamente corretta e il
ponte cassa↔competenza ha valore reale: il problema è **framing e scoping**, non
i numeri. 7.0 riflette matematica solida ma presentata dentro una cornice
(identità piana + colonna per-anno) che non sopravvive al sistema reale.

**Posizione finale: RECUPERABILE** (algebra) **/ da riconfezionare** (drop
pagina-nuova-per-anno).
