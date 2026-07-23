---
type: Domain Logic
title: Deposito cauzionale
description: Versamento e restituzione del deposito, con trigger da data prevista.
resource: backend/apps/properties/models/tenant.py
tags: [domain, deposito, billing]
timestamp: 2026-07-23T00:00:00Z
---

# Overview

Il deposito (ex "caparra" — rinominato "deposito" ovunque) è versato
dall'inquilino a garanzia e restituito all'uscita. I campi vivono su
`TenantProfile`.

# Campi e trigger

| Campo | Ruolo |
|-------|-------|
| `deposito_versato` | importo versato all'ingresso |
| `data_versamento_deposito` | data del versamento |
| `data_restituzione_prevista` | **trigger**: alla sua valorizzazione si genera il Receivable di restituzione |
| `deposito_da_restituire` | override opzionale (se si restituisce importo diverso dal versato) |

# Versamento a rate (dilazione)

Il versamento può essere **dilazionato**: N Receivable DEPOSITO positivi
("Deposito (versamento) — rata i/N") con scadenze diverse, struttura DB
invariata. Li crea l'action `POST room-assignments/prima-assegnazione/`
(che in un'unica transazione crea assignment, ciclo di fatturazione,
rate e quota condominio specifica). Ordine anti-duplicazione con i
signal di `properties/signals.py`: l'assignment è salvato quando
`deposito_versato` è ancora 0 (signal no-op), le rate sono create a
mano, e `deposito_versato` è valorizzato **per ultimo** — l'idempotenza
del signal ("esiste già un DEPOSITO positivo") vede le rate e non crea
il receivable unico. Un tenant con deposito già registrato non può
riceverne un secondo dall'action (400).

# Visibilità lato inquilino

`CAUSALI_OPERATIVE` (dashboard di gestione) esclude DEPOSITO per scelta:
i depositi non sono entrate operative. La **home inquilino** però
aggiunge esplicitamente i DEPOSITO con `importo_dovuto > 0` al blocco
`da_pagare` (tipo API `"deposit"`): l'inquilino le paga come ogni altro
addebito, QR bonifico incluso (conto utenze della proprietà). Il flusso
"Ho pagato" passa da `/api/v1/deposit-charges/` (read-only +
dichiara/conferma pagato, sole rate positive). Le restituzioni
(negative) non compaiono mai fra i "da pagare".

# Restituzione

La restituzione è un [Receivable](/domain/receivable.md) con causale dedicata e
**segno negativo** (esce denaro verso l'inquilino): allocazione, BT e Receivable
tutti negativi — vedi [segni concordi](/decisions/segni-concordi.md). La
generazione dell'addebito di restituzione è esplicita dal frontend. Esiste una
pagina/endpoint di rendiconto deposito.

# Vedi anche

- [Receivable](/domain/receivable.md), [Segni concordi](/decisions/segni-concordi.md).
