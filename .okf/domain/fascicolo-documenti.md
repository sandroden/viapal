---
type: Domain Logic
title: Fascicolo documenti
description: "Elenco dei documenti dell'inquilino con stati derivati (valido/in scadenza/scaduto), servito a inquilino e proprietario dallo stesso servizio. Nessun documento è obbligatorio e nessuna voce è vuota: compare solo ciò che esiste. Include chi vede le carte della casa, che dal 2026-08-06 dipendono dal contratto."
resource: backend/apps/properties/fascicolo.py
tags: [domain, documenti, inquilini, frontend]
timestamp: 2026-08-06T00:00:00Z
---

# Overview

`TenantDocument` è un elenco piatto di file: risponde a «quali documenti ci
sono», non a «cosa manca e cosa scade». Il **fascicolo** è la vista derivata
che risponde alla seconda domanda: raggruppa i file per *tipo* e calcola lo
stato di ogni voce.

Il calcolo sta **solo** nel backend (`properties/fascicolo.py`) e alimenta
tutte le interfacce: area inquilino (`/i/documenti`) e tab "Documenti" della
scheda inquilino lato proprietario. Due UI, una sola definizione di "in
scadenza".

# Stati

| Stato | Quando |
|-------|--------|
| `ok` | caricato, senza scadenza o con scadenza lontana |
| `scadenza` | scade entro `GIORNI_PREAVVISO_SCADENZA` (**60 giorni**) |
| `scaduto` | `data_scadenza` passata |

Lo stato di una voce con più file è il **peggiore** delle sue pagine
(`scaduto` > `scadenza` > `ok`).

**Nessun documento è obbligatorio** (decisione del 2026-08-01): non esiste uno
stato "mancante" e il fascicolo non misura la completezza. Le copie servono per
il contratto e le utenze, e dopo la verifica possono essere cancellate — meno
dati conservati, meno rischio.

**Nessuna voce è vuota** (2026-08-03): il fascicolo elenca i file che
esistono e basta. Anche i due documenti che produce l'applicazione sono
spariti dall'elenco finché non li si genera — vedi *Documenti generati* più
sotto. Con loro sono spariti lo stato `attesa`, il flag
`a_carico_proprieta` e il predicato `applicabile`, che servivano solo a
decidere *quali* voci vuote mostrare.

# Voci dell'elenco

`VOCI` in `fascicolo.py` dà l'**ordine** dei tipi e, per i due documenti
generati, il codice del generatore (`generabile`) che la UI usa per offrire
"Rigenera" su un PDF già prodotto. Ogni tipo compare solo se ha almeno un
file; `altro` resta fuori dal raggruppamento, con ogni file voce a sé in
`altri`.

`ricevuta_registrazione` = "Registrazione contratto subentro", la ricevuta
telematica che l'agenzia rilascia registrando il contratto (2026-08-01).
Copre anche il subentro: è un adempimento successivo sullo stesso contratto,
non riceve estremi propri e quindi non è un documento diverso. Il tipo
`ricevuta_subentro`, che diceva la stessa cosa, è stato fuso qui dalla
migrazione `0032` (2026-08-03).

**L'atto di subentro delle utenze non è più qui** (2026-08-03): riguarda
l'immobile, non la persona, e semmai va fra i documenti della casa. La
migrazione `0033` toglie il tipo `atto_subentro` e declassa i file già
caricati ad `altro`, conservandone il nome nella descrizione.

I `suggerimento` descrivono il documento e nient'altro: lo stesso payload
alimenta entrambe le UI.

# Pagine (fronte/retro)

Senza modifiche allo schema: più `TenantDocument` dello stesso `tipo` sono
le **pagine** di un unico documento, etichettate con `descrizione`
("fronte"/"retro"). Il tipo `altro` è escluso dal raggruppamento — due file
non correlati non devono fondersi in una voce sola.

# API

`GET /api/v1/tenant-documents/fascicolo/`

- inquilino: il proprio fascicolo;
- gestione: `?tenant=<id>` obbligatorio, limitato all'immobile attivo
  (`X-Property-Id`); 400 senza parametro, 404 su inquilino di altro immobile.

Payload: `voci[]`, `altri[]`, `riepilogo` (conteggi per stato +
`da_sistemare` = scaduti + in scadenza). Ogni voce porta `pagine[]` con `file`
(URL `/media-private/…`), `etichetta`, `is_pdf`, e `generabile` (codice del
generatore o `null`, per il "Rigenera").

