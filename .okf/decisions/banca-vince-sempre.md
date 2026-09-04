---
type: Invariant
title: Banca vince sempre (import movimenti)
description: In import idempotente dei movimenti, il dato bancario prevale sempre.
resource: backend/apps/billing/views.py
resources:
  - backend/apps/billing/views.py
  - backend/apps/billing/serializers.py
  - scripts/carica_movimenti_api.py
tags: [decision, import, riconciliazione]
timestamp: 2026-09-05T00:00:00Z
---

# Decisione

Nell'import (bulk) dei movimenti bancari, in caso di conflitto **il dato della
banca prevale**: la descrizione/gli attributi provenienti dalla banca
sovrascrivono quelli locali; la vecchia descrizione viene conservata **nelle note**.
L'import è **idempotente**.

# Dove vive

`POST /api/v1/bank-transactions/bulk-import/`
(`BankTransactionBulkImportView` in `billing/views.py`; input
`BankTransactionBulkImportInputSerializer`); client:
`scripts/carica_movimenti_api.py` (CSV → API in HTTP Basic, con filtro di
pertinenza affitto e `--dry-run`).

| Regola | Dettaglio |
|--------|-----------|
| chiave naturale | `(owner_account, data, importo)`; a parità di chiave le righe in arrivo si appaiano **in ordine** con le BT già sul conto |
| riga senza corrispondente | creata |
| corrispondente con stessa descrizione | invariata |
| corrispondente con descrizione diversa | la descrizione della banca diventa quella ufficiale; la precedente va in `note` come riga `Precedente: …`, aggiunta **una sola volta** |
| BT in più nel DB | mai cancellate, conteggiate come `extra_db` |
| `dry_run` | riporta i conteggi senza scrivere |
| auth | `SessionAuthentication` + `BasicAuthentication` (lo script non gestisce il CSRF); permesso `IsPropertyMember` |
| conto | deve essere il proprio, oppure [in uso su un immobile](/domain/conti-per-immobile.md) di cui si è membri (403 altrimenti) |

# Motivazione

- La banca è la fonte di verità sui movimenti reali; le annotazioni manuali sono
  arricchimenti, non devono bloccare o falsare il riallineamento.
- L'idempotenza permette di rieseguire l'import senza duplicare.

# Rischio correlato: cap paginazione silenzioso

Le liste DRF a pagina singola (limit 200) troncano in **silenzio**. La
riconciliazione carica esplicitamente tutte le pagine (`fetchAllPaginated`).
Attenzione ad altre liste che potrebbero troncare senza avviso.

# Vedi anche

- [Riconciliazione](/domain/riconciliazione.md).
