---
type: Domain Logic
title: Fascicolo documenti
description: Checklist dei documenti dell'inquilino con stati derivati (valido/in scadenza/scaduto/mancante/a carico proprietà), servita a inquilino e proprietario dallo stesso servizio.
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
| `mancante` | tipo **richiesto** e mai caricato |
| `attesa` | tipo **a carico della proprietà** e non ancora caricato |

Lo stato di una voce con più file è il **peggiore** delle sue pagine
(`scaduto` > `scadenza` > `ok`).

# Voci della checklist

`VOCI` in `fascicolo.py` — ordine e ruolo di ogni tipo:

| Tipo | Ruolo |
|------|-------|
| `carta_identita`, `codice_fiscale`, `contratto_lavoro` | **richiesti**: se assenti compaiono come `mancante` |
| `passaporto`, `permesso_soggiorno`, `ricevuta_subentro` | facoltativi: **compaiono solo se caricati** |
| `atto_subentro` | a carico della proprietà: sempre presente, `attesa` finché manca |
| `altro` | fuori checklist: ogni file è una voce a sé, in `altri` |

**Perché i facoltativi assenti non compaiono**: non si può dedurre chi ha
bisogno di un permesso di soggiorno o di un passaporto; mostrarli come
"mancanti" sarebbe un allarme falso. Restano caricabili scegliendo il tipo
nel modulo di caricamento.

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

Payload: `voci[]` (checklist), `altri[]`, `riepilogo` (conteggi per stato,
`da_sistemare`, `completezza` %). Ogni voce porta `pagine[]` con `file`
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

- **Sollecito** all'inquilino (email/push) per i documenti mancanti: previsto
  dal design, rinviato — richiede template, destinatari e throttling.
- **Quadro della casa** (matrice inquilini × documenti, con sollecito
  massivo): rinviato.
- **Notifica di scadenza**: non c'è alcun job che avvisa prima della
  scadenza; il preavviso di 60 giorni è solo lo stato `scadenza` mostrato nel
  fascicolo. I testi dell'interfaccia dicono esattamente questo.

# Vedi anche

- [Modelli properties](/models/properties.md) — `TenantDocument`,
  `PropertyDocument`.
- [PWA](/architecture/pwa.md) — service worker e denylist dei path non-SPA.
