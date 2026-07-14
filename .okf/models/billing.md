---
type: Django App
title: App billing
description: Addebiti (Receivable), incassi bancari, utenze e spese.
resource: backend/apps/billing/models/
tags: [models, billing]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

Cuore contabile: addebiti verso inquilini, movimenti bancari, bollette/periodi
utenze e spese. La logica sta nei concetti di [dominio](/domain/).

# Modelli

| Modello | Campi chiave | Note |
|---------|--------------|------|
| `Receivable` | `assignment`, `causale`, `importo_dovuto`, `importo_pagato`, `stato`, `scadenza`, `competenza_da`/`_a`, `utility_period`, `giorni_presenza`, `is_aggiustamento` | addebito unificato → [receivable](/domain/receivable.md) |
| `BankTransaction` | `data`, `descrizione`, `importo`, `owner_account` | movimento bancario importato |
| `BankTransactionAllocation` | `bank_transaction`, `receivable`, `importo` | ponte M:N BT↔Receivable |
| `UtilityBill` | `immobile`, `supplier`, `prodotto`, `periodo_da`/`_a`, `importo_totale`, `consumo`, `file_pdf`, `expense` (1:1) | bolletta |
| `AnnualUtilityCost` | `voce`, `anno`, `importo_annuale`, `valid_from`/`_to` | costo annuale a forfait (es. TARI) |
| `UtilityChargePeriod` | `periodo_da`/`_a`, `criterio_ripartizione`, `stato`, `tot_luce/gas/tari/altro`, `giorni_totali`, `utility_bills` (M2M), `annual_utility_costs` (M2M), `data_invio`, `avvisi_inviati_at` | periodo di addebito utenze |
| `Supplier` | `nome`, `tipo`, `partita_iva` | fornitore |
| `ExpenseCategory` | `nome`, `codice`, `ripartibile_inquilini` | categoria spesa |
| `Expense` | `data`, `category`, `importo`, `anticipata_da_owner`, `ripartibile_su_inquilini`, `is_straordinaria`, `riferimento_quota_owner` | spesa |
| `TenantCondominioRate` | `contract`, `valid_from`/`_to`, `importo_mensile` | quota condominio a carico inquilino (data-driven) |

# Vedi anche

- [Riconciliazione](/domain/riconciliazione.md), [Calcolo utenze](/domain/calcolo-utenze.md),
  [Generazione affitti](/domain/generazione-affitti.md), [Conguaglio](/domain/conguaglio.md).
