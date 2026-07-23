---
type: Domain Logic
title: Generazione affitti
description: Creazione dei canoni mensili con pro-rata, quota condominio e anniversary.
resource: backend/apps/billing/calc/rent.py
tags: [domain, affitti, rent, billing]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

`billing/calc/rent.py` genera i [Receivable](/domain/receivable.md) di causale
AFFITTO per una `RoomAssignment` in un dato mese. Funzione principale:
`genera_pagamenti_mese`; comando: `genera_rent_payments`.

# Regole di calcolo

- **Canone**: da `RoomAssignment.canone_mensile`.
- **Pro-rata** all'ingresso/uscita nel mese: `_giorni_mese`, giorni di presenza
  sul totale del mese; l'importo è arrotondato (`_arrotonda`).
- **Quota condominio**: aggiunta dalla `TenantCondominioRate` valida per la data
  di competenza (`_quota_condominio_per`). È **data-driven**, non una costante nel
  codice: i valori storici (es. 70€ fino al 2025, 90€ dal 2026) sono dati seed.
- **Anniversary / periodo**: `_anniversary_periodo` gestisce cicli non solari.
- **Uscita anticipata**: `aggiustamento_uscita` crea un Receivable di rettifica
  (`is_aggiustamento=True`).

# Interazione con gli incassi

La rigenerazione **non sovrascrive** i Receivable che hanno già allocazioni vive
— [guardia allocations](/decisions/guardia-allocations.md). `--force` rispetta
comunque questa invariante.

# Vedi anche

- [Receivable](/domain/receivable.md), [Conguaglio](/domain/conguaglio.md).
