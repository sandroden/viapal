---
type: Domain Logic
title: Riconciliazione bonifici
description: Matching e allocazione dei movimenti bancari sugli addebiti (M:N).
resource: backend/apps/billing/calc/matching.py
tags: [domain, riconciliazione, matching, billing]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

Riconciliare = collegare i `BankTransaction` (incassi reali) ai
[Receivable](/domain/receivable.md) (addebiti). Il collegamento è **M:N** via
`BankTransactionAllocation`, ciascuna con il proprio `importo`. Un bonifico può
coprire più addebiti (pagamento unico), un addebito può essere coperto da più bonifici.

# Matching automatico

`billing/calc/matching.py`:

- `classifica_descrizione` / `riconosci_tenant` — inferiscono l'inquilino dalla
  descrizione del movimento (keyword per tenant).
- `finestra_match` — finestra temporale plausibile attorno alla scadenza del Receivable.
- `candidati_bonifici_per` / `trova_bonifico_per` — cercano i BT compatibili.
- `alloca_bonifico` — crea le allocazioni.
- `receivables_compagni` / `trova_receivables_per_bt` — dato un BT, gli addebiti coprbili.

Il matching è un **suggeritore**: la conferma passa dalla UI di riconciliazione.

# UX di riconciliazione (frontend)

`ProprietarioRiconciliazione.vue` è simmetrica: allocazioni esplicite vs
automatiche, modalità "creazione" vs "vedi chi paga", banner per BT fuori dal
filtro corrente. Carica **tutte le pagine** (`fetchAllPaginated`) — vedi il rischio
[cap paginazione](/decisions/banca-vince-sempre.md) sotto e nelle liste DRF.

# Credito (resti bonifici)

I resti di bonifici non ancora imputati sono un **credito** dell'inquilino:
nella home inquilino il pagamento unico scala il credito (importo netto = lordo −
credito), senza generare uno sbilancio a favore della proprietà.

# Invarianti

- **[Banca vince sempre](/decisions/banca-vince-sempre.md)**: sull'import, il dato
  bancario prevale; la vecchia descrizione va nelle note.
- **[Guardia allocations](/decisions/guardia-allocations.md)**: un Receivable con
  allocazioni vive non viene sovrascritto dai ricalcoli.
- **[Segni concordi](/decisions/segni-concordi.md)**: allocazione, BT e Receivable
  concordi in segno (restituzione deposito = tutti negativi).

# Diagnosi "non abbinati"

Se Receivable e BT non combaciano, spesso **manca l'anagrafica** (canone, quota
condominio) più che l'azione di riconciliazione.
