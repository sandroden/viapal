---
type: Domain Logic
title: Conguaglio
description: Ripartizione utenze di un periodo (conguaglio reale) e conguaglio previsionale all'uscita dell'inquilino.
resource: backend/apps/billing/calc/utility.py
resources:
  - backend/apps/billing/calc/utility.py
  - backend/apps/billing/management/commands/calcola_conguaglio.py
  - backend/apps/billing/management/commands/genera_conguagli_storici.py
  - backend/apps/billing/dashboard_views.py
tags: [domain, conguaglio, billing]
timestamp: 2026-09-05T00:00:00Z
---

# Overview

Nel progetto "conguaglio" ha **due significati**, da non confondere:

1. **conguaglio utenze** (questo concetto): la ripartizione dei costi di un
   `UtilityChargePeriod` sugli inquilini, con i relativi Receivable UTENZE, e
   la sua variante **previsionale** all'uscita di un inquilino;
2. il conguaglio **di cassa fra proprietari**, che è il ponte descritto in
   [conto economico](/domain/conto-economico.md) e [saldi proprietari](/domain/saldi-proprietari.md).

Il calcolo vive in `billing/calc/utility.py: calcola_conguaglio_periodo`
(dettagli dell'algoritmo in [calcolo utenze](/domain/calcolo-utenze.md)). Il
comando `calcola_conguaglio --period-id N [--persist]` è solo il wrapper CLI
(dry-run di default, nessuna opzione `--property`: il periodo identifica già
l'immobile); `genera_conguagli_storici --dal --al --property` crea i periodi
mensili e li persiste in serie. L'emissione dal frontend passa da
`utility-periods/<id>/emetti/`, che chiama la stessa funzione con `persist=True`.

# Conguaglio reale (per periodo)

Input: bollette e costi annuali attribuiti al periodo; per ogni
`RoomAssignment` in overlap (rinunce escluse) `giorni_presenza` = giorni di
intersezione, sempre pro-rata sui giorni **a prescindere da
`TenantProfile.ciclo_fatturazione`** (che vale solo per gli affitti);
`costo_per_giorno_persona = totale_voce / sum_giorni`; quota per inquilino =
somma delle voci, `ROUND_HALF_UP`; `diff_arrotondamento` esposto.

Con `persist=True`: scrive `tot_*` (netti delle quote escluse) e
`giorni_totali` sul periodo e fa `update_or_create` di un Receivable UTENZE per
`(period, assignment)` — idempotente, vincolo `receivable_utenze_unique`.
Rispetta la [guardia allocations](/decisions/guardia-allocations.md): un
Receivable già allocato non viene toccato e finisce in `skipped` con importo
esistente e ricalcolato.

Esiti `skipped`: `no_bollette_luce_gas` (senza `forza_senza_bollette`),
`nessun_importo` (periodo davvero vuoto). Un periodo `inviato` è congelato;
le ricostruzioni a posteriori chiamano il calcolo con `persist=False` e
`forza_senza_bollette=True`.

# Conguaglio previsionale (uscita dell'inquilino)

Serve quando l'inquilino esce prima che arrivino le bollette del suo ultimo
periodo: si trattiene una stima dal deposito e la si conguaglia dopo. Vive in
`billing/dashboard_views.py`, per immobile (scoping 2026-07-24):

| Passo | Endpoint | Cosa fa |
|-------|----------|---------|
| stima | `GET tenants/<id>/previsionale-utenze/?data_target=` (`_calcola_stima_previsionale`) | media giornaliera delle **ultime due** utenze del tenant con `giorni_presenza > 0` × giorni dalla fine dell'ultimo periodo alla data target; errore esplicito se non ci sono utenze pregresse o la data non precede il target |
| addebito | `POST tenants/<id>/previsionale-utenze/` | crea un Receivable **EXTRA** marcato in `note` con `previsionale_utenze`, `competenza_da/_a` = range coperto |
| anteprima | `GET tenants/<id>/conguaglia-previsionale/?previsionale_id=` | elenca le utenze reali del range e la rettifica proposta |
| conguaglio | `POST tenants/<id>/conguaglia-previsionale/` | crea un EXTRA di rettifica con `importo = −somma_utenze_reali` e marca il previsionale `conguaglio_previsionale` (409 se già fatto, 400 se non è un previsionale o manca la competenza) |

- **Niente doppio pro-rata**: le utenze reali del range sono già proratate sui
  giorni; la rettifica le somma tal quali (fix noto).
- La trattenuta sul deposito è la partita compensata del caso
  [segni concordi](/decisions/segni-concordi.md): BT −984 ↔ restituzione −1060
  + previsionale +76.

# Frontend

- Inquilino: `/i/conguaglio/:id` (`InquilinoConguaglio.vue`) è il **dettaglio di
  un singolo addebito utenze** (`/api/v1/utility-charges/<id>/`), non una
  pagina di conguaglio previsionale; l'inquilino vede il previsionale come un
  normale addebito EXTRA.
- Proprietario: `PrevisionaleUtenzeDialog` e `ConguagliaPrevisionaleDialog` nel
  dettaglio inquilino; l'emissione per periodo in `/p/utenze`.

# Vedi anche

- [Calcolo utenze](/domain/calcolo-utenze.md), [Deposito](/domain/deposito.md),
  [Conto economico](/domain/conto-economico.md) — per l'altro "conguaglio".
