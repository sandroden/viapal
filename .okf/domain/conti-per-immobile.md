---
type: Domain Concept
title: Conti bancari per immobile
description: Il conto è unico e globale, ma dove è in uso è un dato esplicito; su questo poggia l'isolamento contabile fra immobili.
resource: backend/apps/properties/models/owner.py
tags: [conti, multiproprieta, banca, isolamento]
timestamp: 2026-08-07T00:00:00Z
---

# Il problema

`OwnerBankAccount` non aveva alcuna relazione con `Property`. Ovunque servisse
sapere quali conti riguardassero un immobile, il codice usava lo stesso
predicato transitivo: `owner__user__property_memberships__property=prop`, cioè
**i conti di chiunque ne fosse membro**, con qualunque ruolo.

Con un solo immobile e tre fratelli la scorciatoia reggeva. Con la
multiproprietà no: un **gestore** amministra la casa di qualcun altro, e non
c'è nessun motivo per cui i bonifici di quella casa debbano poter arrivare sul
suo conto. Peggio: siccome `BankTransaction` **non ha una FK a Property** e il
conto è il suo unico aggancio a un immobile, i movimenti del gestore
comparivano nella riconciliazione dell'immobile gestito. In produzione erano
183 movimenti di un immobile visibili nell'altro, contro gli 11 che gli
appartenevano davvero.

# La regola

Il conto resta **unico**: una anagrafica, un IBAN, uno storico di movimenti
intatto — lo stesso conto può servire su più immobili e duplicarlo spezzerebbe
lo storico. Cambia solo *dove è in uso*, che da deduzione diventa dato:
`OwnerBankAccount.properties` (M2M).

Due assi indipendenti, da non confondere:

| campo | significato |
|---|---|
| `attivo` | conto dismesso: sparisce ovunque |
| `properties` | dove un conto attivo può comparire |

Chi **collega/scollega** un conto: proprietari e gestori di quell'immobile, per
qualsiasi conto dei membri — è un atto di gestione, lo stesso di scegliere il
conto utenze fra quelli altrui. Chi **modifica** i dati del conto (IBAN, banca):
solo il titolare, più il superuser. Sono due permessi distinti di proposito.

Lo stesso gate vale per `collegabili/` benché sia una GET: `IsPropertyMember`
da solo lascerebbe a un `sola_lettura` (il commercialista) l'elenco proprio dei
conti che il pannello tiene fuori.

`bank_account_utenze` non è compilabile alla creazione dell'immobile: nessun
conto può essere in uso su qualcosa che non esiste ancora, e sarebbe l'unico
modo rimasto di puntare a un conto scollegato.

# Invariante

> D'ora in poi l'isolamento dei movimenti bancari fra immobili poggia
> **interamente** sul collegamento del conto.

`BankTransaction` continua a non avere una property propria: un conto
realmente collegato a due immobili mostra tutti i suoi movimenti su entrambi.
Chi tocca i filtri delle BT deve saperlo.

# L'eccezione delle spese

Per una spesa il conto è quello di **chi ha anticipato il denaro**, non quello
su cui l'immobile incassa. Quindi lì si accetta anche un conto del richiedente
non collegato all'immobile: senza questa eccezione un gestore non potrebbe
registrare una spesa pagata di tasca sua — ed è il caso reale, su ViaPessi
tutte le spese sono anticipate dal gestore.

Lato frontend la distinzione è la stessa: in `/p/spese` le opzioni sono i conti
dell'immobile **più** i propri; nei dialog di incasso solo quelli dell'immobile
(proporre i propri significherebbe offrire un conto che il backend rifiuta).

# Migrazione

`properties.0036` collega ogni conto agli immobili dove era *davvero* in uso,
da cinque sorgenti: membership con ruolo `proprietario` (i gestori sono esclusi
— è il punto), conto utenze dell'immobile, conto affitto di un'assegnazione,
conto di destinazione di un addebito e — la sorgente che non si può omettere —
i **movimenti già riconciliati** con addebiti di quell'immobile
(`Receivable.allocations__bank_transaction__owner_account`). Un conto la cui
unica traccia sono gli import storici sparirebbe altrimenti in silenzio dalla
riconciliazione.

# Scollegare invece di eliminare

Un conto con movimenti non si può eliminare (`PROTECT`, ed è giusto). Prima
questo lasciava senza via d'uscita chi vedeva un conto estraneo nella lista;
ora l'azione corretta è **toglierlo dall'immobile**, che non tocca il conto né
il suo storico. Lo scollegamento è rifiutato finché quel conto è il conto
utenze dell'immobile o il conto affitto di un'assegnazione: prima si cambia il
riferimento.

# Vedi anche

- [Receivable](/domain/receivable.md) — conto di destinazione e `conto_suggerito`.
- [Riconciliazione](/domain/riconciliazione.md) — le BT visibili su un immobile.
- [Reference modelli properties](/models/properties.md).
