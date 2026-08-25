---
type: Decision
title: Incasso sempre attribuito
description: Un addebito pagato deve dire chi ha incassato; l'unica strada per chiuderlo è registrare il movimento bancario.
tags: [decision, invariant, riconciliazione, saldi, api]
timestamp: 2026-08-25T00:00:00Z
---

# Invariante

Un [Receivable](/domain/receivable.md) in stato `pagato` ha sempre
`incassato_da_owner` valorizzato. Vincolo di database
(`receivable_pagato_ha_incassante`), non solo validazione applicativa: la
regola vale per ogni strada di scrittura — API, admin, management command,
script una tantum.

Corollario di percorso: `incassato_da_owner` **non si scrive a mano**. Lo
valorizza il signal di riallineamento a partire dal conto della
`BankTransaction` allocata, quindi chiudere un addebito significa registrarne
il movimento (`billing/calc/incassi.py: registra_incasso`).

# Il buco che ha motivato il vincolo

L'action `conferma_pagato` portava l'addebito a `pagato` scrivendo solo
`stato` / `importo_pagato` / `data_pagamento`. Nessuna
`BankTransactionAllocation`, nessun incassante. Nella pagina Ritardi il
bottone che la chiamava non era vincolato allo stato «dichiarato»: era di
fatto un «segna pagato» senza attribuzione, disponibile su ogni riga.

Conseguenza: [i saldi tra proprietari](/domain/saldi-proprietari.md) ignorano i
Receivable senza incassante (`saldi_live._incassi_per_owner`), quindi
l'incasso spariva dal riparto e la quadratura elencava «incassi esclusi dal
calcolo». Il buco si vede solo dai saldi o dall'admin: la pagina
dell'inquilino mostra l'addebito come regolarmente pagato.

Caso reale (lug 2026): affitto 540 € e utenze 55,15 € di un inquilino
confermati dalla pagina Ritardi; scoperti a fine agosto dal banner di
quadratura, con la data del pagamento sbagliata e nessuna memoria di chi
avesse ricevuto il denaro.

# Come è chiuso

* `conferma_pagato` richiede `owner_account` (400 se manca, 403 se il conto
  non è [in uso su quell'immobile](/domain/conti-per-immobile.md)) e delega a
  `registra_incasso`: BT + allocazione, come `registra-pagamento/`.
* Nella pagina Ritardi il bottone apre `RegistraPagamentoDialog` — conto, data
  e importo, con il conto dell'immobile proposto di default.
* `Receivable.clean()` ripete la regola per dare all'admin un errore di campo
  invece di un 500.
* `sana_incassi_senza_incassante` ricostruisce i casi storici: lista chiusa,
  idempotente, da eseguire **prima** della migration del vincolo.
* Correggere in admin il **movimento** (conto o data) riallinea gli addebiti
  che copre: il signal è su `BankTransaction` oltre che sulle allocazioni,
  altrimenti spostare un bonifico sul conto giusto lascerebbe scritto
  l'incassante sbagliato senza dirlo a nessuno.

# Incassi non monetari

Un addebito saldato con un bene (materasso lasciato in dotazione a fronte di
una quota di [deposito](/domain/deposito.md)) non ha un vero incassante. La
scelta è **non** introdurre un'eccezione al vincolo: si registrano un incasso
sintetico sul conto di chi tiene la contabilità e una spesa di pari importo
anticipata dallo stesso proprietario. Le due partite si compensano
esattamente nei saldi (netto zero per tutti) e resta la traccia del bene
acquisito. Il costo è un movimento che nell'estratto conto reale non esiste,
riconoscibile dalla nota — stesso compromesso già accettato per le BT
sintetiche dell'import storico.
