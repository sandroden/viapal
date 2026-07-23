---
type: Decision
title: Segni concordi (allocazioni)
description: Allocazione, BankTransaction e Receivable devono concordare in segno.
tags: [decision, invariant, riconciliazione, deposito]
timestamp: 2026-07-08T00:00:00Z
---

# Invariante

In una riconciliazione, `BankTransactionAllocation.importo`, il `BankTransaction`
e il [`Receivable`](/domain/receivable.md) devono essere **concordi in segno**.

- Incasso ordinario (affitto/utenze): tutti **positivi** (denaro che entra).
- **Restituzione [deposito](/domain/deposito.md)**: tutti **negativi** (denaro che
  esce verso l'inquilino).

# Motivazione

Segni discordi producono saldi incoerenti e conguagli sbagliati. Vincolare la
concordanza rende la contabilità verificabile per costruzione (la somma delle
allocazioni ha lo stesso segno del movimento).

# Vedi anche

- [Riconciliazione](/domain/riconciliazione.md), [Deposito](/domain/deposito.md).
