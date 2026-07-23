---
type: Django App
title: App accounting
description: Contabilità tra proprietari — ledger, settlement e partite bilaterali.
resource: backend/apps/accounting/models/
tags: [models, accounting]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

Contabilità **fra i proprietari** (i tre fratelli): chi ha anticipato cosa, quanto
è dovuto a chi, e i conguagli periodici. Logica in [saldi fratelli](/domain/saldi-fratelli.md).

# Modelli

| Modello | Campi chiave | Note |
|---------|--------------|------|
| `OwnerLedgerEntry` | `owner`, `data`, `importo`, `tipo`, `riferimento_receivable`, `riferimento_expense`, `riferimento_settlement`, `bank_transaction` | voce di libro mastro per proprietario |
| `OwnerSettlement` | `data`, `periodo_da`/`_a`, `snapshot` (JSON) | conguaglio periodico congelato in snapshot |
| `InterOwnerLoan` | `owner_da`, `owner_a`, `importo_originale`, `chiuso` | prestito bilaterale |
| `InterOwnerEntry` | `owner_da`, `owner_a`, `importo`, `riferimento_loan/_expense/_settlement`, `bank_transaction` | movimento bilaterale |
| `WithholdingRule` | `owner_da`, `owner_a`, `importo_mensile`, `attiva`, `valid_from`/`_to` | trattenuta ricorrente (definita, non ancora usata) |

# Vedi anche

- [Saldi fratelli](/domain/saldi-fratelli.md) — `saldi_live`, `genera_settlement`.
- [Conto economico](/domain/conto-economico.md) — ponte cassa↔competenza.
