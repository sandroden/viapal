---
type: Domain Logic
title: Generazione affitti
description: Creazione dei canoni mensili con pro-rata, quota condominio e anniversary.
resource: backend/apps/billing/calc/rent.py
tags: [domain, affitti, rent, billing]
timestamp: 2026-08-03T00:00:00Z
---

# Overview

`billing/calc/rent.py` genera i [Receivable](/domain/receivable.md) di causale
AFFITTO per una `RoomAssignment` in un dato mese. Funzione principale:
`genera_pagamenti_mese`; comando: `genera_rent_payments`.

# Regole di calcolo

- **Canone**: da `RoomAssignment.canone_mensile`.
- **Pro-rata** all'ingresso/uscita nel mese: `_giorni_mese`, giorni di presenza
  sul totale del mese; l'importo è arrotondato (`_arrotonda`).
- **Quota condominio**: aggiunta da `_quota_condominio_per(assignment, data)`.
  È **data-driven**, non una costante nel codice, e risolta così: righe
  `TenantCondominioRate` dell'**immobile** dell'assignment (`property`),
  valide alla data di competenza; una riga con
  `tenant` valorizzato è un'**eccezione per quell'inquilino** e prevale
  sulla riga base (`tenant` NULL); a parità vince la `valid_from` più
  recente; **mai la somma** di più righe. Caso reale: base 90€ dal 2026,
  eccezione 70€ per i nuovi ingressi (non responsabili degli extra
  riscaldamento pregressi). Prima del fix 2026-07 la funzione sommava
  tutte le quote valide alla data senza filtro per immobile: sarebbe
  esploso alla seconda proprietà con quote configurate.
  Dal 2026-08 la quota pende dall'immobile e non più dal contratto: su una
  casa appena creata (contratto assente o con decorrenza futura) la prima
  assegnazione con quota falliva con "Nessun contratto attivo". Il
  contratto resta come riferimento facoltativo. Le quote si gestiscono da
  `/api/v1/quote-condominio/` (tab Spese della casa), oltre che in prima
  assegnazione.
- **Anniversary / periodo**: `_anniversary_periodo` gestisce cicli non solari.
- **Uscita anticipata**: `aggiustamento_uscita` crea un Receivable di rettifica
  (`is_aggiustamento=True`).

# Interazione con gli incassi

La rigenerazione **non sovrascrive** i Receivable che hanno già allocazioni vive
— [guardia allocations](/decisions/guardia-allocations.md). `--force` rispetta
comunque questa invariante.

# Vedi anche

- [Receivable](/domain/receivable.md), [Conguaglio](/domain/conguaglio.md).
