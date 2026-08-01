---
type: Domain Logic
title: Fascicolo documenti
description: Checklist dei documenti dell'inquilino con stati derivati (valido/in scadenza/scaduto/a carico proprietà), servita a inquilino e proprietario dallo stesso servizio. Nessun documento è obbligatorio.
resource: backend/apps/properties/fascicolo.py
tags: [domain, documenti, inquilini, frontend]
timestamp: 2026-08-01T00:00:00Z
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
| `carta_identita`, `codice_fiscale`, `passaporto`, `permesso_soggiorno`, `contratto_lavoro`, `ricevuta_registrazione`, `ricevuta_subentro` | compaiono **solo se caricati** |
| `atto_subentro` | a carico della proprietà: sempre presente, `attesa` finché manca |
| `altro` | fuori checklist: ogni file è una voce a sé, in `altri` |

`ricevuta_registrazione` = "Ricevuta di registrazione (agenzia)", la ricevuta
che l'agenzia rilascia per la registrazione del contratto (2026-08-01).

**Perché l'atto di subentro è diverso**: lo produce il fornitore di utenze e
lo carica il proprietario. All'inquilino appare come «non devi fare nulla:
lo carica la proprietà» (nessun bottone), al proprietario come «lo carichi
tu, non l'inquilino» (riga attiva, con caricamento).

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
(URL `/media-private/…`), `etichetta`, `is_pdf`.

# Visualizzazione

I documenti si aprono **dentro l'app**, mai in una nuova scheda: la nuova
scheda perde il contesto, esce dalla PWA e su iOS apre Safari. Il visore usa
l'URL privato direttamente — funziona perché `/media-private/` risponde
`Content-Disposition: inline`, `X_FRAME_OPTIONS = SAMEORIGIN` e la denylist
del service worker esclude `^/media` dal navigation fallback (vedi
[PWA](/architecture/pwa.md)).

Immagini in `<img>`, PDF in `<iframe>`; le miniature dei PDF restano una
"carta rigata" con etichetta `PDF` (non c'è render server-side).

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

- [Modelli properties](/models/properties.md) — `TenantDocument`,
  `PropertyDocument`.
- [PWA](/architecture/pwa.md) — service worker e denylist dei path non-SPA.
