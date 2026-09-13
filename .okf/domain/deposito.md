---
type: Domain Logic
title: Deposito cauzionale
description: Versamento e restituzione del deposito, con trigger da data prevista.
resource: backend/apps/properties/models/tenant.py
resources:
  - backend/apps/properties/models/tenant.py
  - backend/apps/properties/signals.py
  - backend/apps/properties/views.py
  - backend/apps/billing/dashboard_views/deposito.py
  - backend/apps/billing/dashboard_views/rendiconto.py
tags: [domain, deposito, billing]
generated:
  by: process:okf-migrate
  at: 2026-09-13T00:00:00Z
---

# Overview

Il deposito (ex "caparra" — rinominato "deposito" ovunque) è versato
dall'inquilino a garanzia e restituito all'uscita. I campi vivono su
`TenantProfile`.

# Campi e trigger

| Campo | Ruolo |
|-------|-------|
| `deposito_versato` | importo del deposito; con le rate è il **totale pattuito**, valorizzato subito dall'action anche se non ancora incassato |
| `data_versamento_deposito` | data del versamento (o della pattuizione, con le rate) |
| `data_restituzione_prevista` | **trigger**: alla sua valorizzazione si genera il Receivable di restituzione |
| `deposito_da_restituire` | override opzionale (se si restituisce importo diverso dal versato) |

# Versamento a rate (dilazione)

Il versamento può essere **dilazionato**: N Receivable DEPOSITO positivi
("Deposito (versamento) — rata i/N") con scadenze diverse, struttura DB
invariata. Li crea l'action `POST room-assignments/prima-assegnazione/`
(che in un'unica transazione crea assignment, ciclo di fatturazione,
rate e quota condominio specifica). Ordine anti-duplicazione con i
signal di `properties/signals.py`: l'assignment è salvato quando
`deposito_versato` è ancora 0 (signal no-op), le rate sono create a
mano, e `deposito_versato` è valorizzato **per ultimo** — l'idempotenza
del signal ("esiste già un DEPOSITO positivo") vede le rate e non crea
il receivable unico. Un tenant con deposito già registrato non può
riceverne un secondo dall'action (400).

# Visibilità lato inquilino

`CAUSALI_OPERATIVE` (dashboard di gestione) esclude DEPOSITO per scelta:
i depositi non sono entrate operative. La **home inquilino** però
aggiunge esplicitamente i DEPOSITO con `importo_dovuto > 0` al blocco
`da_pagare` (tipo API `"deposit"`): l'inquilino le paga come ogni altro
addebito, QR bonifico incluso (conto utenze della proprietà). Il flusso
"Ho pagato" passa da `/api/v1/deposit-charges/` (read-only +
dichiara/conferma pagato, sole rate positive). Le restituzioni
(negative) non compaiono mai fra i "da pagare". Le rate **pagate**
compaiono in `ultimi_pagamenti` (home inquilino) insieme alle causali
operative.

# Pattuito vs incassato: non si rende ciò che non è entrato

Dal 2026-09-13 (caso Rosalia: 2 rate da 470 appena create, nulla pagato,
e la simulazione mostrava "versato 940" e 576,50 da rendere) **tutto ciò
che riguarda la restituzione ragiona sull'incassato effettivo**, mai sul
pattuito. Un solo punto di verità in `dashboard_views/deposito.py`:

- `versato_effettivo(tenant)` = Σ `importo_pagato` delle righe DEPOSITO
  positive (rate comprese);
- `importo_suggerito(tenant)` (lordo da rendere) = `deposito_da_restituire`
  se > 0, altrimenti `versato_effettivo` — **non più** `deposito_versato`.

Lo usano la vista di restituzione esplicita, la chiusura (componente
virtuale "deposito da rendere", `registrabile` è falso se non c'è nulla
da rendere e la riga manca, 409 sul POST), il rendiconto
(`deposito.da_restituire`) e la situazione, che espone fuori dall'anno
`deposito.pattuito` / `incassato` / `da_rendere`. Le card Deposito dei
due frontend (dettaglio proprietario e `/i/situazione`) leggono quei tre
campi: con incasso parziale l'etichetta diventa "Pattuito … · incassato
finora X" (o "non ancora incassato") e la simulazione mostra "Deposito
incassato, di Y pattuiti". Con l'override valorizzato l'override vince
ancora, anche sopra l'incassato: è una scelta esplicita di chi lo scrive.

Effetto sui dati reali: chi ha la riga di versamento `atteso` senza
allocazioni (caso Mehmet, 1250 del 2025-11) vede "non ancora incassato"
e 0 da rendere finché il bonifico non viene riconciliato — è la verità
del sistema, non un bug, e il rimedio è la riconciliazione.

# Deposito nel rendiconto

