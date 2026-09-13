---
type: Domain Logic
title: Receivable — l'addebito unificato
description: Il modello unico che rappresenta ogni importo dovuto dall'inquilino.
resource: backend/apps/billing/models/receivables.py
resources:
  - backend/apps/billing/models/receivables.py
  - backend/apps/billing/_notifiche.py
  - backend/apps/billing/signals.py
  - backend/apps/billing/calc/incassi.py
  - backend/apps/billing/_payments.py
  - backend/apps/billing/views/receivables.py
  - backend/apps/billing/views/_common.py
tags: [domain, receivable, billing]
generated:
  by: process:okf-migrate
  at: 2026-09-13T00:00:00Z
---

# Overview

`Receivable` è **un addebito verso l'inquilino**, indipendentemente dalla natura.
Prima esistevano tre modelli separati (`RentPayment`, `UtilityCharge`,
`ExtraCharge`); sono stati unificati in un solo modello distinto dal campo
`causale`. Vedi [decisione di unificazione](/decisions/unificazione-receivable.md).

# Anatomia

- **Cosa è dovuto**: `importo_dovuto`, `causale`, `descrizione` (obbligatoria
  per EXTRA, opzionale altrove), `competenza_da`/`competenza_a` (nulla per
  EXTRA: addebito puntuale), `scadenza`, `assignment` (a chi/quale stanza,
  FK `PROTECT`: un'assegnazione con addebiti non si cancella).
- **Cosa è stato pagato**: `importo_pagato`, `stato`, `data_pagamento`,
  `incassato_da_owner`. Questi sono derivati dalle allocazioni bancarie,
  **non** inseriti a mano.
- **Stati** (`StatoPagamento`): `atteso`, `dichiarato`, `pagato`,
  `in_ritardo`, `insoluto`.
- **Legami**: `utility_period` (se causale utenze), `giorni_presenza` (pro-rata),
  `is_aggiustamento` (voce di rettifica, es. uscita anticipata),
  `bank_account_destinazione` (override del conto su cui va versato),
  `ricevuta` (file su storage privato).
- **Previsionale d'uscita**: `previsionale` (UTENZE senza periodo, stima
  trattenuta dal deposito) e `conguaglio_di` (self-FK: la rettifica punta il
  previsionale che compensa). Vedi [conguaglio](/domain/conguaglio.md).
- **`note`**: log append-only della macchina a stati dichiara/rifiuta; da non
  confondere con i commenti (sotto).

# Vincoli di database

