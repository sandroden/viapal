---
type: Domain Logic
title: Deposito cauzionale
description: Versamento e restituzione del deposito, con trigger da data prevista.
resource: backend/apps/properties/models/tenant.py
tags: [domain, deposito, billing]
timestamp: 2026-09-03T00:00:00Z
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
- `deposito_versato` è il **pattuito**, non l'incassato: con un versamento
  parziale la restituzione proporrebbe il pattuito. Chiudendo la posizione
  vanno allineati entrambi (Receivable e anagrafica), e lo stato del
  Receivable **non** si riallinea da solo — `_riallinea_receivable` scatta
  sulle allocazioni, non sul salvataggio dell'addebito.

Un deposito trattenuto è di fatto un ricavo, ma la causale DEPOSITO è fuori
da `CAUSALI_OPERATIVE`: per vederlo nel [conto economico](/domain/conto-economico.md)
andrebbe riclassificato su `extra`. Nessun automatismo lo fa.

# Restituzione

La restituzione è un [Receivable](/domain/receivable.md) con causale dedicata e
**segno negativo** (esce denaro verso l'inquilino): allocazione, BT e Receivable
tutti negativi — vedi [segni concordi](/decisions/segni-concordi.md). La
generazione dell'addebito di restituzione è esplicita dal frontend. Esiste una
pagina/endpoint di rendiconto deposito.

# Vedi anche

- [Receivable](/domain/receivable.md), [Segni concordi](/decisions/segni-concordi.md).
