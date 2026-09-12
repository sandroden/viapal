---
type: Playbook
title: Import dati storici
description: Comandi per popolare/riconciliare i dati contabili pregressi.
resource: backend/apps/billing/management/commands/importa_contabilita_xlsx.py
resources:
  - backend/apps/billing/management/commands/importa_contabilita_xlsx.py
  - backend/apps/billing/management/commands/riconcilia_bonifici.py
  - backend/apps/billing/management/commands/riconcilia_storico_manuale.py
  - backend/apps/billing/management/commands/pin_bollette_periodi_emessi.py
  - backend/apps/billing/management/commands/genera_storico.py
tags: [playbook, import, storico, data]
generated:
  by: process:okf-migrate
  at: 2026-09-05T00:00:00Z
---

# Overview

La contabilità pregressa (2023–2024) viene ricostruita con management command
idempotenti, da rieseguire anche in produzione. Restano alcune riconciliazioni
**manuali** che i comandi non coprono.

Dalla multiproprietà (2026-07) i comandi di import accettano `--property`
(id **o slug** dell'immobile, `resolve_property_cli`): senza, alcuni si
fermano o lavorano sul solo immobile esistente. Non lanciare mai due comandi
di scrittura in parallelo sullo stesso immobile.

# Comandi principali

| Comando | Scopo |
|---------|-------|
| `importa_contabilita_xlsx` | libro mano `Contabilità.xlsx` (BT sintetiche, bollette, TARI) |
| `importa_utenze_da_xlsx` | bollette storiche da xlsx |
| `carica_bollette_scanner` | PDF da `~/scanner` → `UtilityBill` (nome file = `numero_fattura`, metadati dal PDF) |
| `riparsa_bollette_pdf` | riestrae i metadati dai PDF già caricati |
| `pin_bollette_storiche` | aggancia una bolletta al periodo **aperto** che la contiene |
| `pin_bollette_periodi_emessi` | riempie la M2M dei periodi **già emessi** che ne sono privi (dry-run di default) |
| `genera_storico` | Receivable AFFITTO per tutti i mesi dei contratti (`--dal`/`--al`) |
| `genera_conguagli_storici` | `UtilityChargePeriod` mensili + conguagli persistiti |
| `riconcilia_bonifici` | matching automatico BT↔Receivable; `--reset` **cancella tutte** le allocazioni e riporta ad ATTESO (unica deroga voluta alla guardia allocations); sweep delle allocazioni con causale incoerente; valorizza `incassato_da_owner` dai conti |
| `riconcilia_storico_manuale` | 6 abbinamenti forensi inquilini passati (lista chiusa, idempotente, fail-safe) |
| `salda_con_resti` | imputa i resti bonifici di un inquilino ai suoi scoperti |
| `assegna_incassi_da_csv` | `incassato_da_owner` da estratti conto CSV (bonifico sul conto X ⇒ incassato da X) |
| `popola_depositi_storici` (app properties) | depositi cauzionali pregressi |
| `inserisci_spese_condominio_tari` | rate condominio + TARI annuale come `Expense` (dati 2026-05-02) |
| `inserisci_conguaglio_condominiale` | **storico, già eseguito**: con `--pagato` marca PAGATO senza incassante e oggi viola `receivable_pagato_ha_incassante` — non rieseguire |

# Comandi di risanamento (2026-07/08)

| Comando | Scopo |
|---------|-------|
| `riallinea_dichiarati` | riporta `importo_pagato` dei DICHIARATO alla copertura reale (prima `dichiara_pagato` lo sovrascriveva col dovuto) |
| `sana_incassi_senza_incassante` | lista chiusa di ricostruzioni dei PAGATO senza incassante; da eseguire **prima** della migration del vincolo — [incasso sempre attribuito](/decisions/incasso-sempre-attribuito.md) |
| `sana_allocazioni_eccedenti` | riduce le allocazioni che superano l'importo della BT (dalla più recente) e riallinea; dry-run, `--apply`, `--bt` — [allocazioni non eccedenti](/decisions/allocazioni-non-eccedenti.md) |

# Note operative

- **[Banca vince sempre](/decisions/banca-vince-sempre.md)** e
  **[guardia allocations](/decisions/guardia-allocations.md)** valgono anche in import.
- Alcune riconciliazioni restano manuali (utenze, affitti, cauzioni): non forzare
  i comandi su record scoperti/orfani noti.
- Le BT **sintetiche** (libro mano, incassi non monetari) sono riconoscibili
  dalla nota: nell'estratto conto reale non esistono.
- Upload bollette in prod richiede `poppler-utils` (Dockerfile) + encoding utf-8
  esplicito; PDF organizzati in `bollette/<immobile>/<anno>/<mese>`.
- Gli import storici fatti *dopo* la creazione dei periodi passano la guardia
  `created_at` dell'attribuzione retroattiva: è `RETRO_FINESTRA_MESI` a
  tenerli fuori dalla ripartizione corrente (vedi [calcolo utenze](/domain/calcolo-utenze.md)).

# Vedi anche

- [Calcolo utenze](/domain/calcolo-utenze.md), [Riconciliazione](/domain/riconciliazione.md).
