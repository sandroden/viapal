---
type: Domain Logic
title: Riconciliazione bonifici
description: Matching e allocazione dei movimenti bancari sugli addebiti (M:N).
resource: backend/apps/billing/calc/matching.py
resources:
  - backend/apps/billing/calc/matching.py
  - backend/apps/billing/views/banca.py
  - backend/apps/billing/views/receivables.py
  - backend/apps/billing/signals.py
  - backend/apps/billing/calc/incassi.py
  - backend/apps/billing/models/payments.py
tags: [domain, riconciliazione, matching, billing]
generated:
  by: process:okf-migrate
  at: 2026-09-05T00:00:00Z
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

# Scrittura delle allocazioni

Tre strade, tutte in `billing/views.py`, tutte atomiche:

| Endpoint | Cosa fa |
|----------|---------|
| `POST /api/v1/reconciliations/` (`ReconciliationBulkView`) | sostituisce **in blocco** le allocazioni delle BT in `replace_for_transactions` con quelle in `items`; una BT presente in `items` ma non nella lista da sostituire è 400 (niente allocazioni orfane); valida segni e somme (sotto); riallinea esplicitamente i Receivable toccati, vecchi e nuovi, perché `bulk_create` non emette `post_save` |
| `POST receivables/<pk>/registra-pagamento/` | data + importo + conto → BT + allocazione via `calc/incassi.registra_incasso`: alloca al massimo il residuo, l'eccedenza resta sulla BT come "parziale"/credito; 409 se già pagato |
| `POST receivables/<pk>/conferma_pagato` | stesso motore, dalla pagina Ritardi; il conto è obbligatorio e deve essere [in uso sull'immobile](/domain/conti-per-immobile.md) |

`rifiuta_pagato` non scrive allocazioni: rimette l'addebito alla verità delle
allocazioni esistenti (`_riallinea_receivable`) e annota il rifiuto in `note`.
`dichiara_pagato` (inquilino) non tocca `importo_pagato`: la copertura resta
quella bancaria.

# Stato di riconciliazione di una BT

`BankTransaction.stato_riconciliazione` (`models/payments.py`), segno-aware
sulla **somma algebrica** delle allocazioni: `vuoto` (nessuna), `parziale`,
`pieno` (somma ≥ importo per le entrate, ≤ per le uscite), `sovra` (somma oltre
l'importo di più di `TOLLERANZA_ALLOC` = 0,01 €, o di verso opposto alla BT).
`residuo` conserva il segno della BT. I queryset `non_riconciliate()` /
`riconciliate()` usano la stessa regola; una BT a importo 0 è "pieno" (nulla da
abbinare) salvo che abbia allocazioni (`sovra`). Nel FE `sovra` è il chip
*eccedente*, in admin un'icona rossa.

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
- **[Segni concordi](/decisions/segni-concordi.md)**, nella forma
  **rilassata**: ogni allocazione ha il segno del `importo_dovuto` del suo
  Receivable (regola assoluta); il segno della BT deve coincidere solo con
  quello della **somma** delle sue allocazioni. Restituzione deposito = tutti
  negativi; restituzione con trattenuta = BT −984 ↔ alloc −1060 + alloc +76,
  valida. Imposta da `reconciliations/` (400), dal formset admin, da
  `registra_incasso` e dal signal, che tratta come non coperto un Receivable
  con allocazioni di segno opposto al dovuto.
- **[Allocazioni non eccedenti](/decisions/allocazioni-non-eccedenti.md)**: la somma
  allocata non supera l'importo della BT (tolleranza 0,01 €) — verificata in
  `reconciliations/`, per costruzione in `registra_incasso`, e nell'admin anche
  quando si corregge l'importo di un movimento già riconciliato; lo sbilancio
  residuo è visibile come stato `sovra` e si ripara con
  `sana_allocazioni_eccedenti`.
- **[Incasso sempre attribuito](/decisions/incasso-sempre-attribuito.md)**: un
  Receivable arriva a `pagato` solo attraverso un'allocazione; `incassato_da_owner`
  lo scrive il signal dal conto della BT.

# Diagnosi "non abbinati"

Se Receivable e BT non combaciano, spesso **manca l'anagrafica** (canone, quota
condominio) più che l'azione di riconciliazione.
