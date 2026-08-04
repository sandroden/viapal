---
type: Domain Logic
title: Calcolo utenze
description: Da bolletta a periodo di addebito con pro-rata giorni, pinning e invio avvisi.
resource: backend/apps/billing/calc/utility.py
tags: [domain, utenze, utility, billing]
timestamp: 2026-08-04T00:00:00Z
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

# Acquisizione della bolletta (parsing PDF)

`billing/management/commands/riparsa_bollette_pdf.py` estrae importo, periodo,
data emissione, consumo, fornitore e prodotto dal testo di `pdftotext -layout`
(`estrai_da_testo`, testabile senza PDF). Template riconosciuti: Acea/Wind3
(date numeriche), Enel (mesi abbreviati), **Iren** (mesi estesi, "Fattura n.",
"Consumo totale fatturato nel periodo"). Stessa funzione dietro l'upload UI
(`UtilityBillViewSet.create`) e il command `carica_bollette_scanner`.

Due regole imparate sul campo:

- il **prodotto si deduce dai codici di fornitura** (POD `IT…E…` → luce, PDR →
  gas), non dalla prosa: le bollette gas Edison citano l'energia elettrica nel
  testo sui bonus sociali e venivano classificate "luce";
- il **PDF vince sul nome file**: in archivio esistono bollette gas chiamate
  `utenze-mz-luce-…`.

# Emissione e avvisi

`billing/calc/avvisi.py`: `costruisci_avvisi_utenze` / `invia_avvisi_utenze`
generano gli avvisi per inquilino (email HTML + testo) con QR EPC (GiroCode) per
il bonifico. Flusso frontend in `/p/utenze`; anteprima per-mese prima dell'emissione.

# Vedi anche

- [Conguaglio](/domain/conguaglio.md) — le utenze reali confluiscono nel conguaglio.
- [Conto destinazione / QR](/domain/riconciliazione.md).
