# Update Log

## 2026-08-03
* **Maintain**: `domain/fascicolo-documenti.md` — `atto_subentro` (utenze) tolto dai documenti dell'inquilino (migrazione `0033`, file esistenti declassati ad `altro` col nome in descrizione): riguarda l'immobile, non la persona.
* **Maintain**: `domain/fascicolo-documenti.md` — `ricevuta_subentro` fuso in `ricevuta_registrazione` (migrazione `0032`, remap dei dati esistenti): erano lo stesso documento, la ricevuta telematica dell'agenzia. Nuova etichetta "Registrazione contratto subentro".

## 2026-08-02
* **Creation**: `domain/generazione-documenti.md` — atto di subentro nel contratto e comunicazione di cessione di fabbricato generati in PDF (WeasyPrint): i campi dichiarati come tupla producono sia il contesto sia l'elenco dei dati mancanti, ciascuno col posto in cui compilarlo; il testo è un `DocumentTemplate` per immobile (nel repo solo gli esempi), sostituzione con `str.replace` e `url_fetcher` che blocca le risorse esterne; rigenerare tocca solo i PDF con `generato=True`.
* **Maintain**: `domain/fascicolo-documenti.md` — due voci generabili, `VoceFascicolo.applicabile` (l'atto di subentro compare solo se c'è `subentra_a`), `costruisci_fascicolo` riceve l'assegnazione, campo `generabile` nel payload.
* **Maintain**: `models/properties.md` — `AnagraficaPersonaMixin`, indirizzo strutturato e `owner_firmatario` su `Property`, estremi di registrazione e `durata_rinnovo_anni` su `Contract`, `RoomAssignment.subentra_a`, `TenantDocument.generato`, `DocumentTemplate`.
* **Creation**: `domain/solleciti.md` — email di riepilogo addebiti (canone del mese in apertura, pendenti a 15 giorni, dichiarati a parte), niente totali/QR/IBAN, scadenze non riscritte, ex inquilini inclusi; registro comunicazioni su `Notification` (`corpo_html`, `destinatario`, `codice`, `errore`) con invariante `inviata_at` vs `errore`.
* **Maintain**: `models/notifications.md` — nuovi campi di `Notification` e nota che `ReminderRule` resta senza engine.
* **Maintain**: `domain/receivable.md` — rimando ai due flussi di sollecito.

## 2026-08-01
* **Maintain**: `domain/fascicolo-documenti.md` — nessun documento è obbligatorio: eliminato lo stato "mancante" (e con esso card di completezza lato inquilino e "mancanti" nel banner del proprietario); nuovo tipo `ricevuta_registrazione` ("Ricevuta di registrazione (agenzia)").
* **Creation**: `domain/fascicolo-documenti.md` — fascicolo documenti inquilino: stati derivati nel backend (soglia 60 giorni), facoltativi non mostrati come mancanti, atto di subentro a carico proprietà, pagine fronte/retro senza modifiche di schema, visore interno (inline + SAMEORIGIN + denylist SW). Sollecito e quadro della casa non implementati.
* **Maintain**: `models/properties.md` — rimando al fascicolo da `TenantDocument`.

## 2026-07-30
* **Maintain**: `architecture/overview.md` — media pubblici vs privati: nuovo storage `MEDIA_PRIVATE_ROOT` + vista autenticata `/media-private/` (documenti, bollette, ricevute, spese); `/media/` resta statico solo per i contenuti pubblici. Riferimento al piano GDPR in `docs/privacy/`.

## 2026-07-29
* **Maintain**: `domain/galleria-pubblica.md` — wordmark cliccabile per l'utente loggato: ritorno a `/p/` sull'immobile della galleria (o `/i/` per l'inquilino).
* **Maintain**: `domain/galleria-pubblica.md` — ridimensionamento client-side in `ImageSlot` (`utils/image.ts`, WebP ≤1920px, fallback su file non decodificabili) e dialog "Scarica foto" (selezione miniature; una foto = file singolo, più foto = ZIP store-only generato da `utils/zip.ts`).

## 2026-07-24
* **Creation**: `domain/unita-intera.md` — proprietà a unità intera (`Property.tipo_gestione` `stanze`/`unita_intera`, Room implicita "Appartamento", vincolo max-1, invariante un-solo-pagatore, degradazione utenze al 100%).
* **Maintain**: `models/properties.md` (campo `tipo_gestione` su Property, Room = unità locata, vincolo Room implicita), `architecture/modello-dati.md` (Room come unità locata), indici `domain/` e root aggiornati.

## 2026-07-08
* **Initialization**: creato il bundle OKF `.okf/` con struttura `architecture/`, `domain/`, `models/`, `decisions/`, `playbooks/`.
* **Creation**: concetti di dominio (Receivable, riconciliazione, generazione affitti, calcolo utenze, conguaglio, deposito, saldi fratelli, conto economico).
* **Creation**: decisioni architetturali (unificazione Receivable, "banca vince sempre", guardia allocations, segni concordi).
* **Creation**: reference strutturale dei modelli Django per le 5 app.
* **Creation**: playbook dev-setup, validazione, import storico.
