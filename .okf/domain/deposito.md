---
type: Domain Logic
title: Deposito cauzionale
description: Versamento e restituzione del deposito, con trigger da data prevista.
resource: backend/apps/properties/models/tenant.py
tags: [domain, deposito, billing]
timestamp: 2026-07-08T00:00:00Z
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

# Restituzione

La restituzione è un [Receivable](/domain/receivable.md) con causale dedicata e
**segno negativo** (esce denaro verso l'inquilino): allocazione, BT e Receivable
tutti negativi — vedi [segni concordi](/decisions/segni-concordi.md). La
generazione dell'addebito di restituzione è esplicita dal frontend. Esiste una
pagina/endpoint di rendiconto deposito.

# Vedi anche

- [Receivable](/domain/receivable.md), [Segni concordi](/decisions/segni-concordi.md).
