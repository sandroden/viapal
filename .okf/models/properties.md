---
type: Django App
title: App properties
description: Anagrafica immobile, proprietari, quote e assegnazioni stanze.
resource: backend/apps/properties/models/property.py
resources:
  - backend/apps/properties/models/property.py
  - backend/apps/properties/models/tenant.py
  - backend/apps/properties/models/owner.py
  - backend/apps/properties/models/membership.py
  - backend/apps/properties/models/share.py
tags: [models, properties]
generated:
  by: process:okf-migrate
  at: 2026-09-05T00:00:00Z
---

# Overview

Anagrafica: immobile, stanze, contratti, assegnazioni, proprietari e inquilini.
Reference strutturale — la logica sta nei concetti di [dominio](/domain/).
Tutti i modelli ereditano da `TimestampedModel` (`created_at`/`updated_at`,
`models/_base.py`). Moduli: `property.py` (immobile, stanze, galleria,
contratti, assegnazioni, documenti immobile), `tenant.py`, `owner.py`,
`membership.py`, `share.py` (link di lettura), `document_template.py`,
`anagrafica.py` (`AnagraficaPersonaMixin`: cognome/nome, nascita, cittadinanza,
residenza).

# Modelli

| Modello | Campi chiave | Note |
|---------|--------------|------|
| `Property` | `nome`, `indirizzo` (libero) + indirizzo strutturato `via`/`civico`/`cap`/`comune`/`provincia`/`piano`/`scala`/`interno`/`vani`/`accessori`/`ingressi`, `bank_account_utenze` (FK), `owner_anticipa_cessioni` (FK), `owner_firmatario` (FK), `tipo_gestione`; annuncio: `slug`, `pubblica`, `foto_hero`/`foto_planimetria`/`foto_mappa`, `testi_pubblici` (JSON) | conto utenze; `tipo_gestione` = `stanze` (default) / `unita_intera`; `via` contiene già "Via/Piazza"; slug auto in `save()` |
| `PropertyMembership` | `property`, `user`, `ruolo` (`proprietario`/`gestore`/`sola_lettura`), `invitato_da` | accesso di un utente a un immobile: è ciò che rende "lato gestione" un utente (vedi [Auth e ruoli](/architecture/auth-e-ruoli.md)); `sola_lettura` = solo metodi safe |
| `Room` | `property`, `nome`, `superficie_mq`, `foto`, `ordinamento`; annuncio: `colore`, `descrizione`, `disponibile`, `libera_dal`, `prezzo_mensile`, `pubblica` | stanza, o **unità locata** su `unita_intera`; i campi d'annuncio sono indipendenti dalle assegnazioni |
| `GalleryArea` | `property`, `nome`, `colore`, `descrizione`, `ordinamento`, `pubblica` | ambiente comune (cucina, bagno…): raggruppa foto, **non** è oggetto d'affitto |
| `GalleryImage` | `property`, `room` **xor** `area`, `image`, `didascalia`, `formato` (`quadrato`/`orizzontale`/`verticale`), `ordinamento`, `caricato_da` | foto dell'annuncio — vedi [Galleria pubblica](/domain/galleria-pubblica.md) |
| `Contract` | `property`, `nome`, `data_stipula`, `data_decorrenza`, `termine`, `durata_anni`+`durata_rinnovo_anni` (il "4+2"), `asseverato`, `regime_fiscale`, `default_pagatore_bollette`, estremi di registrazione (`ufficio_registrazione`, `data_registrazione`, `numero_registrazione`, `serie_registrazione`, `codice_identificativo`), `note` | contratto d'affitto; `Property.contratto_attivo()` |
| `RoomAssignment` | `room`, `tenant`, `contract` (FK), `valid_from`/`valid_to`, `rinunciata`, `data_rinuncia`, `canone_mensile`, `bank_account_affitto`, `costo_cessione`, `data_atto_cessione`, `subentra_a` (self-FK), `note` | stanza↔inquilino nel tempo; `subentra_a` è un dato di intenzione, non dedotto dalle date; **`rinunciata`** = l'occupazione non è mai iniziata (vedi sotto) |
| `OwnerProfile` | `user` (1:1), `nominativo`, `codice_fiscale`, `telefono`, `note`, + `AnagraficaPersonaMixin` | proprietario; l'anagrafica è del profilo, non della membership |
| `OwnershipShare` | `property`, `owner`, `valid_from`/`valid_to`, `quota` | quota di proprietà temporale; vincolo DB anti-duplicato + lock su `POST /quote` |
| `OwnerBankAccount` | `owner`, `banca`, `iban`, `intestatario`, `attivo`, `ordinamento`, `properties` (M2M) | conto proprietario; l'anagrafica è unica e globale, `properties` dice **dove** è in uso — vedi [Conti bancari per immobile](/domain/conti-per-immobile.md) |
| `TenantProfile` | `user` (1:1), `property` (FK), `nominativo`, `codice_fiscale`, `telefono`, `email_alt`, `giorno_pagamento_affitto`, `frequenza_conguagli`, `ciclo_fatturazione`, `note_pagamento`, `deposito_versato`, `data_versamento_deposito`, `deposito_da_restituire`, `data_restituzione_prevista`, + `AnagraficaPersonaMixin` e `documento_tipo/numero/autorita/data_rilascio` | inquilino; `TenantProfileQuerySet` porta l'unico predicato "attivo ora" (esclude le rinunce) |
| `TenantDocument` | `tenant`, `tipo`, `file`, `descrizione`, `data_scadenza`, `generato`, `caricato_da` | `tipo` ∈ `carta_identita`, `codice_fiscale`, `passaporto`, `permesso_soggiorno`, `contratto_lavoro`, `ricevuta_registrazione` (ricevuta telematica dell'Agenzia, vale per registrazione e subentro), `atto_subentro_locazione`, `cessione_fabbricato` (i due generati), `altro`; nessuno è obbligatorio. `generato=True` = prodotto dall'app: solo questi vengono sostituiti rigenerando |
| `PropertyDocument` | `property`, `contract`, `tipo`, `file`, `descrizione`, `data_scadenza`, `visibile_inquilini`, `copia_di` (self-FK), `esponibile`, `caricato_da` | `tipo`: `contratto`/`side_letter`/`registrazione_contratto` (carte **di un contratto**: `contract` obbligatorio), `regolamento_condominiale`/`regole_convivenza`/`altro` (carte della casa), `fac_simile` (generato senza dati personali). Lettura inquilini dei soli `visibile_inquilini=True` ("Documenti della casa" in /i/documenti), esclusi i rinunciatari. `copia_di`/`esponibile` = copie oscurate per i [link di lettura](/domain/link-lettura.md) |
| `DocumentTemplate` | `property`, `codice` (univoco per immobile), `nome`, `corpo_html`, `note` | modello HTML dei documenti generati; `carica_modelli_documenti --property <id>` |
| `DocumentShare` | `property`, `token`, `destinatario`, `tenant` (FK opz.), `introduzione`(+`_html`), `attivo`, `visite`, `ultima_visita`, `creato_da` | pacchetto a token `/d/<token>` (`share.py`) |
| `ShareItem` | `share`, `ordine`, `titolo`, `documento` (FK `PropertyDocument`, opz.), `corpo_md`(+`_html`) | voce del pacchetto: allegato **o** chiarimento markdown |

# Rinuncia (`RoomAssignment.rinunciata`, 2026-09-03)

- Caso: inquilino che versa la caparra e non entra. L'assegnazione resta
  (`Receivable.assignment` è PROTECT e non nullable: è l'unico aggancio del
  deposito) ma **non produce nulla e non occupa la stanza**.
- L'autorità è il **flag**, non le date: i conteggi giorni sono inclusivi,
  quindi `valid_to = valid_from` da solo varrebbe un giorno di affitto/utenze/
  TARI. `valid_to = valid_from` è solo la scrittura leggibile; `clean()` e il
  serializer allineano la fine, chi fa `.save()` diretto deve farlo da sé.
- Vincolo DB sulle date rilassato **solo sotto flag**: un 5→5 ordinario resta
  vietato (migrazione `…assignment_valid_to_after_valid_from_and_more`).
- Escluse da: generazione affitti, riparto utenze/TARI (prima del conteggio,
  altrimenti diluirebbero la quota degli altri), inquilini attivi, occupazione
  stanze, controllo sovrapposizioni, costo di registrazione, accesso alle carte
  del contratto (`core/media_private.py`).
- `data_rinuncia` è cronaca (quando è stata comunicata).
- FE: dialog "Modifica assegnazione" (ex "Correggi") nel dettaglio inquilino,
  anche sulle assegnazioni chiuse; rigenera gli addebiti solo se cambia un
  campo che li determina. Vedi anche [Deposito](/domain/deposito.md).

# Vedi anche

- [Unità intera](/domain/unita-intera.md) — `tipo_gestione`: su `unita_intera`
  il backend crea **una sola** Room implicita "Appartamento" (signal `post_save`,
  vincolo max-1 in `Room.clean` + API).
- [Fascicolo documenti](/domain/fascicolo-documenti.md) — `TenantDocument` raggruppato per tipo con stati derivati (in scadenza/scaduto/a carico proprietà) e visore interno.
- [Generazione documenti](/domain/generazione-documenti.md) — `DocumentTemplate`, `AnagraficaPersonaMixin`, indirizzo strutturato di `Property` (`via`/`civico`/`cap`/`comune`/`provincia`/`piano`/`scala`/`interno`/`vani`/`accessori`/`ingressi`) e `owner_firmatario`: campi che esistono per i documenti generati, non per la gestione.
- [Deposito](/domain/deposito.md) — `deposito_*` / `data_restituzione_prevista`.
- [Generazione affitti](/domain/generazione-affitti.md) — `canone_mensile`, `RoomAssignment`.
- `costo_cessione`: totale cessione stanza, split 50/50 (Receivable REGISTRAZIONE + Expense proprietari).
