---
type: Domain Logic
title: Saldi proprietari (contabilità inter-proprietario)
description: Chi ha anticipato cosa fra i proprietari, saldi live e settlement.
resource: backend/apps/accounting/services/saldi_live.py
resources:
  - backend/apps/accounting/services/saldi_live.py
  - backend/apps/accounting/services/settlement.py
  - backend/apps/accounting/services/bt_inter_owner.py
  - backend/apps/accounting/views.py
tags: [domain, accounting, settlement, saldi]
generated:
  by: process:okf-migrate
  at: 2026-09-05T00:00:00Z
---

# Overview

I proprietari (nel caso storico, i tre fratelli) anticipano spese e incassano
affitti in modo non uniforme; questa area tiene i conti tra loro. Servizi in
`backend/apps/accounting/services/`. Fino al 2026-08 l'area si chiamava
"Saldi fratelli"; con la multiproprietà il nome è neutro.

Tutto è **per immobile**: ogni servizio riceve la `Property` e usa le quote
attive alla data (`properties.quote_attive_at`); ledger, settlement e partite
bilaterali hanno la FK `property` (vedi [reference](/models/accounting.md)).

# Saldi live

`saldi_live.py` calcola in tempo reale, **mai persistito** (durante l'anno
non si scrivono voci ledger automatiche: 30 spese × 3 proprietari sarebbero
90 voci di rumore), `{saldi, quadratura, piano_rientro}`:

- **saldi** (`calcola_saldi_correnti(property, at_date)`): posizione netta di
  ciascun proprietario con quota attiva; >0 credito verso gli altri, <0 debito.
  Periodo aperto = dal giorno dopo l'ultimo `OwnerSettlement` chiuso ≤ data
  fino alla data (tutta la storia se non c'è settlement); si parte dalla
  **baseline** letta dallo `snapshot` di quel settlement;
- **quadratura** (`verifica_quadratura`): Σ saldi = 0 ed elenco degli orfani;
- **piano_rientro** (`calcola_piano_rientro`): bonifici minimi debitori →
  creditori, greedy a due puntatori.

Convenzioni di segno (decomposizione in `SaldoLive`):

| Flusso | Chi | Contributo |
|--------|-----|------------|
| spesa anticipata da X | X | `+(1 − quota_X) · importo` (`anticipi_pendenti`) |
| | Y ≠ X | `−quota_Y · importo` |
| spesa con `riferimento_quota_owner = R` | anticipante A | `+importo` (credito intero verso R); se A = R nessun effetto |
| | R | `−importo` |
| incasso ricevuto da X (Receivable `pagato`) | X | `−(1 − quota_X) · importo_pagato` (tiene i soldi degli altri) |
| | Y ≠ X | `+quota_Y · importo_pagato` |
| BT marcata inter-owner | owner della voce ledger | `+importo` della voce |

Entrano nel riparto solo i Receivable `pagato` con `data_pagamento` e
`importo_pagato` valorizzati **e** `incassato_da_owner`. La quadratura elenca
a parte gli «incassi esclusi dal calcolo» (`receivable_orfani`: manca
«incassato da», PAGATO senza importo pagato, incassante senza quota attiva) e
le `expense_orfane` (anticipante senza quota attiva). Il caso «manca incassato
da» non è più producibile — cfr.
[Incasso sempre attribuito](/decisions/incasso-sempre-attribuito.md) — ma
resta nel controllo per i dati storici.

`Expense.riferimento_quota_owner` permette di imputare una spesa a un
proprietario specifico anziché ripartirla per quote (es. Bruna paga l'IMU di
Fabio).

# Settlement

`settlement.py`: `genera_settlement` cristallizza un conguaglio fra proprietari in
un `OwnerSettlement` (con `snapshot` JSON) su un periodo, creando le
`OwnerLedgerEntry` da Receivable ed Expense (ripartite per quota,
`_ripartisci`); rifiuta un periodo già coperto (`SettlementGiaEsistente`).
Comando: `genera_settlement` (con `--property`); azionabile anche da UI
(`POST owner-settlements/genera/`).

# BT come voce inter-owner

`bt_inter_owner.py`: `marca_bt_come_ledger` / `disfa_marcatura` permettono di
trattare un movimento bancario come regolamento fra proprietari (idempotente e
reversibile, `BTGiaMarcata` se già marcata); dal FE via
`bt-inter-owner/` sull'`OwnerLedgerEntryViewSet`, nel perimetro dell'immobile.

# Frontend

- `/p/saldi-proprietari` (`ProprietarioSaldiProprietari.vue`) — saldi, quadratura,
  settlement; `/p/saldi-fratelli` resta come redirect per i segnalibri.
- Dashboard "Flusso di cassa".

# Vedi anche

- [Conto economico](/domain/conto-economico.md) — ponte cassa↔competenza.
- [Reference accounting](/models/accounting.md).
- [Incasso sempre attribuito](/decisions/incasso-sempre-attribuito.md) — perché ogni pagato ha un incassante.
