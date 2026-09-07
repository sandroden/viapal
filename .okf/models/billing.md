---
type: Django App
title: App billing
description: Addebiti (Receivable), incassi bancari, utenze e spese.
resource: backend/apps/billing/models/receivables.py
resources:
  - backend/apps/billing/models/receivables.py
  - backend/apps/billing/models/payments.py
  - backend/apps/billing/models/utilities.py
  - backend/apps/billing/models/expenses.py
tags: [models, billing]
timestamp: 2026-09-07T00:00:00Z
---

# Overview

Cuore contabile: addebiti verso inquilini, movimenti bancari, bollette/periodi
utenze e spese. La logica sta nei concetti di [dominio](/domain/).

Dalla multiproprietà (2026-07) `Supplier`, `ExpenseCategory`, `Expense`,
`AnnualUtilityCost`, `UtilityChargePeriod`, `PropertyUtilityService` e
`TenantCondominioRate` hanno la FK `property`; `UtilityBill` la chiama
`immobile`. `Receivable` la deriva da `assignment.room.property` e
`BankTransaction` **non ne ha una**: il suo unico aggancio a un immobile è
`owner_account.properties` (vedi [conti per immobile](/domain/conti-per-immobile.md)).

# Modelli

| Modello | Campi chiave | Note |
|---------|--------------|------|
| `Receivable` | `assignment` (PROTECT), `causale` (affitto/utenze/extra/deposito/registrazione), `descrizione`, `importo_dovuto`, `importo_pagato`, `stato`, `data_pagamento`, `incassato_da_owner`, `bank_account_destinazione`, `ricevuta`, `scadenza`, `competenza_da`/`_a`, `utility_period`, `giorni_presenza`, `is_aggiustamento`, `previsionale`, `conguaglio_di` (self-FK, PROTECT), `note` | addebito unificato → [receivable](/domain/receivable.md); vincoli `receivable_affitto_unique`, `receivable_utenze_unique`, `receivable_pagato_ha_incassante` (check) |
| `ReceivableComment` | `receivable`, `autore`, `testo` | commento libero, inoltrato via email |
| `BankTransaction` | `data`, `descrizione`, `importo` (+entrata/−uscita), `owner_account`, `note` | movimento bancario; `stato_riconciliazione` calcolato: `pieno`/`parziale`/`vuoto`/`sovra`; queryset `non_riconciliate()`/`riconciliate()` segno-aware; `TOLLERANZA_ALLOC` = 0,01 € |
| `BankTransactionAllocation` | `bank_transaction` (CASCADE), `receivable` (PROTECT), `importo` | ponte M:N BT↔Receivable, unica per coppia (`allocation_unique_pair`) |
| `UtilityBill` | `immobile`, `supplier`, `prodotto`, `numero_fattura`, `data_emissione`, `periodo_da`/`_a`, `importo_totale`, `quota_esclusa` + `motivo_esclusione`, `consumo`, `file_pdf`, `pagata_da_owner`, `expense` (1:1) | bolletta; con `pagata_da_owner` il signal crea/aggiorna l'`Expense` specchio (al lordo) |
| `AnnualUtilityCost` | `property`, `voce`, `anno`, `importo_annuale`, `valid_from`/`_to` | costo annuale a forfait (es. TARI) |
| `PropertyUtilityService` | `property`, `voce` (luce/gas/acqua/tari), `gestione` (proprieta/inquilino) | quali utenze esistono per la casa e chi le gestisce; riga assente = voce inesistente; unica per `(property, voce)` |
| `UtilityChargePeriod` | `property`, `periodo_da`/`_a`, `criterio_ripartizione`, `stato`, `tot_luce/gas/tari/altro` (netti), `giorni_totali`, `quota_esclusa_tari` + `motivo_esclusione_tari`, `nota_calcolo`, `utility_bills` (M2M), `annual_utility_costs` (M2M), `data_invio`, `avvisi_inviati_at` | periodo di addebito utenze; `data_invio` valorizzato = congelato |
| `Supplier` | `property`, `nome`, `tipo`, `partita_iva`, `contatto` | fornitore |
| `ExpenseCategory` | `property`, `nome`, `codice`, `ripartibile_inquilini` | categoria spesa, unica per `(property, codice)` |
| `Expense` | `property`, `data`, `category`, `supplier`, `importo`, `anticipata_da_owner`, `ripartibile_su_inquilini`, `is_straordinaria`, `riferimento_quota_owner`, `allegato` (media-private `spese/`, validator PDF/JPG/PNG ≤10 MB) | spesa; l'allegato è la fattura arrivata dopo, caricabile da /p/spese (il PATCH non pretende il conto) |
| `TenantCondominioRate` | `property`, `tenant` (opz.), `contract` (opz., SET_NULL), `valid_from`/`_to`, `importo_mensile` | quota condominio a carico inquilino (data-driven); appartiene all'immobile, il contratto è solo il documento in cui è pattuita |

# Vedi anche

- [Riconciliazione](/domain/riconciliazione.md), [Calcolo utenze](/domain/calcolo-utenze.md),
  [Generazione affitti](/domain/generazione-affitti.md), [Conguaglio](/domain/conguaglio.md).
