---
type: Architecture
title: Modello dati
description: Mappa Receivable-centrica delle entità e relazioni principali.
tags: [architecture, data-model]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

Il modello ruota attorno al **[Receivable](/domain/receivable.md)**: un unico
addebito verso l'inquilino che unifica affitto, utenze ed extra (distinti dal
campo `causale`). Il decoupling tra ciò che è *dovuto* (Receivable) e ciò che è
*incassato* (BankTransaction) avviene tramite `BankTransactionAllocation` (M:N).

# Assi principali

```
Property ──< Room ──< RoomAssignment >── TenantProfile
                            │
                            └──< Receivable >──< BankTransactionAllocation >── BankTransaction
                                     │
                                     └── UtilityChargePeriod (per le utenze)
```

- **Anagrafica immobile**: `Property` → `Room` → `RoomAssignment` (stanza assegnata
  a un inquilino in un intervallo `valid_from`/`valid_to`, con `canone_mensile`).
  `Room` è più in generale l'**unità locata**: se `Property.tipo_gestione ==
  "unita_intera"` esiste una sola `Room` implicita "Appartamento" e l'immobile è
  affittato per intero a un unico inquilino (vedi [Unità intera](/domain/unita-intera.md)).
- **Proprietà**: `OwnerProfile` + `OwnershipShare` (quote temporali) +
  `OwnerBankAccount`.
- **Addebiti**: `Receivable` (verso inquilino) con causale AFFITTO/UTENZE/EXTRA/…
- **Incassi**: `BankTransaction` (movimenti bancari) allocati ai Receivable via
  `BankTransactionAllocation` (relazione M:N con importo per allocazione).
- **Utenze**: `UtilityBill` (bolletta) → `UtilityChargePeriod` (periodo di
  addebito, M:N con le bollette) → Receivable per inquilino.
- **Costi**: `Expense`, `Supplier`, `ExpenseCategory`.
- **Contabilità fra proprietari**: `OwnerLedgerEntry`, `OwnerSettlement`,
  `InterOwnerLoan`/`InterOwnerEntry`.

# Reference strutturale per app

- [properties](/models/properties.md), [billing](/models/billing.md),
  [accounting](/models/accounting.md), [accounts](/models/accounts.md),
  [notifications](/models/notifications.md).

# Vedi anche

- [Riconciliazione bonifici](/domain/riconciliazione.md)
- [Unità intera](/domain/unita-intera.md)
- [Decisione: unificazione Receivable](/decisions/unificazione-receivable.md)
