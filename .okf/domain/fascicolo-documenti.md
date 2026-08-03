---
type: Domain Logic
title: Fascicolo documenti
description: "Elenco dei documenti dell'inquilino con stati derivati (valido/in scadenza/scaduto), servito a inquilino e proprietario dallo stesso servizio. Nessun documento è obbligatorio e nessuna voce è vuota: compare solo ciò che esiste."
resource: backend/apps/properties/fascicolo.py
tags: [domain, documenti, inquilini, frontend]
timestamp: 2026-08-03T00:00:00Z
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

# Vedi anche

- [Generazione documenti](/domain/generazione-documenti.md) — atto di
  subentro e cessione di fabbricato.
- [Modelli properties](/models/properties.md) — `TenantDocument`,
  `PropertyDocument`.
- [PWA](/architecture/pwa.md) — service worker e denylist dei path non-SPA.
