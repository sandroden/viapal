---
type: Playbook
title: Import dati storici
description: Comandi per popolare/riconciliare i dati contabili pregressi.
resource: backend/apps/billing/management/commands/
tags: [playbook, import, storico, data]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

La contabilità pregressa (2023–2024) viene ricostruita con management command
idempotenti, da rieseguire anche in produzione. Restano alcune riconciliazioni
**manuali** che i comandi non coprono.

# Comandi principali

| Comando | Scopo |
|---------|-------|
| `importa_contabilita_xlsx` | libro mano `Contabilità.xlsx` (BT sintetiche, bollette, TARI) |
| `importa_utenze_da_xlsx` | bollette storiche da xlsx |
| `pin_bollette_storiche` | pinning periodi utenze già inviati |
| `riconcilia_bonifici` | matching automatico BT↔Receivable |
| `riconcilia_storico_manuale` | 6 abbinamenti forensi inquilini passati (idempotente, fail-safe) |
| `salda_con_resti` | imputa i resti bonifici |
| `genera_conguagli_storici` / `genera_storico` | conguagli e storico |
| `popola_depositi_storici` | depositi cauzionali pregressi |
| `assegna_incassi_da_csv` | incassi da CSV |

# Note operative

- **[Banca vince sempre](/decisions/banca-vince-sempre.md)** e
  **[guardia allocations](/decisions/guardia-allocations.md)** valgono anche in import.
- Alcune riconciliazioni restano manuali (utenze, affitti, cauzioni): non forzare
  i comandi su record scoperti/orfani noti.
- Upload bollette in prod richiede `poppler-utils` (Dockerfile) + encoding utf-8
  esplicito; PDF organizzati in `bollette/<immobile>/<anno>/<mese>`.

# Vedi anche

- [Calcolo utenze](/domain/calcolo-utenze.md), [Riconciliazione](/domain/riconciliazione.md).
