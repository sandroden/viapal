---
type: Decision
title: Unificazione in Receivable
description: RentPayment + UtilityCharge + ExtraCharge fusi in un unico Receivable con causale.
tags: [decision, receivable, refactor]
timestamp: 2026-07-08T00:00:00Z
---

# Decisione

Fondere i tre modelli di addebito (`RentPayment`, `UtilityCharge`, `ExtraCharge`)
in un unico modello [`Receivable`](/domain/receivable.md), distinto dal campo
`causale`. Il legame con gli incassi diventa **M:N** tramite
`BankTransactionAllocation`.

# Motivazione

- Un inquilino spesso paga affitto + utenze con **un unico bonifico**: modellare
  gli addebiti separati rendeva impossibile allocare pulito un incasso cumulativo.
- La logica di riconciliazione, saldo e conguaglio diventa uniforme su un solo tipo.

# Conseguenze

- API e frontend mantenuti **retrocompatibili** durante la transizione.
- Tutte le nuove causali (registrazione, restituzione deposito, extra) sono
  varianti di Receivable, non nuovi modelli.

# Vedi anche

- [Receivable](/domain/receivable.md), [Riconciliazione](/domain/riconciliazione.md).
