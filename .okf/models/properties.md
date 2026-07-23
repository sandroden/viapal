---
type: Django App
title: App properties
description: Anagrafica immobile, proprietari, quote e assegnazioni stanze.
resource: backend/apps/properties/models/
tags: [models, properties]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

Anagrafica: immobile, stanze, contratti, assegnazioni, proprietari e inquilini.
Reference strutturale — la logica sta nei concetti di [dominio](/domain/).
Tutti i modelli ereditano da `TimestampedModel` (`created_at`/`updated_at`).

# Modelli

| Modello | Campi chiave | Note |
|---------|--------------|------|
| `Property` | `nome`, `indirizzo`, `bank_account_utenze` (FK) | conto di domiciliazione utenze |
| `Room` | `property`, `nome`, `superficie_mq`, `foto` | stanza |
| `Contract` | `data_decorrenza`, `termine`, `regime_fiscale`, `default_pagatore_bollette` | contratto d'affitto |
| `RoomAssignment` | `room`, `tenant`, `valid_from`/`valid_to`, `canone_mensile`, `bank_account_affitto`, `costo_cessione`, `data_atto_cessione` | stanza↔inquilino nel tempo |
| `OwnerProfile` | `user` (1:1), `nominativo`, `codice_fiscale` | proprietario |
| `OwnershipShare` | `owner`, `valid_from`/`valid_to`, `quota` | quota di proprietà temporale |
| `OwnerBankAccount` | `owner`, `banca`, `iban`, `intestatario`, `attivo` | conto proprietario |
| `TenantProfile` | `user` (1:1), `giorno_pagamento_affitto`, `frequenza_conguagli`, `ciclo_fatturazione`, `deposito_versato`, `deposito_da_restituire`, `data_restituzione_prevista` | inquilino |
| `TenantDocument` | `tenant`, `tipo`, `file`, `data_scadenza` | CI/CF/passaporto/permesso/contratto |

# Vedi anche

- [Deposito](/domain/deposito.md) — `deposito_*` / `data_restituzione_prevista`.
- [Generazione affitti](/domain/generazione-affitti.md) — `canone_mensile`, `RoomAssignment`.
- `costo_cessione`: totale cessione stanza, split 50/50 (Receivable REGISTRAZIONE + Expense proprietari).
