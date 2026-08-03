---
type: Domain Logic
title: Fascicolo documenti
description: Checklist dei documenti dell'inquilino con stati derivati (valido/in scadenza/scaduto/a carico proprietà), servita a inquilino e proprietario dallo stesso servizio. Nessun documento è obbligatorio.
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
| `attesa` | tipo **a carico della proprietà** e non ancora caricato |

Lo stato di una voce con più file è il **peggiore** delle sue pagine
(`scaduto` > `scadenza` > `ok`).

**Nessun documento è obbligatorio** (decisione del 2026-08-01): non esiste uno
stato "mancante" e il fascicolo non misura la completezza. Le copie servono per
il contratto e le utenze, e dopo la verifica possono essere cancellate — meno
dati conservati, meno rischio. Di conseguenza una voce senza file compare solo
quando è a carico della proprietà.

# Voci della checklist

`VOCI` in `fascicolo.py` — ordine e ruolo di ogni tipo:

| Tipo | Ruolo |
|------|-------|
| `carta_identita`, `codice_fiscale`, `passaporto`, `permesso_soggiorno`, `contratto_lavoro`, `ricevuta_registrazione` | compaiono **solo se caricati** |
| `atto_subentro_locazione` | a carico della proprietà, **generato** dall'app; compare **solo se** l'assegnazione ha `subentra_a` |
| `cessione_fabbricato` | a carico della proprietà, **generato** dall'app; sempre presente |
| `altro` | fuori checklist: ogni file è una voce a sé, in `altri` |

`ricevuta_registrazione` = "Registrazione contratto subentro", la ricevuta
telematica che l'agenzia rilascia registrando il contratto (2026-08-01).
Copre anche il subentro: è un adempimento successivo sullo stesso contratto,
non riceve estremi propri e quindi non è un documento diverso. Il tipo
`ricevuta_subentro`, che diceva la stessa cosa, è stato fuso qui dalla
migrazione `0032` (2026-08-03).

**L'atto di subentro delle utenze non è più qui** (2026-08-03): riguarda
l'immobile, non la persona, e semmai va fra i documenti della casa. La
migrazione `0033` toglie il tipo `atto_subentro` e declassa i file già
caricati ad `altro`, conservandone il nome nella descrizione. Il pattern «a
carico della proprietà» resta, usato dai due documenti generati.

**Voci condizionate** (2026-08-02): `VoceFascicolo.applicabile` è un
predicato sull'assegnazione dell'inquilino. Serviva all'atto di subentro nel
contratto, che ha senso solo per chi è subentrato a qualcuno: senza
condizione, il primo occupante di una stanza resterebbe per sempre in
`attesa` di un atto che non esisterà mai — l'opposto della regola "nessun
documento è dovuto". La cessione di fabbricato resta invece incondizionata:
l'art. 12 obbliga il cedente per **ogni** nuovo occupante. Per valutare il
predicato, `costruisci_fascicolo` accetta l'assegnazione (default: l'ultima
dell'inquilino). Un file già caricato si mostra comunque, anche se la voce
non si applicherebbe: esiste, va visto.

I `suggerimento` descrivono il documento e nient'altro: lo stesso payload
alimenta entrambe le UI, e un «lo generi tu» nel fascicolo dell'inquilino
non direbbe nulla. L'invito ad agire sta nel frontend del proprietario.

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

Payload: `voci[]` (checklist), `altri[]`, `riepilogo` (conteggi per stato +
`da_sistemare` = scaduti + in scadenza). Ogni voce porta `pagine[]` con `file`
(URL `/media-private/…`), `etichetta`, `is_pdf`, e `generabile` (codice del
generatore o `null`): il fascicolo resta l'unica sorgente, non serve un
endpoint per scoprire cosa si può generare.

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

Due voci della checklist non si caricano: le **produce l'applicazione**
(2026-08-02) — vedi [Generazione documenti](/domain/generazione-documenti.md).
Il PDF prodotto è un `TenantDocument` come gli altri, con `generato=True`, e
sfrutta storage privato, autorizzazioni, visore e fascicolo già esistenti.

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
