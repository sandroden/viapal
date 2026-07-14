---
type: Decision
title: Guardia allocations
description: Un Receivable con allocazioni vive non viene mai sovrascritto dai ricalcoli.
tags: [decision, invariant, riconciliazione]
timestamp: 2026-07-08T00:00:00Z
---

# Invariante

Un [`Receivable`](/domain/receivable.md) che ha **allocazioni bancarie vive**
(`BankTransactionAllocation`) non viene sovrascritto né rigenerato dai ricalcoli:

- `calcola_conguaglio`
- `genera_rent_payments` (anche con `--force`)

# Motivazione

Una volta che un addebito è stato collegato a un incasso reale, riscriverlo
romperebbe la contabilità (importi, segni, corrispondenza col bonifico). Il dato
riconciliato è "sacro": i ricalcoli lavorano solo su ciò che è ancora libero.

# Applicazione

Ogni funzione che rigenera o azzera Receivable deve **controllare la presenza di
allocazioni prima di toccare il record**. È una guardia da preservare in ogni
nuova operazione batch.

# Vedi anche

- [Riconciliazione](/domain/riconciliazione.md), [Conguaglio](/domain/conguaglio.md),
  [Generazione affitti](/domain/generazione-affitti.md).
