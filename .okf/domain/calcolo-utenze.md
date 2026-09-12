---
type: Domain Logic
title: Calcolo utenze
description: Da bolletta a periodo di addebito con pro-rata giorni, pinning e invio avvisi.
resource: backend/apps/billing/calc/utility.py
resources:
  - backend/apps/billing/calc/utility.py
  - backend/apps/billing/calc/avvisi.py
  - backend/apps/billing/models/utilities.py
  - backend/apps/billing/views/utenze.py
  - backend/apps/billing/management/commands/riparsa_bollette_pdf.py
tags: [domain, utenze, utility, billing]
generated:
  by: process:okf-migrate
  at: 2026-09-05T00:00:00Z
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

Le assegnazioni `rinunciata` (chi non è mai entrato, vedi
[generazione affitti](/domain/generazione-affitti.md)) sono escluse **prima**
del conteggio dei giorni: se entrassero nel denominatore `sum_giorni`
diluirebbero in silenzio la quota di tutti gli altri (2026-09-03).

# Configurazione utenze per immobile (2026-08-06)

`PropertyUtilityService` (billing) dichiara per ogni casa quali voci esistono
e chi le gestisce: `voce` (luce/gas/acqua/tari) × `gestione`
(proprieta/inquilino); riga assente = la voce non esiste. Nessuna voce è
obbligatoria (un appartamento può avere tutto intestato all'inquilino).
Effetti:

- **completezza** del periodo (`_completezza` nel viewset): le attese sono le
  voci `gestione=proprieta`; `completo` = tutte le attese a bolletta presenti
  (la TARI annuale non blocca). La response espone `attese` per il wizard
  data-driven. Fallback per immobili senza righe: luce+gas+tari (storico).
- **voci fatturabili** del calcolo (`_voci_fatturabili`): sostituiscono la
  costante globale `VOCI_FATTURABILI` (che resta come fallback); da qui
  l'acqua entra nella ripartizione dove configurata (totali in `tot_altro`).
- una voce annuale configurata `inquilino` (TARI intestata a lui) non si
  ripartisce anche se l'`AnnualUtilityCost` esiste; un immobile configurato
  senza voci a bolletta ripartisce i soli costi annuali senza forzature.
- Config editabile da proprietari E **gestori** (`/api/v1/utenze-config/`,
  pannello "Utenze della casa" nel tab spese di /p/impostazioni).

# Attribuzione v3 day-based e conguagli retroattivi (2026-08-06)

`_attribuisci_bollette` non esclude più in blocco le bollette pinnate da un
altro periodo `inviato` (una bolletta a cavallo non perde la coda se i mesi si
emettono in ordine sparso): i giorni nei periodi inviati restano congelati lì,
gli altri contano dove cadono. In più la **quota retroattiva** (caso Edison):
i giorni che cadono in periodi inviati che NON hanno pinnato la bolletta — e
nati prima della bolletta (guardia `bill.created_at > periodo.created_at`, che
esclude gli import storici) — si ribaltano tutti sul periodo **target** (il
primo che copre il giorno dopo la fine dell'ultimo inviato). Il risultato
espone `arretrati` (bolletta, giorni, importo) mostrato come banner nel wizard.

Il ribaltamento vale **solo dentro `RETRO_FINESTRA_MESI`** (6 mesi, costante in
`calc/utility.py`): una bolletta che si chiude prima di quella finestra è
storia, non un conguaglio in ritardo, e non entra mai nella ripartizione del
mese corrente. La sola guardia `created_at` non bastava: gli import storici
fatti *dopo* la creazione dei periodi che coprono la passano (caso reale
2026-08: due segnaposto del libro mano 2023 gonfiavano la luce di luglio 2026
da 216,82 a 542,82). Gli inquilini di oggi ripartiscono le bollette di oggi.
Dettagli e casi limite: docs/piano-utenze-configurabili.md §8.

# Quota esclusa (voci a carico proprietà)

`UtilityBill.quota_esclusa` + `motivo_esclusione`: la parte della bolletta che
NON va addebitata agli inquilini (canone RAI, aumento potenza, allacci). Il
calcolo usa sempre `importo_ripartibile = importo_totale − quota_esclusa`, in
entrambi i rami di `_attribuisci_bollette` (pinned: quota intera; pro-rata:
stessa frazione giorni per netto ed escluso). Il risultato espone
`totale_escluso` + `esclusioni` e i `tot_*` persistiti sono netti.

Scelte deliberate: l'**Expense mirror resta al lordo** (il proprietario ha
pagato tutto → la differenza resta a suo carico senza scritture extra); le
**statistiche €/kWh usano il netto**; l'inquilino **vede l'esclusione** (riga
"Escluso, a carico proprietà" in card e nota nell'email, placeholder
`{{esclusioni}}`/`{{esclusioni_html}}`). Edit dal FE: matita sulla card in
`/p/utenze` (dialog `BollettaEditDialog`, PATCH `utility-bills/`); modificare
una bolletta di un periodo già `inviato` NON ricalcola i Receivable (warning UI).

# Quota TARI esclusa: i posti sfitti restano alla proprietà (2026-09-01)

Come per le bollette, anche la TARI può avere una parte che non si ripartisce:
la fetta dei posti che non si è riusciti ad affittare. Il valore sta sul
**periodo** (`UtilityChargePeriod.quota_esclusa_tari` +
`motivo_esclusione_tari`), non sull'`AnnualUtilityCost`, per due ragioni:

- lo sfitto è un fatto **mensile** (una stanza vuota a marzo può essere piena
  ad aprile);
- la vista inquilino ricalcola il conguaglio al volo: solo un valore salvato
  sul mese fa tornare gli stessi numeri anche a distanza di anni.

Meccanica: `POST utility-periods/<id>/esclusione-tari/` (tetto = TARI lorda
del mese); `calcola_conguaglio_periodo` sottrae la quota dalla voce `tari`
prima della ripartizione, con clamp difensivo (mai una voce negativa: se la
TARI del mese è calata sotto la quota, la voce sparisce) e aggiunge una riga
in `esclusioni` con `bill_id=None`, quindi compare nell'avviso email e nella
pagina dell'inquilino come le esclusioni delle bollette. Su un periodo già
`inviato` la modifica è ammessa ma gli addebiti creati non si aggiornano da
soli (il dialog `EsclusioneTariDialog` e la notifica lo dicono). Nel wizard la
card TARI è editabile con aiuto al calcolo (n posti sfitti su m → quota).

# Pinning: "una volta inviato non si tocca più"

In modalità pinning una bolletta agganciata a un **solo** periodo vale per
intero (è l'override manuale: "questa bolletta la voglio qui"), mentre una
agganciata a **più** periodi si ripartisce pro-rata sui giorni, come la quota
propria: così la bimestrale sta in entrambi i mesi senza doppia imputazione.
La trappola resta per chi pinna a mano una bolletta su un solo periodo che non
la copre tutta.

Regola centrale: quando un periodo è **inviato** (`data_invio` valorizzato), i
suoi importi sono **congelati** (pinning tramite le M2M). Le bollette arrivate in
ritardo/retroattive si ribaltano sull'**ultimo periodo ancora aperto**, non su
quelli già inviati.

La M2M `utility_bills` è però scritta **solo dall'emissione** (`persist=True`):
i periodi nati dagli import hanno i `tot_*` ma nessuna bolletta agganciata, e
l'abbinamento che si vede in UI è calcolo al volo per overlap di date, non
dato. Le bollette restano quindi "libere" e candidabili al ribaltamento
retroattivo. `pin_bollette_periodi_emessi` riempie il buco sui periodi già
emessi, agganciando **tutte** le bollette che li intersecano — bimestrali
comprese, che finiscono su entrambi i mesi coperti (scelta di Sandro: è la
verità documentale). Il piano si valuta in blocco (quanto vale una bimestrale
su maggio dipende dal fatto che anche giugno la agganci) e si ferma dove il
pinning allontanerebbe il ricalcolo dai `tot_*` addebitati, verificato dentro
un savepoint; avvicinarsi invece va bene (un periodo che oggi riceve arretrati
fantasma torna al suo importo vero). Resta fuori solo chi ha una voce
addebitata di cui a DB non esiste alcuna bolletta: lì manca il dato, non
l'aggancio.

`pin_bollette_storiche` lavora invece bolletta→periodo, e solo su periodi
**aperti** che la contengono: non ribalta più sul "primo periodo dopo"
(regola v1, precedente alla day-based) e non tocca i periodi inviati — così
com'era avrebbe pinnato le bollette 2022 sul febbraio 2023 già emesso.

# Acquisizione della bolletta (parsing PDF)

`billing/management/commands/riparsa_bollette_pdf.py` estrae importo, periodo,
data emissione, consumo, fornitore e prodotto dal testo di `pdftotext -layout`
(`estrai_da_testo`, testabile senza PDF). Template riconosciuti: Acea/Wind3
(date numeriche), Enel (mesi abbreviati), **Iren** (mesi estesi, "Fattura n.",
"Consumo totale fatturato nel periodo"), **Magis Energia** ("Periodo oggetto di
fatturazione / Dal … al …", "Fattura n° … del …", "Consumi … Smc"). Stessa
funzione dietro l'upload UI (`UtilityBillViewSet.create`) e il command
`carica_bollette_scanner`.

L'ordine dei pattern conta: i fallback **posizionali** (il consumo Enel, cercato
dopo "Totale da pagare") vanno provati per ultimi, perché su altri layout
pescano numeri plausibili ma sbagliati.

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

## Completezza e ripartizione parziale forzata

L'emissione richiede di norma **almeno una bolletta luce E una gas** nel periodo
(`_completezza` nel viewset: la TARI non concorre). Due gate distinti:

- viewset `emetti` → 400 se incompleto (gate hard);
- `calcola_conguaglio_periodo` → `skipped="no_bollette_luce_gas"` se non c'è
  **nessuna** bolletta luce/gas (regola 2026-05-02: niente conguagli solo-TARI).

Eccezione (2026-08-06): il proprietario può **forzare la ripartizione parziale**
— fornitori con cadenza diversa (mensile vs bimestrale), bolletta non
disponibile, utenze intestate all'inquilino. `POST emetti {"forza": true}` e
`GET anteprima?forza=1` passano `forza_senza_bollette=True` al calcolo, che
allora ripartisce ciò che c'è (anche la sola TARI); un periodo davvero vuoto
risponde comunque 400 (`skipped="nessun_importo"`) e resta bozza. Nel FE il
bottone "Procedi comunque" (dialog di conferma) sblocca il wizard; un periodo
già emesso in forma parziale viene riconosciuto e non ripropone il lucchetto.

Corollario (2026-09-01): tutte le **ricostruzioni a posteriori** di un periodo
emesso — il dettaglio nell'avviso (`avvisi._risultato_calcolo`) e la pagina
utenze dell'inquilino (`UtenzeInquilinoView`) — chiamano il calcolo con
`persist=False, forza_senza_bollette=True`. Senza il flag un periodo emesso
solo-TARI tornava `skipped` e l'inquilino vedeva un periodo vuoto pur avendo
l'addebito. Chi aggiunge una nuova lettura di un periodo emesso deve fare lo
stesso: descrive ciò che è stato addebitato, non decide se addebitare.

# Vedi anche

- [Conguaglio](/domain/conguaglio.md) — le utenze reali confluiscono nel conguaglio.
- [Conto destinazione / QR](/domain/riconciliazione.md).