`GET /api/v1/tenant-documents/generabili/?tenant=<id>` (`IsPropertyMember`)
elenca invece **cosa si può produrre**: `codice`, `titolo`, `tipo`,
`tipo_display` e `esistente` (il PDF già generato, se c'è). Da quando il
fascicolo non mostra più voci vuote, senza questo elenco non ci sarebbe
modo di scoprire quali documenti l'applicazione sa fare. È una GET — non
produce nulla — così anche `sola_lettura` vede l'elenco, mentre generare
resta una POST vietata a quel ruolo.

# Visualizzazione

I documenti si aprono **dentro l'app**, mai in una nuova scheda: la nuova
scheda perde il contesto, esce dalla PWA e su iOS apre Safari. Il visore usa
l'URL privato direttamente — funziona perché `/media-private/` risponde
`Content-Disposition: inline`, `X_FRAME_OPTIONS = SAMEORIGIN` e la denylist
del service worker esclude `^/media` dal navigation fallback (vedi
[PWA](/architecture/pwa.md)).

Immagini in `<img>`, PDF in `<iframe>`; le miniature dei PDF restano una
"carta rigata" con etichetta `PDF` (non c'è render server-side).

# Documenti generati

Due documenti non si caricano: li **produce l'applicazione** (2026-08-02) —
vedi [Generazione documenti](/domain/generazione-documenti.md). Il PDF
prodotto è un `TenantDocument` come gli altri, con `generato=True`, e sfrutta
storage privato, autorizzazioni, visore e fascicolo già esistenti.

**Generare è un'azione, non un posto vuoto** (2026-08-03, richiesta di
Sandro). Prima i due documenti comparivano nel fascicolo come voci in
`attesa`, con il bottone "Genera" al posto di "Carica". Sbagliato per due
motivi: una riga che aspetta un documento è già una richiesta, e non tutti i
casi la meritano (l'esempio di Sandro: un cittadino UE, per cui certi
adempimenti non servono); e il fascicolo diceva "manca" di un documento che
nessuno ha mai chiesto. Ora l'elenco dei producibili sta dietro un'azione
esplicita — bottone **"Genera"** accanto a "Carica documento" nel pannello
del proprietario, che apre lo sheet servito da `generabili/`. Sulle voci già
generate resta la scorciatoia "Rigenera".

Scartata l'idea di infilare "Genera" dentro il flusso *Carica documento*:
«"Carica" uno si aspetta che il documento esista».

# Non implementato

- **Sollecito** all'inquilino (email/push): previsto dal design, rinviato —
  richiede template, destinatari e throttling. Con i documenti non obbligatori
  ha senso solo per i rinnovi.
- **Quadro della casa** (matrice inquilini × documenti, con sollecito
  massivo): rinviato.
- **Notifica di scadenza**: non c'è alcun job che avvisa prima della
  scadenza; il preavviso di 60 giorni è solo lo stato `scadenza` mostrato nel
  fascicolo. I testi dell'interfaccia dicono esattamente questo.

# Documenti della casa: chi li vede (2026-08-06)

I `PropertyDocument` sono le carte dell'immobile. `visibile_inquilini` da solo
non basta più a dire chi li vede: dal 2026-08-06 un documento può essere
**collegato a un contratto** (`PropertyDocument.contract`), e le occupazioni
sanno sotto quale contratto stanno (`RoomAssignment.contract`, facoltativo).

| Documento | Assegnazione dell'inquilino | Lo vede? |
|-----------|-----------------------------|----------|
| senza contratto, `visibile_inquilini` | qualsiasi | sì (regolamento, regole di convivenza) |
| con contratto, `visibile_inquilini` | stesso contratto | sì |
| con contratto, `visibile_inquilini` | altro contratto o nessuno | **no** |
| `visibile_inquilini` falso | qualsiasi | no (solo la proprietà) |

Il gate è in **due punti** e vanno tenuti allineati: il queryset di
`PropertyDocumentViewSet` (cosa compare in elenco) e
`_autorizza_documento_proprieta` in `core/media_private.py` (chi scarica il
file). Filtrare solo l'elenco lascerebbe il file accessibile a chi ha l'URL —
gli allegati sono su storage privato servito da quella vista.

Conseguenze da ricordare:

- `RoomAssignment.contract` è **facoltativo per scelta** (Sandro, 2026-08-06):
  senza, l'inquilino non vede le carte di nessun contratto. Le assegnazioni
  esistenti prima della migrazione `0034` ce l'hanno vuoto: finché non lo si
  compila, nessun inquilino vede documenti di contratto.
  `manage.py collega_assegnazioni_contratto --contratto "<nome>" [--dal] [--apply]`
  collega in blocco quelle **iniziate dalla decorrenza in poi** — lo stesso
  criterio con cui la prima assegnazione propone il contratto. Non tocca chi
  un contratto ce l'ha già, e **non indovina i casi a cavallo** (chi c'era
  prima della decorrenza ed è rimasto dopo): li elenca e si ferma, perché lì
  serve una decisione di merito. A Via Palestrina, 2026-08-26: 7 occupazioni
  collegate al «Collettivo 2025», 3 a cavallo lasciate a Sandro.
