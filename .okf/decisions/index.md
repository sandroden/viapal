# Decisioni e invarianti

Due nature diverse: la **decisione architetturale** (ADR, `status: active | superseded`, si legge per capire il perché) e le **invarianti** (`type: Invariant`, `resource:` sul punto in cui il vincolo è imposto: chi tocca quel file trova il concetto davanti, via gate pre-commit).

## Decisioni

* [Unificazione in Receivable](unificazione-receivable.md) - i 3 addebiti fusi in un modello con causale.

## Invarianti

* [Banca vince sempre](banca-vince-sempre.md) - in import il dato bancario prevale; idempotenza.
* [Guardia allocations](guardia-allocations.md) - un Receivable con allocazioni vive non si sovrascrive.
* [Segni concordi](segni-concordi.md) - allocazione, BT e Receivable concordi in segno.
* [Allocazioni non eccedenti](allocazioni-non-eccedenti.md) - la somma allocata non supera l'importo del movimento, nemmeno dopo una correzione.
* [Incasso sempre attribuito](incasso-sempre-attribuito.md) - un addebito pagato dice sempre chi ha incassato; si chiude solo registrando il movimento.
