---
type: Invariant
title: Guardia allocations
description: Un Receivable con allocazioni vive non viene mai sovrascritto dai ricalcoli.
resource: backend/apps/billing/calc/rent.py
resources:
  - backend/apps/billing/calc/rent.py
  - backend/apps/billing/calc/utility.py
  - backend/apps/properties/views.py
  - backend/apps/billing/dashboard_views/deposito.py
tags: [decision, invariant, riconciliazione]
timestamp: 2026-09-07T00:00:00Z
---

# Invariante

Un [`Receivable`](/domain/receivable.md) che ha **allocazioni bancarie vive**
(`BankTransactionAllocation`) non viene sovrascritto né rigenerato dai ricalcoli:

- `calcola_conguaglio` / emissione utenze
- `genera_rent_payments` (anche con `--force`)
- rigenerazione da frontend e restituzione deposito (sotto)

# Dove è imposta

Non c'è un vincolo di database né un signal: è un `allocations.exists()`
**prima di ogni scrittura** in ciascuna funzione batch.

| Punto | Comportamento |
|-------|---------------|
| `calc/rent.genera_pagamenti_mese` | il Receivable esistente (o quello dello stesso mese su un altro assignment del tenant) con allocazioni è `skip_allocation` anche con `force`; finisce in `skippati_per_allocation` |
| `calc/utility._persist_receivables` (via `calcola_conguaglio_periodo(persist=True)`) | quota ricalcolata **non** scritta sul Receivable UTENZE allocato; riportata in `skipped` con importo esistente e calcolato |
| `properties/views.py` — `POST room-assignments/<id>/rigenera-receivable/` | rigenera con force e poi elimina gli orfani, ma **solo** quelli senza allocazioni (`skip_alloc_ids`) |
| `dashboard_views/deposito.crea_o_aggiorna_restituzione` | la riga di restituzione già riconciliata non si modifica da lì (409: "modificala dalla riconciliazione"); helper usato da `RestituzioneDepositoView` e dal `POST chiusura/`, che la genera solo se manca |

Deroga esplicita e voluta: `riconcilia_bonifici --reset` cancella **tutte** le
allocazioni per ripartire da zero — è distruttivo per definizione, non una
violazione. `sana_allocazioni_eccedenti` riduce allocazioni, non Receivable.

# Motivazione

Una volta che un addebito è stato collegato a un incasso reale, riscriverlo
romperebbe la contabilità (importi, segni, corrispondenza col bonifico). Il dato
riconciliato è "sacro": i ricalcoli lavorano solo su ciò che è ancora libero.

# Applicazione

Ogni funzione che rigenera o azzera Receivable deve **controllare la presenza di
allocazioni prima di toccare il record**. È una guardia da preservare in ogni
nuova operazione batch; il modo di segnalarla è restituire gli skip nel
risultato (mai in silenzio).

# Vedi anche

- [Riconciliazione](/domain/riconciliazione.md), [Conguaglio](/domain/conguaglio.md),
  [Generazione affitti](/domain/generazione-affitti.md).
