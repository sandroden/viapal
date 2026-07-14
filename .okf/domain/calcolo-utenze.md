---
type: Domain Logic
title: Calcolo utenze
description: Da bolletta a periodo di addebito con pro-rata giorni, pinning e invio avvisi.
resource: backend/apps/billing/calc/utility.py
tags: [domain, utenze, utility, billing]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

Le utenze vengono ripartite tra gli inquilini per **giorni di presenza**. Le
bollette (`UtilityBill`) e i costi annuali (`AnnualUtilityCost`) confluiscono in
un `UtilityChargePeriod`, che genera i [Receivable](/domain/receivable.md) di
causale UTENZE. Codice: `billing/calc/utility.py`; avvisi: `billing/calc/avvisi.py`.

# Algoritmo (bolletta → periodo → inquilino)

1. Il periodo raccoglie le bollette (M2M `utility_bills`) e i forfait annuali
   (M2M `annual_utility_costs`), sommando `tot_luce/gas/tari/altro`.
2. Ripartizione **pro-rata sui giorni** di intersezione tra il periodo di
   competenza della bolletta e la presenza dell'inquilino (`_giorni_intersezione`).
3. Arrotondamento (`_arrotonda`) con ribaltamento dei resti.

# Pinning: "una volta inviato non si tocca più"

Regola centrale: quando un periodo è **inviato** (`data_invio` valorizzato), i
suoi importi sono **congelati** (pinning tramite le M2M). Le bollette arrivate in
ritardo/retroattive si ribaltano sull'**ultimo periodo ancora aperto**, non su
quelli già inviati. Comando `pin_bollette_storiche` per il pinning storico.

# Emissione e avvisi

`billing/calc/avvisi.py`: `costruisci_avvisi_utenze` / `invia_avvisi_utenze`
generano gli avvisi per inquilino (email HTML + testo) con QR EPC (GiroCode) per
il bonifico. Flusso frontend in `/p/utenze`; anteprima per-mese prima dell'emissione.

# Vedi anche

- [Conguaglio](/domain/conguaglio.md) — le utenze reali confluiscono nel conguaglio.
- [Conto destinazione / QR](/domain/riconciliazione.md).
