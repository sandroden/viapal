---
type: Django App
title: App accounting
description: Contabilità tra proprietari — ledger, settlement e partite bilaterali.
resource: backend/apps/accounting/models/ledger.py
resources:
  - backend/apps/accounting/models/ledger.py
  - backend/apps/accounting/models/bilateral.py
tags: [models, accounting]
timestamp: 2026-09-05T00:00:00Z
---

# Overview

Contabilità **fra i proprietari** di un immobile: chi ha anticipato cosa,
quanto è dovuto a chi, e i conguagli periodici. Logica in
[saldi proprietari](/domain/saldi-proprietari.md). Dalla multiproprietà
(2026-07) ogni modello ha la FK `property`: i saldi non attraversano mai gli
immobili.

# Modelli

| Modello | Campi chiave | Note |
|---------|--------------|------|
| `OwnerLedgerEntry` | `property`, `owner`, `data`, `descrizione`, `importo`, `tipo`, `riferimento_receivable`, `riferimento_expense`, `riferimento_settlement`, `bank_transaction`, `note` | voce di libro mastro per proprietario; `tipo` ∈ incasso_affitto, incasso_conguaglio, spesa, anticipo, distribuzione, aggiustamento; unica per `(riferimento_receivable, owner, tipo)` e `(riferimento_expense, owner, tipo)` — così `genera_settlement` è idempotente |
| `OwnerSettlement` | `property`, `data`, `periodo_da`/`_a`, `descrizione`, `snapshot` (JSON), `note` | conguaglio periodico congelato in snapshot; è la baseline dei saldi live |
| `InterOwnerLoan` | `property`, `owner_da`, `owner_a`, `data_apertura`, `importo_originale`, `chiuso` | prestito bilaterale |
| `InterOwnerEntry` | `property`, `owner_da`, `owner_a`, `data`, `importo`, `riferimento_loan/_expense/_settlement`, `bank_transaction` | movimento bilaterale |
| `WithholdingRule` | `property`, `owner_da`, `owner_a`, `importo_mensile`, `attiva`, `valid_from`/`_to` | trattenuta ricorrente (definita, non ancora usata da alcun servizio) |

# Vedi anche

- [Saldi proprietari](/domain/saldi-proprietari.md) — `saldi_live`, `genera_settlement`.
- [Conto economico](/domain/conto-economico.md) — ponte cassa↔competenza.
