---
type: Decision
title: Banca vince sempre (import movimenti)
description: In import idempotente dei movimenti, il dato bancario prevale sempre.
resource: backend/apps/billing/management/commands/
tags: [decision, import, riconciliazione]
timestamp: 2026-07-08T00:00:00Z
---

# Decisione

Nell'import (bulk) dei movimenti bancari, in caso di conflitto **il dato della
banca prevale**: la descrizione/gli attributi provenienti dalla banca
sovrascrivono quelli locali; la vecchia descrizione viene conservata **nelle note**.
L'import è **idempotente**.

# Motivazione

- La banca è la fonte di verità sui movimenti reali; le annotazioni manuali sono
  arricchimenti, non devono bloccare o falsare il riallineamento.
- L'idempotenza permette di rieseguire l'import senza duplicare.

# Rischio correlato: cap paginazione silenzioso

Le liste DRF a pagina singola (limit 200) troncano in **silenzio**. La
riconciliazione carica esplicitamente tutte le pagine (`fetchAllPaginated`).
Attenzione ad altre liste che potrebbero troncare senza avviso.

# Vedi anche

- [Riconciliazione](/domain/riconciliazione.md).
