---
type: Domain Logic
title: Solleciti e registro comunicazioni
description: Email di riepilogo addebiti agli inquilini (canone del mese + pendenti a 15 giorni + voci dichiarate) e registro di cosa è stato inviato, a chi e con che esito.
resource: backend/apps/billing/calc/riepilogo.py
tags: [domain, solleciti, notifiche, email, inquilini]
timestamp: 2026-08-02T00:00:00Z
---

# Overview

Due cose distinte, introdotte insieme:

1. il **riepilogo addebiti**, l'unica email che parla di soldi in modo
   aggregato (`billing/calc/riepilogo.py`);
2. il **registro delle comunicazioni**, cioè `Notification` usata come archivio
   di *cosa è stato inviato* — successi e fallimenti.

Prima esisteva solo l'avviso utenze ([calcolo utenze](calcolo-utenze.md)),
legato a un singolo `UtilityChargePeriod`. Per l'affitto non partiva niente:
gli addebiti venivano generati e restavano lì.

# Destinatari e selezione

Per ogni `TenantProfile` dell'immobile si chiama
`billing.calc.posizione.posizione_inquilino(tenant, oggi, property)` — la
stessa funzione che alimenta la home dell'inquilino — e si partizionano gli
addebiti **aperti**:

| Blocco | Regola |
|--------|--------|
| **canone del mese** | l'item `rent` con competenza nel mese di `oggi` (aggiustamenti pro-rata inclusi: un moncone d'uscita è comunque il canone di quel mese). Se ce n'è più d'uno, vince la competenza più recente e gli altri passano tra i pendenti |
| **pendenti** | gli altri aperti con `scadenza <= oggi + giorni` (default **15**, opzione `--giorni`) |
| **in attesa di conferma** | gli addebiti in stato `dichiarato`, in una sezione separata |
| fuori finestra | non compaiono: l'app resta la fonte del conto completo |

Riceve chi ha il canone del mese **oppure** almeno un pendente. Chi ha solo
voci dichiarate compare in anteprima con `esito="niente_da_sollecitare"` e non
riceve nulla.

Gli inquilini **usciti** (nessuna assegnazione attiva) restano in anteprima
col badge "ex inquilino" ma **non ricevono**: `notificare=False`,
`esito="ex_inquilino"`. All'inizio ricevevano — "sono la popolazione da
sollecitare" — ma sul campo i loro arretrati si sono rivelati quasi sempre
partite storiche mai riconciliate (vedi
[riconciliazione](riconciliazione.md)): sollecitarli automaticamente
significa chiedere soldi per un buco di anagrafica. Restano visibili, spenti, perché il proprietario possa spuntarli
**uno per uno** dal frontend — `includi_ids` di `invia_riepiloghi`, campo
`includi` dell'endpoint. La riga di comando non ha modo di forzarli: è la
selezione simmetrica di `escludi_ids` (l'attivo si toglie, l'uscito si
aggiunge) e deve restare un gesto deliberato.

`da_sollecitare` distingue le due ragioni di `notificare=False`: c'è
qualcosa da chiedere (canone o pendenti) ma manca l'assegnazione, oppure non
c'è proprio nulla. `includi_ids` deroga solo alla prima.

Conseguenza voluta della soglia di 1 € in `billing/signals.py`: un residuo
sotto l'euro è già `PAGATO`, quindi gli spiccioli non entrano nei solleciti.

# Cosa la mail NON contiene

* **nessun totale**: invecchia (basta un bonifico nel frattempo) e l'app lo
  mostra già, aggiornato e al netto del credito;
* **nessun QR, nessun IBAN**: ogni voce ha il suo QR in `/i/`, dove l'importo
  è quello giusto. Un IBAN in chiaro nella mail invita a bonificare la cifra
  sbagliata;
* **nessuna riscrittura delle scadenze**. `invia_avvisi_utenze` le sposta a
  +14 giorni perché *è* l'atto che comunica per la prima volta un addebito
  appena emesso. Qui gli addebiti sono già emessi, ognuno con la sua scadenza,
  e la mail ne aggrega N: riscriverle azzererebbe i ritardi esistenti
  (falsando `giorni_ritardo`, il semaforo e la pagina Ritardi) e permetterebbe
  di cancellare un ritardo semplicemente rimandando il sollecito.

# Invio

Manuale, con anteprima, come per le utenze: `/p/riepilogo` chiama
`POST /api/v1/riepilogo-addebiti/invia/` in `dry_run=true` al mount, mostra il
testo reale di ogni email, permette di deselezionare per `tenant_id` e poi
invia.

Il comando `invia_riepilogo_addebiti` è **dry-run per default**; `--invia`
spedisce. È già automatizzabile (non interattivo, exit != 0 sugli errori,
reinviare non altera dati) e la riga di cron è pronta ma **commentata** in
`docs/operazioni-inquilini.md`: durante il rodaggio l'invio resta manuale.

`ReminderRule` resta **senza engine**: nessun automatismo la consuma.

`ultimo_invio_at` per inquilino = ultima `Notification` con
`codice="riepilogo_addebiti"`, canale email e `inviata_at` non nullo. Senza il
filtro sul codice si pescherebbe l'email di invito (stessa GenericFK su
`TenantProfile`); senza quello su `inviata_at` un invio fallito comparirebbe
come "già inviato".

# Registro comunicazioni

`Notification` ha quattro campi che la rendono un archivio consultabile:
`corpo_html` (l'HTML realmente recapitato), `destinatario` (l'indirizzo
effettivo — può essere `email_alt`, e non è ricostruibile se l'utente cambia
recapito), `codice` (che comunicazione è) ed `errore`.

**Invariante**: `inviata_at` valorizzato = partita; `errore` valorizzato =
fallita, con `inviata_at` nullo. Le due condizioni si escludono.

Perché il `codice` è indispensabile: invito inquilino e riepilogo addebiti
puntano entrambi a un `TenantProfile` via GenericFK, e il ContentType non li
distingue.

Lettura dal sito: `GET /api/v1/comunicazioni/` (paginata, scoping su
`user__tenant_profile__property`, che esclude di suo le notifiche verso
proprietari e gestori). Il corpo sta solo nel dettaglio. Due punti di accesso
in UI, stesso componente: tab "Inviati" di `/p/riepilogo` (tutto l'immobile) e
tab "Inviati" della scheda inquilino.

Gli avvisi utenze scrivono **due righe** per lo stesso evento (email + push):
non si deduplica, la colonna canale le distingue.

# Vedi anche

- [Receivable](receivable.md) — gli addebiti che la mail elenca.
- [Calcolo utenze](calcolo-utenze.md) — l'altro flusso email, con QR e riscrittura scadenze.
- [App notifications](/models/notifications.md) — campi di `Notification`.
- `backend/apps/billing/calc/posizione.py` — la formula unica del residuo.