Poiché `deposito_versato` è il pattuito, il rendiconto NON lo usa come
"versato": espone `deposito.versato_effettivo` (somma di
`importo_pagato` delle rate positive) e `deposito.movimenti` con
`data_pagamento`. Il FE (ProprietarioRendiconto / InquilinoRendiconto)
mostra in cronologia una riga informativa per **rata pagata** (fallback
alla riga anagrafica unica solo per i rapporti storici senza rate
riconciliate) e in simulazione uscita "Deposito pattuito / di cui
incassato finora". Il ledger "Versamenti e imputazioni" include anche le
allocazioni su DEPOSITO (il bonifico c'è stato davvero); righe, saldi e
resti restano sul solo perimetro non-DEPOSITO.

# Deposito di chi ha rinunciato

Se l'inquilino versa (anche solo in parte) e poi rinuncia prima di entrare,
l'assegnazione **resta**: è ciò che tiene la caparra attaccata a quella
persona, e cancellarla non si può (`Receivable.assignment` è `PROTECT`). Si
marca `rinunciata` — vedi [generazione affitti](/domain/generazione-affitti.md)
— e il deposito continua ad agganciarsi lì.

Due trappole verificate sul caso reale (settembre 2026, 490 € versati su 980
pattuiti):

- `deposito_da_restituire = 0` **non** significa "trattengo": lo zero è
  trattato come "non valorizzato" e fa fallback su `deposito_versato`.
  Trattenere = lasciare `data_restituzione_prevista` vuota, cioè non far
  scattare il trigger;
- `deposito_versato` è il **pattuito**, non l'incassato: fino al 2026-09-13
  con un versamento parziale la restituzione proponeva il pattuito (oggi
  propone l'incassato, vedi sopra). Chiudendo la posizione vanno comunque
  allineati entrambi (Receivable e anagrafica), e lo stato del Receivable
  **non** si riallinea da solo — `_riallinea_receivable` scatta sulle
  allocazioni, non sul salvataggio dell'addebito.

Un deposito trattenuto è di fatto un ricavo, ma la causale DEPOSITO è fuori
da `CAUSALI_OPERATIVE`: per vederlo nel [conto economico](/domain/conto-economico.md)
andrebbe riclassificato su `extra`. Nessun automatismo lo fa.

# Restituzione

La restituzione è un [Receivable](/domain/receivable.md) con causale dedicata e
**segno negativo** (esce denaro verso l'inquilino): allocazione, BT e Receivable
tutti negativi — vedi [segni concordi](/decisions/segni-concordi.md). La
generazione dell'addebito di restituzione è esplicita dal frontend. Esiste una
pagina/endpoint di rendiconto deposito.

# Chiusura: netto da rendere e bonifico unico

`GET tenants/<id>/chiusura/` (`ChiusuraDepositoView`, 2026-09-07) scompone il
netto da restituire nelle sue parti, così che "61,95" o "275,05" abbiano una
spiegazione leggibile: la riga di restituzione (positiva, deposito da rendere;
se l'addebito non è ancora generato, il lordo suggerito come componente
virtuale senza `receivable_id`), ogni addebito aperto con il suo residuo
(`effetto = −residuo`: un affitto o una bolletta da trattenere pesa negativo,
una rettifica o un accredito positivo) e i resti dei bonifici già ricevuti.
`netto = Σ effetti + resti` coincide con `deposito − sbilancio reale` della
simulazione; la restituzione già saldata non compare fra le componenti.
`bonifici` elenca i movimenti che hanno pagato la restituzione con tutte le
loro imputazioni e lo scarto: è la memoria di come si componeva quel che si
è reso, e resta visibile dopo. `registrabile` = c'è un'assegnazione e la
restituzione non è saldata (riga assente compresa, purché l'incassato
da rendere sia > 0: la crea il POST).

`POST tenants/<id>/chiusura/` `{data, importo>0, owner_account, descrizione?,
note?}` genera la riga di restituzione se manca (lordo suggerito, data del
bonifico, stesso helper `crea_o_aggiorna_restituzione` della vista esplicita)
e registra il bonifico fatto all'inquilino come **una sola** BT in uscita
allocata a tutte le componenti (la partita compensata di
[segni concordi](/decisions/segni-concordi.md)): trattenute e rettifiche per
intero, la restituzione prende il resto così che Σ allocazioni = BT, mai oltre
il suo residuo. Bonifico superiore al netto ⇒ l'eccedenza resta sulla BT e nel
saldo compare come debito dell'inquilino (caso Davide: 275,05 contro 267,59 →
−7,46); inferiore ⇒ la restituzione resta parzialmente aperta. 409 senza riga
di restituzione, con restituzione già saldata, o se il bonifico non copre
nemmeno gli accrediti aperti.

Frontend: card Deposito del dettaglio inquilino (tab Profilo & contratto).
Prima della restituzione: riga "Netto da restituire" con badge `atteso`
cliccabile (lo stesso gesto della tabella pagamenti) che apre
`RegistraBonificoChiusuraDialog` (importo proposto = netto, nota sullo scarto,
elenco delle imputazioni) ed espansore "Come si calcola" con le componenti.
Dopo: riga "Restituito <importo> il <data>" con badge `pagato` ed espansore
"Come si compone" con le imputazioni di ogni bonifico e lo scarto. Si
ricarica a ogni cambio della situazione.

# Vedi anche

- [Receivable](/domain/receivable.md), [Segni concordi](/decisions/segni-concordi.md).
