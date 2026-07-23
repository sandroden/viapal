# Reviewer — Comprensibilità per non-contabile (Fabio)

Persona: Fabio, uno dei 3 fratelli proprietari. NON commercialista. Leggo dal
telefono (PWA). Cold first-read, alta intensità critica: se non è cristallino
per me, è un difetto del design.

## Punteggio comprensibilità (0-10, non-contabile): **4/10**

Il prospetto è tecnicamente ineccepibile e onesto (lo scarto di timing non viene
nascosto sotto il tappeto), ma è costruito per chi già sa cosa cerca. Da telefono,
in <30 secondi, NON arrivo con sicurezza al numero che mi interessa, e due scelte
(segno del conguaglio + disallineamento tabella-annuale / bonifico-live) rischiano
di farmi versare o aspettare l'importo sbagliato.

---

## Findings

### P0 — Non c'è "IL MIO numero". Devo cercarmi la riga tra tre
**Mockup: tabella righe 164-192, KPI righe 138-142.**
Atterro sulla pagina per sapere UNA cosa: «io, Fabio, per il 2026 devo versare o
ricevere, e quanto?». La pagina invece mi mostra prima 3 KPI dell'immobile
(30.000 / 27.000 / −3.000 — che NON sono soldi miei) e poi una tabella con tutti
e tre i fratelli. Devo scorrere, trovare la riga "Fabio", leggere l'ultima
colonna. Su un immobile con 3 proprietari passi ancora; il punto è che la
gerarchia visiva mi porta prima ai numeri dell'immobile e poi mi lascia cercare
me stesso. Manca un blocco grande, in cima, tipo: **"Fabio — per il 2026 RICEVI
5.999,10 €"**. Quello è il 90% del motivo per cui apro la pagina.

### P0 — Il segno è contro-intuitivo: numero NEGATIVO = ricevo (buono)
**Mockup: col. Conguaglio, righe 172 / 181 / 190.**
La mia riga dice **`−5.999,10 riceve`**. Un numero col meno davanti, per me che
non sono contabile, urla "sei in rosso, sei sotto". Invece significa che INCASSO
soldi. E Alessandro ha `+10.998,20 versa`: numero positivo = deve pagare. È
esattamente rovesciato rispetto all'istinto (positivo = ho, negativo = devo). Il
colore aiuta (verde/rosso) ma il segno combatte contro il colore. Se leggo di
fretta il solo numero, capisco il contrario. Togliete il segno dalla cella
"azione" e lasciate parola + colore: **"RICEVI 5.999,10 €"** in verde, **"VERSI
10.998,20 €"** in rosso. Il segno con lo zero-sum tenetelo nel totale/verifica,
non nella cella che l'utente legge per agire.

