---
type: Domain Logic
title: Saldi fratelli (contabilità inter-proprietario)
description: Chi ha anticipato cosa fra i tre proprietari, saldi live e settlement.
resource: backend/apps/accounting/services/
tags: [domain, accounting, settlement, saldi]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

I tre fratelli proprietari anticipano spese e incassano affitti in modo non
uniforme; questa area tiene i conti tra loro. Servizi in
`backend/apps/accounting/services/`.

# Saldi live

`saldi_live.py` calcola in tempo reale `{saldi, quadratura, piano_rientro}`:
- **saldi**: posizione netta di ciascun proprietario (dare/avere);
- **quadratura**: verifica che la somma torni a zero;
- **piano_rientro**: chi deve versare a chi per azzerare.

Il campo `Expense.riferimento_quota_owner` permette di imputare una spesa a un
proprietario specifico anziché ripartirla per quote.

# Settlement

`settlement.py`: `genera_settlement` cristallizza un conguaglio fra proprietari in
un `OwnerSettlement` (con `snapshot` JSON) su un periodo, creando le
`OwnerLedgerEntry` da Receivable ed Expense (ripartite per quota). Comando:
`genera_settlement`; azionabile anche da UI.

# BT come voce inter-owner

`bt_inter_owner.py`: `marca_bt_come_ledger` / `disfa_marcatura` permettono di
trattare un movimento bancario come regolamento fra proprietari (idempotente e reversibile).

# Frontend

- `/p/saldi-fratelli` (`ProprietarioSaldiFratelli.vue`) — saldi, quadratura, settlement.
- Dashboard "Flusso di cassa".

# Vedi anche

- [Conto economico](/domain/conto-economico.md) — ponte cassa↔competenza.
- [Reference accounting](/models/accounting.md).