- Alla prima assegnazione il contratto in vigore alla data d'ingresso è
  **proposto**, non imposto: un `contract: null` esplicito nel payload
  significa "nessun contratto" e viene rispettato.
- Nella cessione il subentrante **eredita** il contratto del cedente (è quello
  che dice l'atto di subentro).
- Entrambe le FK sono `SET_NULL`: eliminare un contratto non porta via file né
  occupazioni, ma un documento che era visibile torna a essere una carta della
  casa — e da quel momento **lo vedono tutti** gli inquilini.

# L'ambito è nel tipo (2026-08-26)

`contract` è nullable, ma non allo stesso modo per tutti i tipi.
**Contratto, side letter e ricevuta di registrazione *sono* la carta di un
contratto**: senza quel collegamento non stanno "nella casa", sono un dato
malformato — e per giunta con l'effetto opposto a quello voluto, perché
finiscono fra i documenti generali che vedono gli inquilini di *ogni*
contratto. Regolamento condominiale e regole di convivenza valgono invece
per la casa, e lì il contratto resta facoltativo.

La lista sta in `PropertyDocument.TIPI_CONTRATTUALI`, la regola in
`valida_ambito()`, applicata da `clean()` (admin) e dal `validate()` del
serializer — i due percorsi di scrittura non passano l'uno per l'altro.

Sul PATCH il controllo scatta **solo se la richiesta tocca `tipo` o
`contract`**: sui documenti già in archivio malformati, cambiare la sola
visibilità non deve fallire per un difetto che quella modifica non ha
introdotto. Altrimenti un record legacy non si potrebbe nemmeno nascondere.

**Tipo nuovo**: `regole_convivenza` (prima era `altro` più una descrizione
scritta a mano).

Fino a qui l'unico modo di correggere tipo o contratto di un documento era
**ricaricarlo**, ed è così che sono nati i doppioni casa/contratto: la stessa
carta due volte, una per posto, senza che nulla lo segnalasse. Ora:

- `PropertyDocumentViewSet` accetta anche JSON (serve `contract: null` per
  staccare: in multipart un campo vuoto non sa dire "nessuno");
- il dialog «Modifica documento» (matita sulla riga e sul chip del contratto)
  cambia tipo, descrizione, destinazione e visibilità;
- il foglio di caricamento avvisa se un tipo contrattuale è diretto alla casa
  (e blocca) e se un documento dello stesso tipo è già in quella
  destinazione (avvisa soltanto: fronte e retro sono legittimi);
- l'etichetta del chip non è più il nome del file: con lo storage firmato
  l'URL porta la querystring e il nome diventava un troncone illeggibile —
  è così che un doppione è passato inosservato.

`manage.py sistema_documenti_immobile [--apply]` applica la lista chiusa
delle correzioni al caso reale (idempotente, fail-safe, travasa la
descrizione al gemello che resta) e chiude con due diagnosi: le carte di
contratto rimaste senza contratto, e i documenti spuntati «visibili agli
inquilini» che **nessun inquilino vede** perché nessuna assegnazione è
collegata al loro contratto.

**In produzione l'ordine è obbligato** (il deploy del solo codice è invece
sicuro e può precederli):

1. `collega_assegnazioni_contratto --contratto "Collettivo 2025" --apply`
2. `sistema_documenti_immobile --apply`

Invertendoli si apre una finestra in cui nessun inquilino vede contratto e
lettera: il secondo comando cancella i doppioni senza contratto — quelli che
tutti vedevano — e i gemelli diventano visibili solo dopo il primo.

# Vedi anche

- [Generazione documenti](/domain/generazione-documenti.md) — atto di
  subentro e cessione di fabbricato.
- [Modelli properties](/models/properties.md) — `TenantDocument`,
  `PropertyDocument`.
- [PWA](/architecture/pwa.md) — service worker e denylist dei path non-SPA.
