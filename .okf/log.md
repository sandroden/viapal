# Update Log

## 2026-08-26
* **Creation**: `domain/link-lettura.md` — link di lettura a token (`DocumentShare`/`ShareItem`), `PropertyDocument.copia_di` + `esponibile`. Due scostamenti dal piano da ricordare: `copia_di` è `PROTECT` e non `SET_NULL` (con `SET_NULL`, eliminando l'originale, la copia oscurata diventerebbe un documento ufficiale) e l'anteprima markdown passa da un endpoint invece che da un renderer JS. Invariante: l'esponibilità si ricontrolla al momento di servire, non solo quando si compone.
* **Maintain**: `domain/fascicolo-documenti.md` — sezione "L'ambito è nel tipo": contratto/side letter/registrazione richiedono `contract` (`TIPI_CONTRATTUALI` + `valida_ambito()` in `clean()` e nel serializer), nuovo tipo `regole_convivenza`, PATCH JSON per staccare il contratto, dialog «Modifica documento» (prima l'unico modo di correggere era ricaricare, da cui i doppioni casa/contratto), avvisi nel foglio di caricamento, etichetta del chip non più il nome file (la querystring firmata la rendeva illeggibile). Command `sistema_documenti_immobile` con le due diagnosi di coda.
* **Maintain**: `models/properties.md` — `PropertyDocument`: `contract` in tabella e distinzione carte-di-contratto / carte-della-casa.
* **Maintain**: `domain/fascicolo-documenti.md` — `collega_assegnazioni_contratto`: le occupazioni senza contratto rendevano invisibili agli inquilini le carte di contratto (in prod nessuna delle 28 lo aveva). Collega quelle dalla decorrenza in poi, si ferma sui casi a cavallo.

## 2026-08-07
* **Creation**: `domain/conti-per-immobile.md` — `OwnerBankAccount.properties` (M2M): il conto resta unico ma dove è in uso diventa un dato esplicito, al posto del predicato transitivo sulla membership. Nasce dal gestore che si vedeva proporre i propri conti come destinazione dei bonifici di un immobile altrui e i propri movimenti nella sua riconciliazione (in produzione 183 movimenti di un immobile visibili nell'altro). Invariante nuovo: l'isolamento delle BT poggia interamente sul collegamento del conto, perché `BankTransaction` non ha una property propria. Eccezione voluta per le spese (conto di chi anticipa). Backfill `properties.0036` da cinque sorgenti, inclusi i movimenti già riconciliati.
* **Maintain**: `models/properties.md`, `domain/receivable.md` — rimandi al nuovo concetto; i conti eleggibili come destinazione sono quelli in uso sull'immobile.

## 2026-08-06
* **Maintain**: `domain/fascicolo-documenti.md` — sezione "Documenti della casa: chi li vede": `PropertyDocument.contract` lega le carte al contratto e `RoomAssignment.contract` (facoltativo) dice sotto quale contratto sta un'occupazione; un documento di contratto visibile lo vedono solo gli inquilini di quel contratto, senza contratto sull'assegnazione nessuno. Il gate sta in due punti (queryset del viewset e `core/media_private.py`) e vanno tenuti allineati. Le assegnazioni precedenti alla migrazione `0034` hanno il campo vuoto.

## 2026-08-05
* **Maintain**: `domain/generazione-documenti.md`, `domain/generazione-affitti.md` — "Immobile e membri" e "La casa" fuse nell'unica pagina a tab "Immobile" (`/p/impostazioni`, 10 tab, governance in coda); tabella "Dove si compila" con le nuove etichette "Immobile → …"; le vecchie route `/p/impostazioni/proprieta` e `/p/impostazioni/casa` restano come redirect che preservano `campo`/`contratto`.

## 2026-08-04
* **Maintain**: `domain/saldi-fratelli.md` → `domain/saldi-proprietari.md` (+ link in `index.md`, `domain/index.md`, `domain/conto-economico.md`, `domain/conguaglio.md`, `models/accounting.md`) — con la multiproprietà "fratelli" era specifico del solo immobile originale: pagina rinominata "Saldi proprietari", route `/p/saldi-proprietari` con redirect dal vecchio path.

## 2026-08-03
* **Maintain**: `domain/generazione-affitti.md`, `models/billing.md` — la quota condominio (`TenantCondominioRate`) pende dall'immobile (`property` obbligatoria, backfill dal contratto) e non più dal contratto, ora riferimento facoltativo con `SET_NULL`: su una casa appena creata la prima assegnazione con quota falliva con "Nessun contratto attivo". Le quote si gestiscono da `/api/v1/quote-condominio/` (tab Spese della casa).
* **Maintain**: `domain/receivable.md` — sezione "Conto di destinazione": `conto_per_receivable` è la fonte del conto **proposto** quando si registra un incasso (`conto_suggerito`), mai il conto di chi guarda; le spese restano sul conto di chi anticipa.
* **Maintain**: `architecture/auth-e-ruoli.md` — l'invito membro manda il link imposta-password a chiunque non abbia una password utilizzabile, non solo a chi è appena stato creato.
* **Maintain**: `domain/fascicolo-documenti.md`, `domain/generazione-documenti.md` — il fascicolo elenca solo i documenti esistenti: via lo stato `attesa`, `a_carico_proprieta` e `applicabile` (le voci vuote erano una richiesta implicita, non dovuta a nessuno). Generare diventa un'azione invocata dal pannello, alimentata dal nuovo `GET tenant-documents/generabili/`.
* **Maintain**: `domain/generazione-documenti.md` — `riepilogo` dell'anteprima per documento (`Documento.riepilogo`, base vuota): la cessione di fabbricato non mostra più canone, deposito, oneri e comproprietari.
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
