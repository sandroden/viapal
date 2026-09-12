---
type: Invariant
title: Segni concordi (allocazioni)
description: Ogni allocazione ha il segno del Receivable che copre; la somma delle allocazioni di una BT ha il segno della BT.
resource: backend/apps/billing/signals.py
resources:
  - backend/apps/billing/signals.py
  - backend/apps/billing/calc/incassi.py
  - backend/apps/billing/views/banca.py
  - backend/apps/billing/admin.py
  - backend/apps/billing/models/payments.py
tags: [decision, invariant, riconciliazione, deposito]
generated:
  by: process:okf-migrate
  at: 2026-09-05T00:00:00Z
---

# Invariante

Due regole, una assoluta e una sulla somma:

1. `sign(BankTransactionAllocation.importo) == sign(Receivable.importo_dovuto)`
   per **ogni** allocazione (regola assoluta).
2. La **somma algebrica** delle allocazioni di una `BankTransaction` va nel
   verso della BT (entrata o uscita). Il segno della singola allocazione può
   differire da quello della BT.

Casi tipici:

- Incasso ordinario (affitto/utenze): tutti **positivi** (denaro che entra).
- **Restituzione [deposito](/domain/deposito.md)**: tutti **negativi** (denaro che
  esce verso l'inquilino).
- Partita compensata: BT −984 ↔ alloc −1060 sul Receivable di restituzione +
  alloc +76 sul Receivable utenze previsionali. Somma −984 = BT: valida.

La regola è stata **rilassata** rispetto alla formulazione originale
("BT, allocazione e Receivable tutti dello stesso segno") proprio per
ammettere la trattenuta sulla restituzione del deposito.

# Dove è imposta

| Punto | Cosa fa |
|-------|---------|
| `signals._riallinea_receivable` | somma delle allocazioni di segno opposto al dovuto ⇒ Receivable trattato come **non coperto** (ATTESO, derivati azzerati): un'allocazione discorde non chiude mai un addebito |
| `calc/incassi.registra_incasso` | rifiuta (`IncassoRifiutato`, 400) un importo di segno diverso dal residuo del Receivable; usato da `conferma_pagato` e `registra-pagamento/` |
| `views.py` — `POST reconciliations/` | 400 su alloc discorde col dovuto; 400 se la somma per BT è di segno opposto alla BT |
| `admin.BankTransactionAllocationInlineFormSet.clean` | stessa regola sulla somma, per chi passa dall'admin |
| `models/payments.BankTransaction.stato_riconciliazione` | somma di segno opposto alla BT ⇒ stato `"sovra"` (anomalia visibile, non muta) |

Non esiste un vincolo di database: la regola è applicativa e le vie di
scrittura sono quelle sopra più i management command (`riconcilia_bonifici`,
`salda_con_resti`, `riconcilia_storico_manuale`), che devono rispettarla da sé.

# Motivazione

Segni discordi producono saldi incoerenti e conguagli sbagliati. Vincolare la
concordanza rende la contabilità verificabile per costruzione (la somma delle
allocazioni ha lo stesso segno del movimento).

# Vedi anche

- [Riconciliazione](/domain/riconciliazione.md), [Deposito](/domain/deposito.md),
  [Allocazioni non eccedenti](/decisions/allocazioni-non-eccedenti.md).