| Nome | Regola |
|------|--------|
| `receivable_affitto_unique` | un solo AFFITTO per `(assignment, competenza_da, competenza_a)` |
| `receivable_utenze_unique` | un solo UTENZE per `(utility_period, assignment)` |
| `receivable_pagato_ha_incassante` | `stato=pagato` ⇒ `incassato_da_owner` valorizzato (`CheckConstraint`; `clean()` ripete la regola per l'admin) |

# Causali

`Receivable.Causale`: `AFFITTO`, `UTENZE`, `EXTRA`, `DEPOSITO`, `REGISTRAZIONE`
(costo cessione, vedi [properties](/models/properties.md)). Ogni sottodominio
genera Receivable con la propria causale:

- [Generazione affitti](/domain/generazione-affitti.md) → AFFITTO.
- [Calcolo utenze](/domain/calcolo-utenze.md) → UTENZE (+ `utility_period`);
  il [previsionale d'uscita](/domain/conguaglio.md) e la sua rettifica sono
  UTENZE **senza** periodo (`previsionale` / `conguaglio_di`).
- [Deposito](/domain/deposito.md) → DEPOSITO, con il segno a distinguere il
  versamento (positivo, eventualmente a rate) dalla restituzione (negativo).
- EXTRA può avere `importo_dovuto` negativo (rimborso/accredito).

Un'assegnazione marcata `rinunciata` (chi non è mai entrato) non produce
AFFITTO né UTENZE; le resta agganciato solo il DEPOSITO.

# Ciclo di vita e incasso

Il legame con gli incassi è **M:N** via `BankTransactionAllocation`: un bonifico
può coprire più addebiti e un addebito può essere coperto da più bonifici.
`importo_pagato`/`stato` riflettono le allocazioni vive. Vedi
[riconciliazione](/domain/riconciliazione.md).

Il riallineamento è `billing/signals.py: _riallinea_receivable`, che scatta
su ogni salvataggio/cancellazione di un'allocazione **e** sul salvataggio di
una `BankTransaction` già esistente (correggere conto o data del movimento
riallinea gli addebiti che copre). Regole:

- somma delle allocazioni con segno; se è zero o di segno opposto al dovuto
  l'addebito è **non coperto** (ATTESO, campi derivati azzerati);
- `|somma| + 1 € ≥ |dovuto|` ⇒ PAGATO (soglia `_SOGLIA`: gli spiccioli non
  tengono aperto un addebito), `data_pagamento` = data dell'ultima BT,
  `incassato_da_owner` = titolare del conto dell'ultima BT allocata;
- altrimenti parziale: resta ATTESO con `importo_pagato` = somma.

Il signal **non** scatta sul salvataggio del Receivable stesso: correggere
`importo_dovuto` a mano non ricalcola lo stato.

# Dichiarazione, conferma, rifiuto

L'inquilino può **dichiarare** di aver pagato (`dichiara_pagato`): lo stato passa
a DICHIARATO ma `importo_pagato` **non viene toccato** — resta la copertura
reale da allocazioni; gli estremi dichiarati finiscono in `note`. Il
proprietario poi **conferma** (`conferma_pagato`, ammesso da DICHIARATO,
ATTESO e IN_RITARDO) oppure **rifiuta** (`rifiuta_pagato` → riallineamento
dalla verità bancaria, l'addebito torna da pagare). Confermare non è una
spunta: richiede il conto su cui è entrato il denaro e delega a
`calc/incassi.py: registra_incasso` (BT + allocazione); è il signal a
portare l'addebito a PAGATO. Una riconciliazione bancaria vince sempre sul
dichiarato.

`registra_incasso` misura il residuo sulle allocazioni (non su
`importo_pagato`, che su un dichiarato riporta l'affermazione
dell'inquilino), rifiuta un importo di segno discorde col residuo e alloca al
massimo il residuo: l'eccedenza resta sulla BT come credito visibile in
riconciliazione. Stesso motore per `receivables/<pk>/registra-pagamento/`.

La dichiarazione **avvisa i proprietari** via push
(`billing/_notifiche.py: notifica_dichiarazione_pagamento`): è l'unico evento
in cui la proprietà deve agire e nient'altro glielo direbbe. Chi riceve lo
decide `Property.notifica_dichiarazioni` (tutti i proprietari, oppure il solo
intestatario del conto risolto da `conto_per_receivable`, con **ripiego su
tutti** se non risolvibile). Escluso chi ha premuto il bottone: `dichiara_pagato`
è aperta anche ai proprietari, che possono dichiarare per conto dell'inquilino.
Il canale è accessorio: non solleva mai e non fa fallire la dichiarazione.

# Conto di destinazione

Su quale conto va versato un addebito lo decide `conto_per_receivable`
(`billing/_payments.py`): override `assignment.bank_account_affitto` per
l'affitto, altrimenti `property.bank_account_utenze`. È la fonte sia del QR
di pagamento sia del conto **proposto** quando un membro registra l'incasso
(campo `conto_suggerito` nell'API): mai il conto di chi sta guardando la
pagina, che su un immobile altrui può essere un gestore senza parte in
causa. Se non è risolvibile (immobile senza conto) non c'è default e si
sceglie a mano. Fa eccezione la registrazione di **spese** (`/p/spese`,
quick add), dove il conto proposto è quello di chi scrive: lì è chi ha
anticipato il denaro.

I conti eleggibili sono solo quelli **in uso su quell'immobile**
(`OwnerBankAccount.properties`, gate `_valida_conto_incasso` in
`billing/views.py`, 403 altrimenti), non più quelli di chiunque ne sia
membro: vedi [Conti bancari per immobile](/domain/conti-per-immobile.md). La
stessa eccezione delle spese vale anche lì — per una spesa si accetta un
conto proprio anche se non in uso sull'immobile.

# Commenti

`ReceivableComment` (FK `commenti`) sono messaggi liberi con autore e data,
distinti da `note`: visibili nel popup di dettaglio della home inquilino e
nell'admin; un commento dell'inquilino viene inoltrato via email ai membri
proprietari/gestori (`billing/commenti.py`, endpoint
`receivables/<pk>/commenti/`).

# Solleciti

Gli addebiti aperti vengono comunicati all'inquilino da due email diverse:
l'avviso utenze (una voce, con QR, sposta la scadenza a +14gg) e il
[riepilogo addebiti](solleciti.md) (N voci, nessun QR, **non** tocca le
scadenze).

# Invarianti

- Un Receivable con allocazioni vive **non viene sovrascritto** dai ricalcoli
  (generazione affitti, conguaglio) — vedi [guardia allocations](/decisions/guardia-allocations.md).
- Allocazioni, BT e Receivable devono essere **concordi in segno** — vedi
  [segni concordi](/decisions/segni-concordi.md).
- La somma delle allocazioni di una BT non ne supera l'importo — vedi
  [allocazioni non eccedenti](/decisions/allocazioni-non-eccedenti.md).
- Un Receivable `pagato` ha sempre `incassato_da_owner` (vincolo di database):
  si chiude registrandone il movimento, mai scrivendo lo stato a mano — vedi
  [incasso sempre attribuito](/decisions/incasso-sempre-attribuito.md).
