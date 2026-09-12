---
type: Domain Logic
title: Conto economico (cassa vs competenza)
description: Le due viste contabili e il ponte tra conguaglio di cassa e saldi live.
resource: backend/apps/billing/dashboard_views/conto_economico.py
resources:
  - backend/apps/billing/dashboard_views/conto_economico.py
  - backend/apps/accounting/services/saldi_live.py
tags: [domain, conto-economico, cassa, competenza]
generated:
  by: process:okf-migrate
  at: 2026-09-05T00:00:00Z
---

# Overview

Il conto economico per i proprietari esiste in due letture:

- **Cassa**: cosa è effettivamente entrato/uscito (movimenti bancari).
- **Competenza**: cosa è di competenza del periodo, a prescindere dall'incasso.

Endpoint: `GET /api/v1/dashboard/conto-economico/?anno=YYYY`
(`ContoEconomicoView` in `billing/dashboard_views.py`, permesso
`IsPropertyMember`, scoping sull'immobile attivo). Frontend:
`/p/conto-economico` (`ProprietarioContoEconomico.vue`).

# Come si costruiscono le due letture

| Blocco | Regola |
|--------|--------|
| ricavi per **cassa** | Receivable `pagato` con `data_pagamento` nell'anno, sommati per `importo_pagato` |
| ricavi per **competenza** | Receivable il cui anno di competenza è quello richiesto (affitti/extra per `competenza_da`, utenze per il periodo bolletta, fallback `scadenza`); il residuo non incassato è esposto a parte (`non_incassato`, `non_incassato_voci`) |
| spese | `Expense` per `data` (unica data disponibile) in **entrambe** le letture, separate in ordinarie e straordinarie |
| voci | `VOCE_PER_CAUSALE`: AFFITTO→`rent`, UTENZE→`utility`, EXTRA e REGISTRAZIONE→`extra`; **DEPOSITO è fuori** da entrambe le letture (non è un ricavo) |
| utile pro-quota | per proprietario, con le quote attive al 31/12 dell'anno (o a oggi se l'anno è in corso): `utile_cassa` e `utile_competenza` |
| serie multi-anno | solo per cassa: ricavi/spese/utile per ogni anno con dati |
| occupazione | giorni-stanza occupati da `RoomAssignment` nella finestra dell'anno |

Un deposito **trattenuto** è di fatto un ricavo ma resta invisibile qui finché
non viene riclassificato su EXTRA: nessun automatismo lo fa (vedi
[deposito](/domain/deposito.md)).

# Il ponte competenza ↔ cassa

Per i proprietari serve riconciliare le due viste. Relazione chiave individuata:

```
conguaglio_cassa = − saldi_live.totale
```

Cioè il conguaglio di cassa è l'opposto del totale dei [saldi live](/domain/saldi-proprietari.md).
La scelta di design è stata **non** creare una terza pagina dedicata, ma un box
dentro `ContoEconomico` con deep-link a `SaldiProprietari`.

# Nota aperta: mismatch anno-vs-live (P0)

I due numeri non sono sullo stesso perimetro per costruzione: il conto
economico è **per anno solare**, i saldi live coprono il **periodo aperto**
(dal giorno dopo l'ultimo `OwnerSettlement` chiuso fino a oggi) e partono
dalla baseline di quel settlement. Coincidono solo se l'ultimo settlement
chiude esattamente al 31/12 dell'anno precedente. Da tenere presente quando i
numeri non tornano; non è stato risolto.

# Vedi anche

- [Saldi proprietari](/domain/saldi-proprietari.md), [Conguaglio](/domain/conguaglio.md).
