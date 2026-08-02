---
type: Django App
title: App properties
description: Anagrafica immobile, proprietari, quote e assegnazioni stanze.
resource: backend/apps/properties/models/
tags: [models, properties]
timestamp: 2026-07-24T00:00:00Z
---

# Overview

Anagrafica: immobile, stanze, contratti, assegnazioni, proprietari e inquilini.
Reference strutturale — la logica sta nei concetti di [dominio](/domain/).
Tutti i modelli ereditano da `TimestampedModel` (`created_at`/`updated_at`).

# Modelli

| Modello | Campi chiave | Note |
|---------|--------------|------|
| `Property` | `nome`, `indirizzo`, `bank_account_utenze` (FK), `tipo_gestione` | conto utenze; `tipo_gestione` = `stanze` (default) / `unita_intera` |
| `Room` | `property`, `nome`, `superficie_mq`, `foto` | stanza, o **unità locata** su `unita_intera` |
| `Contract` | `data_decorrenza`, `termine`, `durata_anni`+`durata_rinnovo_anni` (il "4+2"), `regime_fiscale`, `default_pagatore_bollette`, estremi di registrazione (`ufficio_registrazione`, `data_registrazione`, `numero_registrazione`, `serie_registrazione`, `codice_identificativo`) | contratto d'affitto |
| `RoomAssignment` | `room`, `tenant`, `valid_from`/`valid_to`, `canone_mensile`, `bank_account_affitto`, `costo_cessione`, `data_atto_cessione`, `subentra_a` (self-FK) | stanza↔inquilino nel tempo; `subentra_a` è un dato di intenzione, non dedotto dalle date |
| `OwnerProfile` | `user` (1:1), `nominativo`, `codice_fiscale`, + `AnagraficaPersonaMixin` | proprietario |
| `OwnershipShare` | `owner`, `valid_from`/`valid_to`, `quota` | quota di proprietà temporale |
| `OwnerBankAccount` | `owner`, `banca`, `iban`, `intestatario`, `attivo` | conto proprietario |
| `TenantProfile` | `user` (1:1), `giorno_pagamento_affitto`, `frequenza_conguagli`, `ciclo_fatturazione`, `deposito_versato`, `deposito_da_restituire`, `data_restituzione_prevista`, + `AnagraficaPersonaMixin` e `documento_tipo/numero/autorita/data_rilascio` | inquilino |
| `TenantDocument` | `tenant`, `tipo`, `file`, `data_scadenza`, `generato` | CI/CF/passaporto/permesso/contratto lavoro/ricevuta registrazione (agenzia)/ricevuta e atto di subentro utenze, atto di subentro nel contratto, cessione di fabbricato; nessuno è obbligatorio. `generato=True` = prodotto dall'app: solo questi vengono sostituiti rigenerando |
| `PropertyDocument` | `property`, `tipo`, `file`, `data_scadenza`, `visibile_inquilini` | contratto/side letter/registrazione/regolamento; CRUD lato gestione, lettura inquilini dei soli documenti con `visibile_inquilini=True` ("Documenti della casa" in /i/documenti) |

# Vedi anche

- [Unità intera](/domain/unita-intera.md) — `tipo_gestione`: su `unita_intera`
  il backend crea **una sola** Room implicita "Appartamento" (signal `post_save`,
  vincolo max-1 in `Room.clean` + API).
- [Fascicolo documenti](/domain/fascicolo-documenti.md) — `TenantDocument` raggruppato per tipo con stati derivati (in scadenza/scaduto/a carico proprietà) e visore interno.
- [Generazione documenti](/domain/generazione-documenti.md) — `DocumentTemplate`, `AnagraficaPersonaMixin`, indirizzo strutturato di `Property` (`via`/`civico`/`cap`/`comune`/`provincia`/`piano`/`scala`/`interno`/`vani`/`accessori`/`ingressi`) e `owner_firmatario`: campi che esistono per i documenti generati, non per la gestione.
- [Deposito](/domain/deposito.md) — `deposito_*` / `data_restituzione_prevista`.
- [Generazione affitti](/domain/generazione-affitti.md) — `canone_mensile`, `RoomAssignment`.
- `costo_cessione`: totale cessione stanza, split 50/50 (Receivable REGISTRAZIONE + Expense proprietari).
