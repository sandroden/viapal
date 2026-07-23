# Reviewer — Comprensibilità per non-contabile (Fabio) — ROUND DIBATTITO

Persona: Fabio, uno dei 3 fratelli proprietari. NON commercialista. Leggo dal
telefono. Ho letto i colleghi. Reagisco da utente, non da contabile.

Review di partenza: **4/10** (manca "il mio numero" in cima; segno rovesciato;
contraddizione annuale-vs-live nascosta dal mockup; "scarto di timing" è gergo;
mobile rotto).

---

## Cosa mi hanno insegnato i colleghi (e cosa non cambia per me)

**ALGEBRA (8,5)** dice che la matematica è giusta e che lo scarto di timing è un
concetto reale. Ci credo. Ma "reale e corretto" non è la mia metrica: la mia è
"lo capisco in 20 secondi dal telefono senza chiamare Alessandro". Un numero può
essere esatto al centesimo e restare, per me, un rebus. Anzi, la sua F4 (finestra
anno ≠ finestra live) e la sua F8 ("esempio cherry-picked, i numeri coincidono
apposta") sono la **prova tecnica** del mio P0 sulla contraddizione: gli esperti
confermano che nel caso reale i due numeri divergeranno. Il mockup mi ha mostrato
il caso fortunato. Quindi il mio 4 non sale per merito dell'algebra: sale semmai
se accettano di **mostrarmi un esempio dove NON coincidono**, che è esattamente
quello che chiedevo.

**ARCHITETTURA (6,5)**: propone due blocchi separati (competenza/anno vs
conguaglio/live) e `saldi_live` period-aware. Da utente questo mi piace **molto
più** di quanto pensassero: separare visivamente "quanto hai guadagnato" da
"quanto ti muovi adesso" è precisamente il modo di togliermi la trappola. Se i
due numeri sono in due riquadri distinti con due titoli onesti, non li confondo.
La confusione nasceva dal metterli **sulla stessa riga** facendo credere che uno
discenda dall'altro.

**DEVIL (4)**: dice che forse non serve una pagina nuova, basta una colonna in
SaldiFratelli o un box in ContoEconomico. Da utente **sono d'accordo al 90%**.
Io non voglio "una pagina in più"; voglio il numero **dove già guardo**. Tre
posti sono peggio di due. La sua Alt-B ("Spettante 10.002 · in mano 20.000 →
versi 10.998, dettaglio in Saldi fratelli") è scritta nella mia lingua: è
letteralmente la frase che vorrei leggere. Il suo unico punto debole, per me, è
che io a volte voglio vedere **tutti e tre i fratelli** insieme (per capire se il
piano è equo), e un box "solo per me" non lo dà. Ma quello è un di-più, non il
must-have.

---

## Risposte alle domande

### 1. Lo "scarto di timing": vederlo o no? E come lo chiamo?

**Non voglio vederlo come colonna.** Da utente non ci faccio niente: non è un
numero che bonifico. Mi basta la frase che dicono ALGEBRA e DEVIL messa in
italiano: **"hai guadagnato X, in mano ne hai Y, la differenza arriva quando gli
inquilini pagano"**. Il concetto è utile *come spiegazione*, non come cella.

Se proprio deve avere un nome (in un "mostra dettaglio"), NON "scarto di timing"
(sa di ammanco/errore di produzione, e "timing" è inglese). Lo chiamerei:
- **"In attesa di incasso"** oppure
- **"Maturato ma non ancora incassato"** oppure, ancora più piano,
- **"Soldi già tuoi, non ancora sul conto"**.

Gli esperti hanno ragione che il concetto serve; ma serve *spiegato a parole*,
non *quantificato in una colonna* che compete con quella che devo guardare.

### 2. Numero annuale storico o "quanto bonifico ADESSO"? Uno o entrambi?

Le voglio **entrambe, ma non con lo stesso peso e MAI adiacenti senza etichetta**.

- Quello che apro l'app per sapere è **"quanto devo bonificare ADESSO"**. Questo
  è IL numero. Grande, in cima, con verbo (versi/ricevi) e colore.
- Il numero annuale ("nel 2026 il tuo conguaglio è stato X") lo voglio come
  **contesto/storico**, più piccolo, sotto, chiaramente etichettato come "conto
  dell'anno" e non come "da pagare".

La trappola da evitare (il mio P0) è metterli vicini, uguali di dimensione, sotto
lo stesso titolo, così che io non sappia quale aspettare sul conto. La soluzione
di ARCHITETTURA (due blocchi separati) è giusta **a patto** che quello azionabile
sia visibilmente il capo e l'altro sia dichiarato "storico/informativo". Serve
una frase esplicita tipo: *"Questo è il conto dell'anno 2026. Il bonifico qui
sotto salda tutto il dovuto ancora aperto, anche di anni prima: per questo può
essere diverso."*

### 3. Pagina nuova "Conguaglio <anno>" o il numero dove già guardo?

**Il numero dove già guardo.** Netto. Non voglio una terza pagina.

Concordo con DEVIL: il problema era "due posti", una terza pagina fa tre. Per me
il posto naturale è **Saldi fratelli**, perché lì c'è già "chi versa a chi" —
cioè l'azione. Ci aggiungo la spettanza di competenza come contesto (Alt-A) o la
frase-ponte di Alt-B. Una pagina "Conguaglio 2026" a sé la aprirei una volta e
poi non ricorderei se la verità è lì o in Saldi fratelli. Meno superfici, meno
dubbi.

Unica riserva: se la scelta è "box solo-per-me", voglio comunque un modo di
vedere **tutti e tre** (per capire se il piano è equo). Va bene un'espansione,
non una pagina nuova.

### 4. I 3 must-have (in ordine)

1. **IL MIO numero, in cima, in italiano con verbo e colore**: *"Fabio — adesso
   VERSI / RICEVI 5.999,10 €"*. Niente segni matematici nella cella che leggo per
   agire (il "−5.999,10 riceve" è contro-istinto: meno = credo di essere in
   rosso). Parola + colore, il segno tenetelo nei totali di verifica.
2. **Un solo numero azionabile, senza contraddizioni**: "quanto bonifico adesso"
   deve essere inequivocabile e coincidere con "chi versa a chi". Se il numero
   dell'anno è diverso da quello che bonifico, ditemelo con una frase, non
   lasciatemelo scoprire. (Questo copre il mismatch che ALGEBRA/ARCHITETTURA
   confermano essere reale.)
3. **Il resto come contesto, non come colonne**: guadagnato-vs-in-mano e "in
   attesa di incasso" come **frase** o dietro un "mostra dettaglio"; e deve
   funzionare **sul telefono** (oggi la colonna che conta è l'ultima a destra,
   fuori schermo — inaccettabile).

---

## Punteggio aggiornato: **5/10** (da 4)

**Perché sale di 1, non di più.** Sale perché il dibattito ha portato in tavola
la cura che rende la vista comprensibile: ARCHITETTURA (due blocchi separati,
period-aware) e DEVIL (portare il numero dove già guardo, frase invece di
colonna) sono esattamente ciò che serve a un non-contabile, e ALGEBRA ha
**confermato tecnicamente** che il mockup nascondeva il caso critico — dandomi
ragione sul rischio, non torto.

**Perché non oltre 5.** Sono proposte, non ancora nel design. Il documento *as
is* mi fa ancora atterrare su 3 KPI dell'immobile, cercarmi nella tabella, leggere
un "−5.999 riceve" contro-istinto, e rischiare di aspettare il numero sbagliato
sul conto — su un telefono dove la colonna giusta è fuori schermo. Finché il
mockup mostra il caso fortunato in cui tutto coincide, per me il difetto di
comprensibilità resta. Salgo a 7+ solo quando vedo: il mio numero in cima con
verbo+colore, un esempio in cui annuale e live NON coincidono con la frase che lo
spiega, e lo scarto declassato da colonna a frase.
