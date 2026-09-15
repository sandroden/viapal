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
  at: 2026-09-15T03:30:00Z
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
| spese | `Expense` per `Coalesce(data_competenza, data)` in **entrambe** le letture, separate in ordinarie e straordinarie |
| voci | `VOCE_PER_CAUSALE`: AFFITTO→`rent`, UTENZE→`utility`, EXTRA e REGISTRAZIONE→`extra`; **DEPOSITO è fuori** da entrambe le letture (non è un ricavo) |
| utile pro-quota | per proprietario, con le quote attive al 31/12 dell'anno (o a oggi se l'anno è in corso): `utile_cassa` e `utile_competenza` |
| serie multi-anno | solo per cassa: ricavi/spese/utile per ogni anno con dati |
| occupazione | giorni-stanza occupati da `RoomAssignment` nella finestra dell'anno |

Un deposito **trattenuto** è di fatto un ricavo ma resta invisibile qui finché
non viene riclassificato su EXTRA: nessun automatismo lo fa (vedi
[deposito](/domain/deposito.md)).

# Anno di competenza

Data del pagamento e anno di bilancio sono due cose diverse: l'IMU 2022
versata nel dicembre 2023 pesa sul 2022. `Expense.data_competenza` (nullable)
lo dichiara e il conto economico raggruppa sul `Coalesce` delle due, così il
libro conserva la data vera del pagamento invece di falsarla. Stessa cosa per
i [saldi fra proprietari](/domain/saldi-proprietari.md), dove la competenza
decide a quale chiusura appartiene una spesa.

Su `Receivable` esiste `data_competenza` come **eccezione dichiarata a mano**:
per affitti e utenze la fonte resta `competenza_da`/`competenza_a` (e il
periodo bolletta), l'override serve ai soli casi anomali e, quando c'è, vince
sull'anno di bilancio. In interfaccia si sceglie sempre un anno, tradotto in
data da `data_competenza_da_anno`.

# Imposte dei proprietari

IMU e cedolare secca sono pagate da ciascun proprietario con il proprio F24,
ma sono un'uscita dell'affitto: senza, l'utile è sovrastimato. Stanno qui come
`Expense` con **anticipante e beneficiario coincidenti**
(`anticipata_da_owner == riferimento_quota_owner`), forma che entra nel costo
e che [saldi_live](/domain/saldi-proprietari.md) ignora: le imposte non
spostano nulla fra i proprietari. Se un proprietario le anticipa per un altro,
quel denaro è un trasferimento a parte (`distribuzione`), non una seconda
spesa. Comando di popolamento storico: `inserisci_imposte_proprietari`.

Le imposte versate in ritardo tengono la data vera del pagamento e dichiarano
l'anno in `data_competenza` (il caso reale: l'IMU 2022 di Fabio, pagata nel
dicembre 2023 insieme a quella del 2023).

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