### P0 — Contraddizione tabella-annuale vs bonifico-live: rischio importo sbagliato
**DESIGN.md §5.2 (righe 244-249), §7.4 (righe 340-343); mockup piano righe 223-235.**
Questa è la trappola vera. La tabella dice che io per il 2026 devo **ricevere
5.999,10**. Sotto, il "piano di rientro" dice: Alessandro → Fabio **5.999,10**.
Nel mockup coincidono, e quindi sembra tutto liscio. Ma il DESIGN dice
esplicitamente che il piano NON è annuale: è di **cassa live sul periodo aperto**,
che può includere PIÙ anni (§7.4: "i bonifici azzerano il dovuto di cassa a oggi,
che può includere anni non ancora chiusi"). Quindi in un caso reale la colonna
"Conguaglio 2026" e il bonifico sotto **saranno numeri diversi**, sulla stessa
pagina, sotto lo stesso titolo "Conguaglio fratelli". Da Fabio: quale dei due è
quello che aspetto sul conto? Se guardo la tabella dell'anno e aspetto 5.999 ma
il bonifico reale è 8.200 (perché include il 2025 non chiuso), penso ci sia un
errore, o peggio ne verso/ne pretendo la cifra sbagliata. Il mockup, scegliendo
numeri che coincidono, **nasconde** proprio il rischio dichiarato nel design.
Serve, ben visibile: (a) numeri d'esempio in cui i due NON coincidono, e (b) una
frase in chiaro tipo "La tabella è il conto dell'anno 2026. I bonifici qui sotto
saldano tutto il dovuto ancora aperto (anche di anni precedenti): per questo
l'importo può essere diverso." Oggi quella spiegazione è sepolta nella foot-note
righe 236-241 in grigio piccolo, e parla di `calcola_piano_rientro` e
`saldi_live.totale` — roba che io non so cosa sia.

### P1 — "Scarto di timing" non mi dice niente
**Mockup: KPI riga 141, colonna righe 158/171/180/189, nota righe 205-215.**
"Timing" è inglese e "scarto" sa di errore/scarto di produzione. Da Fabio leggo
"scarto di timing −999,90" e penso: ho perso mille euro? è un ammanco? La nota lo
spiega ("ricavi già maturati ma non ancora incassati... si riassorbe da solo") ed
è una buona spiegazione — ma la nota contiene `quota × (utile_cassa −
utile_competenza)` in `<code>`, e lì ho già smesso di leggere. Proposta: nome in
italiano piano, tipo **"Ricavi maturati ma non ancora incassati"** o **"In
attesa di incasso"**, e la formula fuori dalla vista dell'utente. E soprattutto:
è una colonna che a me, per decidere quanto versare, NON serve. Nascondetela in
un "mostra dettaglio" così la riga principale resta pulita.

### P1 — Troppe colonne che si assomigliano: le confondo comunque
**Mockup: 5 colonne (Fratello, Utile spettante competenza, Cassa netta, Scarto,
Conguaglio).**
Il mandato chiedeva di distinguere 4 grandezze. La pagina le mette tutte in fila,
tutte in euro, tutte con font uguale. "Utile spettante 9.999" e "Cassa netta
3.000" e "Conguaglio −5.999": tre numeri grossi vicini, e io non ho un motivo
visivo per capire quale è "quello da guardare". Sì, l'ultima colonna è in
grassetto (`col-conguaglio`, riga 79) e ha il badge — ma le altre due colonne
competono. Su telefono poi la tabella ha `min-width:640px` (riga 70) e scrolla in
orizzontale: la colonna Conguaglio, quella che conta, è l'ultima a destra, quindi
sul telefono è **fuori schermo** all'apertura. Vedo per prime le colonne che mi
servono meno. Questo è mezzo P0 in versione mobile.

### P1 — Distinguo davvero competenza vs cassa? A metà.
Onestà del design: sì, i concetti sono separati e etichettati, e lo scarto di
timing è la riga che tiene onesta la tabella — apprezzabile. Ma per me restano
due parole tecniche. "Utile spettante (competenza)" = quanto ho guadagnato sulla
carta; "Cassa netta" = quanto ho materialmente preso in mano. Se me le spieghi
così, a parole, le capisco. Le etichette attuali "(competenza)" e
"(incassato − anticipato)" mi lasciano indovinare. La confusione storica cassa/
competenza non è ridipinta — è affrontata — ma è affrontata col vocabolario del
commercialista, non col mio.

### P2 — Il banner verde è rassicurazione in linguaggio tecnico
**Mockup: righe 133-135.** "Conguaglio di cassa quadrato: la somma fa zero e ogni
movimento ha un responsabile." Da Fabio: "somma fa zero" e "ogni movimento ha un
responsabile" non mi dicono che va tutto bene, mi fanno pensare che debba
verificare qualcosa. Un "✓ I conti tornano" basterebbe.

### P2 — I 3 KPI dell'immobile in cima rubano la scena
**Mockup: righe 138-142.** Sono i primi numeri grandi che vedo, e sono i meno
azionabili per me (sono dell'immobile, non miei). Metterli DOPO il mio esito
personale, o più piccoli.

### P2 — "di cui incassato / anticipato" come sub-valore è criptico
**Mockup: righe 168-169 `25.000,00 − 5.000,00`.** Un'operazione senza etichetta
sotto il numero. Capisco che 20.000 = 25.000 − 5.000, ma non cosa siano i due
addendi finché non leggo l'header a fondo colonna. Su mobile con header scrollato
via, è un rebus.

### P3 — Cosa chiederei ad Alessandro (che tiene i conti)
1. "Perché il mio conguaglio è col meno se devo ricevere?"
2. "La tabella dice 2026 ma il bonifico sotto è di un altro importo — qual è
   quello giusto?" (se i numeri divergono, come dice il design)
3. "Cos'è lo scarto di timing, ho perso dei soldi?"
4. "Questi 30.000 in cima sono utili di tutti o miei?"
Tutte e quattro sono domande che il design dovrebbe prevenire, non generare.

---

## Verdetto

Contabilmente rigoroso e onesto, ma pensato per chi già conosce il gergo: manca
il mio esito personale in cima, il segno del conguaglio è rovesciato rispetto
all'istinto, e la tabella-annuale può contraddire il bonifico-live sotto senza
avvisarmi — così com'è, da telefono rischio di capire o versare il numero
sbagliato.
