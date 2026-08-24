---
type: Decision
title: Allocazioni non eccedenti
description: La somma delle allocazioni non può superare l'importo del movimento, nemmeno dopo una correzione.
tags: [decision, invariant, riconciliazione, admin]
timestamp: 2026-08-25T00:00:00Z
---

# Invariante

La **somma algebrica** delle `BankTransactionAllocation` di un
`BankTransaction` va nel verso del movimento e non ne supera l'importo in
valore assoluto (tolleranza 0,01 €). Regola volutamente sulla somma, non sulla
singola riga: le partite compensate restano valide — restituzione
[deposito](/domain/deposito.md) con trattenuta utenze, BT −984 ↔ alloc −1060 +
alloc +76.

# Il buco che ha motivato la guardia

L'invariante era verificata **solo alla creazione** (endpoint
`bank-transactions/riconcilia/` e `registra-pagamento/`), non alla modifica
successiva del movimento. Correggere in admin l'importo di una BT **già
riconciliata** lasciava intatte le allocazioni: il
[Receivable](/domain/receivable.md) restava coperto per denaro mai incassato,
senza alcun segnale (un residuo negativo non veniva mostrato e lo stato
risultava "riconciliato pieno").

Caso reale (ago 2026): deposito da 980 €, bonifico da 100 € digitato come
590.100 € → allocazione clampata al residuo (590 €) → deposito "pagato" 980 €.
Corretto l'importo della BT a 100 €, l'allocazione da 590 € è rimasta.

# Come è chiusa

- `BankTransactionAllocationInlineFormSet.clean` (admin) rifiuta il salvataggio
  quando le allocazioni eccedono l'importo — copre sia la modifica dell'importo
  sia la modifica delle allocazioni, che stanno nella stessa pagina.
- `BankTransaction.stato_riconciliazione` ha un quarto stato `"sovra"`
  (`is_sovra_allocato`), visibile come icona in admin e come chip *eccedente*
  in riconciliazione: l'anomalia non è più muta.
- `manage.py sana_allocazioni_eccedenti` (dry-run di default) ripara i dati già
  sbilanciati riducendo le allocazioni dalla più recente e riallineando i
  Receivable.

# Vedi anche

- [Riconciliazione](/domain/riconciliazione.md), [Segni concordi](/decisions/segni-concordi.md).
