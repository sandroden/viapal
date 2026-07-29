---
type: Domain Logic
title: Receivable — l'addebito unificato
description: Il modello unico che rappresenta ogni importo dovuto dall'inquilino.
resource: backend/apps/billing/models/receivables.py
tags: [domain, receivable, billing]
timestamp: 2026-07-29T00:00:00Z
---

# Overview

`Receivable` è **un addebito verso l'inquilino**, indipendentemente dalla natura.
Prima esistevano tre modelli separati (`RentPayment`, `UtilityCharge`,
`ExtraCharge`); sono stati unificati in un solo modello distinto dal campo
`causale`. Vedi [decisione di unificazione](/decisions/unificazione-receivable.md).

# Anatomia

- **Cosa è dovuto**: `importo_dovuto`, `causale`, `competenza_da`/`competenza_a`,
  `scadenza`, `assignment` (a chi/quale stanza).
- **Cosa è stato pagato**: `importo_pagato`, `stato`, `data_pagamento`. Questi
  sono derivati dalle allocazioni bancarie, **non** inseriti a mano.
- **Legami**: `utility_period` (se causale utenze), `giorni_presenza` (pro-rata),
  `is_aggiustamento` (voce di rettifica, es. uscita anticipata).

# Causali

Il campo `causale` distingue AFFITTO, UTENZE, EXTRA e voci speciali (es.
REGISTRAZIONE per il [costo cessione](/models/properties.md), restituzione deposito).
Ogni sottodominio genera Receivable con la propria causale:

- [Generazione affitti](/domain/generazione-affitti.md) → causale AFFITTO.
- [Calcolo utenze](/domain/calcolo-utenze.md) → causale UTENZE (+ `utility_period`).
- [Deposito](/domain/deposito.md) → causale restituzione deposito.

# Ciclo di vita e incasso

Il legame con gli incassi è **M:N** via `BankTransactionAllocation`: un bonifico
può coprire più addebiti e un addebito può essere coperto da più bonifici.
`importo_pagato`/`stato` riflettono le allocazioni vive. Vedi
[riconciliazione](/domain/riconciliazione.md).

# Dichiarazione, conferma, rifiuto

L'inquilino può **dichiarare** di aver pagato (`dichiara_pagato`): lo stato passa
a DICHIARATO ma `importo_pagato` **non viene toccato** — resta la copertura
reale da allocazioni; gli estremi dichiarati finiscono in `note` (log
append-only della macchina a stati). Il proprietario poi **conferma**
(`conferma_pagato` → PAGATO a dovuto pieno) oppure **rifiuta**
(`rifiuta_pagato` → riallineamento dalla verità bancaria, l'addebito torna
da pagare). Una riconciliazione bancaria vince sempre sul dichiarato: il
signal su `BankTransactionAllocation` ricalcola stato/importi a ogni tocco.

# Commenti

`ReceivableComment` (FK `commenti`) sono messaggi liberi con autore e data,
distinti da `note`: visibili nel popup di dettaglio della home inquilino e
nell'admin; un commento dell'inquilino viene inoltrato via email ai membri
proprietari/gestori (`billing/commenti.py`, endpoint
`receivables/<pk>/commenti/`).

# Invarianti

- Un Receivable con allocazioni vive **non viene sovrascritto** dai ricalcoli
  (generazione affitti, conguaglio) — vedi [guardia allocations](/decisions/guardia-allocations.md).
- Allocazioni, BT e Receivable devono essere **concordi in segno** — vedi
  [segni concordi](/decisions/segni-concordi.md).
