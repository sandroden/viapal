---
type: Domain Logic
title: Conguaglio
description: Ripartizione utenze di un periodo (conguaglio reale) e conguaglio previsionale all'uscita dell'inquilino.
resource: backend/apps/billing/calc/utility.py
resources:
  - backend/apps/billing/calc/utility.py
  - backend/apps/billing/management/commands/calcola_conguaglio.py
  - backend/apps/billing/management/commands/genera_conguagli_storici.py
  - backend/apps/billing/dashboard_views/previsionale.py
tags: [domain, conguaglio, billing]
timestamp: 2026-09-07T00:00:00Z
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
`billing/dashboard_views/previsionale.py`, per immobile (scoping 2026-07-24).

Dal 2026-09-07 il previsionale è un Receivable **UTENZE** senza
`utility_period`, con il campo proprio `previsionale=True`; la rettifica è
un altro UTENZE (negativo) che lo punta via `conguaglio_di`. "Conguagliato"
significa che esiste almeno una rettifica che lo punta: non c'è più nessun
marcatore nelle `note` (che tornano a essere solo il log dichiara/rifiuta).
Prima era un EXTRA riconosciuto dalla stringa `previsionale_utenze` nelle
note; la migrazione `billing/0035` ha convertito i dati. Non è uno *stato*:
lo stato di pagamento viene riallineato dalle allocazioni e non può
custodire la natura dell'addebito.

| Passo | Endpoint | Cosa fa |
|-------|----------|---------|
| stima | `GET tenants/<id>/previsionale-utenze/?data_target=` (`_calcola_stima_previsionale`) | media giornaliera delle **ultime due** utenze del tenant con `giorni_presenza > 0` × giorni dalla fine dell'ultimo periodo alla data target; errore esplicito se non ci sono utenze pregresse o la data non precede il target |
| addebito | `POST tenants/<id>/previsionale-utenze/` | crea un Receivable **UTENZE** con `previsionale=True` (niente periodo), `competenza_da/_a` = range coperto |
| anteprima | `GET tenants/<id>/conguaglia-previsionale/?previsionale_id=` | elenca le utenze reali del range e la rettifica proposta |
| conguaglio | `POST tenants/<id>/conguaglia-previsionale/` | crea un UTENZE di rettifica con `importo = −previsionale` (annulla la **stima**) e `conguaglio_di` = previsionale (409 se già conguagliato, se non ci sono utenze reali nel range o se i periodi emessi non arrivano a `competenza_a`; 400 se non è un previsionale o manca la competenza) |

- **Niente doppio pro-rata**: le utenze reali del range sono già proratate sui
  giorni; si sommano tal quali (fix noto).
- **La rettifica annulla la stima, non le bollette** (2026-09-07, scelta di
  Sandro). Prima valeva −somma_reali: bolletta e rettifica si elidevano e il
  dovuto del periodo restava la stima, qualunque fossero le bollette; la
  differenza fra trattenuto e reale spariva (caso Davide: stima 49,80,
  reale 57,26, bonificati 275,05 invece di 267,59, nessuna traccia dei
  7,46). Ora il dovuto è la somma delle utenze reali e lo scarto emerge nel
  saldo dell'inquilino. Il previsionale resta visibile come acconto:
  nessuna riga viene cancellata. L'anteprima espone `copertura_fino_a` /
  `copertura_completa` e `netto_a_favore_inquilino = stima − reale`.
  `sana_conguagli_previsionali [--apply]` porta le rettifiche vecchie alla
  nuova regola (salta quelle con allocazioni).
- Tutto quel che manca nella chiusura (netto da rendere scomposto, bonifico
  unico) è in [deposito](/domain/deposito.md#chiusura-netto-da-rendere-e-bonifico-unico).
- La trattenuta sul deposito è la partita compensata del caso
  [segni concordi](/decisions/segni-concordi.md): BT −984 ↔ restituzione −1060
  + previsionale +76.

# Frontend

- Inquilino: `/i/conguaglio/:id` (`InquilinoConguaglio.vue`) è il **dettaglio di
  un singolo addebito utenze** (`/api/v1/utility-charges/<id>/`), non una
  pagina di conguaglio previsionale; l'inquilino vede il previsionale come un
  normale addebito EXTRA.
- Proprietario: `PrevisionaleUtenzeDialog` e `ConguagliaPrevisionaleDialog` nel
  dettaglio inquilino (tab Profilo & contratto, card Deposito); l'emissione
  per periodo in `/p/utenze`. Nella tabella pagamenti il previsionale e la
  rettifica stanno fra le **Utenze**, con badge "Previsionale" /
  "Previsionale conguagliato" / "Conguaglio previsionale"; le righe utenze
  senza periodo mostrano la `descrizione` al posto del periodo, ovunque
  (`_descrizione_receivable`, serializer di riconciliazione, situazione).
- Il bottone "Conguaglia" resta disabilitato finché la somma delle utenze
  reali è zero o la copertura è parziale, con un avviso che rimanda
  all'emissione delle bollette. "Crea addebito previsionale" non compare se
  un previsionale esiste già, anche conguagliato.

# Vedi anche

- [Calcolo utenze](/domain/calcolo-utenze.md), [Deposito](/domain/deposito.md),
  [Conto economico](/domain/conto-economico.md) — per l'altro "conguaglio".
