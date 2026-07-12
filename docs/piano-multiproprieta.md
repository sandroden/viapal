# Piano: da Viapal single-property a piattaforma multi-proprietà / multi-utente

> Obiettivo: trasformare Viapal — nato per una casa di 5 stanze gestita da 3 fratelli —
> in un'applicazione dove **molti utenti proprietari** gestiscono **una o più abitazioni**
> (eventualmente a stanze), dove **la stessa proprietà può essere gestita da più persone**
> (comproprietari come Sandro/Bruna/Fabio, oppure un gestore non proprietario come Sandro
> sull'appartamento della moglie), e dove **tutte le gestioni oggi fatte solo nell'admin
> Django vengono portate nel frontend**.
>
> Documento di piano, non di implementazione. Aggiorna e integra `PLAN.md`.

## 0. Fotografia dello stato attuale (perché serve questo piano)

L'analisi del codice (2026-07-11) mostra che il multi-immobile è solo abbozzato:

| Aspetto | Stato attuale |
|---|---|
| Modello `Property` | Esiste (`properties/models/property.py:12`) ma è "vestigiale": solo `nome`, `indirizzo`, `bank_account_utenze`. **Nessun legame con i proprietari.** |
| Aggancio a `Property` | Solo `Room.property` (nullable) e `UtilityBill.immobile` (nullable). Tutto il resto è globale. |
| `Contract` | Dichiarato "contratto unico" nel docstring, **nessuna FK a Property**, letto come singleton (`dashboard_views.py:1223`). |
| `OwnershipShare` | Quote **globali** con vincolo somma = 1.0 sull'intero sistema (`owner.py:118-154`); `quote_attive_at()` è globale. |
| `Expense`, `UtilityChargePeriod`, `AnnualUtilityCost` | Nessun legame con l'immobile. |
| Contabilità (`OwnerLedgerEntry`, `OwnerSettlement`, partitario bilaterale) | Globale, un unico pool di proprietari a somma zero. |
| Permessi | Solo gruppi Django `proprietari`/`inquilini` (`accounts/permissions.py`). Chiunque sia nel gruppo `proprietari` vede e modifica **tutto**. Nessun concetto di "proprietario di *questa* proprietà". |
| Hardcode | `_owner_anticipante()` cerca l'owner con `nominativo__icontains="sandro"` (`properties/signals.py:110-118`); `Property.objects.first()` come fallback (`billing/views.py:479`, `carica_bollette_scanner.py:87`). |
| Frontend | Nessuna nozione di proprietà: nessuno store, nessun selettore, nessuna chiamata API con `property_id`. Store Pinia tutti globali. |
| Frontend vs admin | Il FE è quasi solo operativo (pagamenti, conguagli, spese, riconciliazione). **Tutte le anagrafiche** (immobili, stanze, contratti, cessioni, inquilini, proprietari/quote, conti bancari, categorie, fornitori, regole solleciti, utenti/inviti) vivono solo nell'admin Django. |
| Predisposizione | `accounts/impersonation.py:50-56` documenta già il filtro futuro `Property.objects.filter(owners__user=...)` — la direzione era prevista. |

Nota positiva: l'unificazione degli addebiti in `Receivable` (agganciato a `RoomAssignment`)
significa che **tutta la catena pagamenti eredita l'immobile via `assignment → room →
property`**: non serve toccare i modelli di pagamento, basta rendere `Room.property`
obbligatoria e filtrare via join.

---

## 1. Concetti chiave del nuovo modello

La modifica più importante è **separare due concetti che oggi coincidono**:

1. **Titolarità economica** (chi possiede, con che quota, chi partecipa ai riparti
   pro-quota e ai conti fra comproprietari) → resta `OwnershipShare`, ma **per-proprietà**.
2. **Diritto di accesso/gestione** (chi può vedere e operare su una proprietà) → nuovo
   modello **`PropertyMembership`**.

Questo risolve esattamente i casi richiesti:

| Caso reale | Modellazione |
|---|---|
| Via Palestrina: Sandro, Bruna, Fabio comproprietari | 3 membership `proprietario` + 3 `OwnershipShare` (⅓ ciascuno) su quella property |
| Appartamento della moglie: lei unica proprietaria | 1 membership `proprietario` + 1 `OwnershipShare` (1.0) |
| Sandro gestisce l'appartamento della moglie senza esserne proprietario | membership `gestore` per Sandro su quella property: **operatività piena, nessuna quota**, non compare nei riparti né nei saldi fra proprietari |
| La moglie non vede Via Palestrina | semplicemente non ha membership su quella property |
| Futuro commercialista | membership `sola_lettura` (predisposta da subito nelle choices, UI dopo) |

### Ruoli di membership

```python
class PropertyMembership(TimestampedModel):
    class Ruolo(models.TextChoices):
        PROPRIETARIO = "proprietario"   # gestione piena + partecipa all'economia
        GESTORE      = "gestore"        # gestione piena, NESSUNA quota/ledger
        SOLA_LETTURA = "sola_lettura"   # futuro (commercialista)

    property   = FK(Property, related_name="memberships")
    user       = FK(AUTH_USER_MODEL, related_name="property_memberships")
    ruolo      = CharField(choices=Ruolo.choices)
    invitato_da = FK(AUTH_USER_MODEL, null=True)   # audit
    class Meta:
        unique_together = [("property", "user")]
```

Regole:
- `OwnershipShare` valida che l'owner abbia una membership `proprietario` sulla stessa property.
- Le quote sommano a 1.0 **per property** (non più globalmente).
- Un `gestore` può fare tutto ciò che fa un proprietario **tranne**: modificare
  membership/quote, eliminare la property. (Prima versione: differenza minima; si
  raffina dopo con l'uso reale.)
- I gruppi Django `proprietari`/`inquilini` **restano** ma degradano a "selettore di area
  UI" (`/p/` vs `/i/`): l'autorizzazione vera diventa membership-based. Un utente con
  almeno una membership è "lato proprietari".

### OwnerProfile: da "fratello" a "profilo economico per-property"

`OwnerProfile` oggi è OneToOne con User e globale. Resta OneToOne (anagrafica della
persona: CF, telefono, IBAN), ma **la partecipazione economica passa dalle coppie
(membership, share) per-property**. Non serve spaccare OwnerProfile: serve solo smettere
di usare "tutti gli OwnerProfile" come "i proprietari" — i proprietari di una property
sono `property.memberships.filter(ruolo=PROPRIETARIO)`.

### TenantProfile: agganciato alla property

Un inquilino appartiene di fatto alla property tramite gli assignment, ma un profilo
appena creato (senza assignment) resterebbe orfano/invisibile. Si aggiunge
`TenantProfile.property` (FK obbligatoria dopo backfill):
- definisce chi lo vede (i membri di quella property);
- semplifica tutti i filtri (`tenants` per property senza passare dagli assignment);
- vincolo di coerenza: gli assignment del tenant devono stare su stanze della stessa property.

Limite accettato e documentato: la stessa persona che affittasse presso **due landlord
diversi** avrebbe bisogno di due utenti (il OneToOne user↔TenantProfile resta). Caso
irrealistico per l'uso previsto; se mai servirà, si trasformerà il OneToOne in FK.

---

## 2. Modifiche alla base dati (modello per modello)

### 2.1 Nuovi modelli

| Modello | Scopo |
|---|---|
| `PropertyMembership` | Accesso per-utente-per-property con ruolo (vedi §1) |
| `PropertyInvite` | Invito via email a diventare membro (co-proprietario/gestore) o inquilino: token, email, ruolo proposto, property, scadenza, stato. Generalizza `accounts/inviti.py` |

### 2.2 Campi nuovi / FK da aggiungere

| Modello | Modifica | Note |
|---|---|---|
| `Property` | + `owner_anticipa_cessioni` FK OwnerProfile (nullable), + eventuali settings per-property (giorno pagamento default, ecc.) | sostituisce l'hardcode "sandro" di `signals.py:110` |
| `Room.property` | da nullable a **NOT NULL** | backfill già quasi fatto (migrazione 0011) |
| `Contract` | + `property` FK **NOT NULL** | cade il singleton; una property può avere N contratti nel tempo, più contratti attivi se serve |
| `OwnershipShare` | + `property` FK **NOT NULL**; vincolo somma=1.0 e no-duplicati **per property**; `quote_attive_at(property, data)` | tocca `owner.py:16-38` e tutti i chiamanti (settlement, saldi_live, signals, dashboard) |
| `TenantProfile` | + `property` FK **NOT NULL** | vedi §1 |
| `Expense` | + `property` FK **NOT NULL** | le spese sono dell'immobile |
| `UtilityChargePeriod` | + `property` FK **NOT NULL** | periodi conguaglio per immobile |
| `AnnualUtilityCost` | + `property` FK **NOT NULL** | TARI per immobile |
| `UtilityBill.immobile` | da nullable a **NOT NULL**; rimuovere fallback `.first()` | `billing/views.py:468-480` |
| `Supplier` | + `property` FK **NOT NULL** | privacy fra famiglie diverse: i fornitori di una non devono comparire all'altra |
| `ExpenseCategory` | + `property` FK **NOT NULL**; seed automatico delle categorie standard alla creazione della property | in alternativa: categorie globali condivise — scartato per isolamento |
| `MessageTemplate`, `ReminderRule` | + `property` FK **NOT NULL**; seed dei default alla creazione della property | ogni landlord configura i propri solleciti |
| `OwnerLedgerEntry` | + `property` FK **NOT NULL** | il partitario ufficiale è per-immobile (riparto pro-quota di quell'immobile) |
| `OwnerSettlement` | + `property` FK **NOT NULL** | chiusure per-immobile |
| `TenantCondominioRate` | nessuna (eredita via `contract.property`) | |
| `Receivable`, `BankTransactionAllocation` | nessuna FK: property derivata via `assignment__room__property` | volumi piccoli, il join non è un problema; niente denormalizzazione da tenere sincronizzata |
| `BankTransaction`, `OwnerBankAccount` | **nessuna FK a property**: restano per-owner | un conto riceve per più proprietà; visibilità: vedi §3.3 |
| `InterOwnerLoan/Entry`, `WithholdingRule` | + `property` FK **NOT NULL** *(deciso 2026-07-11)* | il partitario bilaterale è legato alla proprietà: visibile ai membri di quella property, come oggi fra fratelli |
| `Notification`, `PushSubscription` | nessuna FK (sono per-user) | eventualmente `Notification.property` nullable per il deep-link, non necessario ora |

### 2.3 Migrazione dati (una sola release, reversibile)

Ordine delle migrations (tutte con backfill in `RunPython`):

1. Creare `PropertyMembership`; backfill: per la property esistente ("Viapal", creata
   dalla migrazione 0011) una membership `proprietario` per ogni user con `owner_profile`
   nel gruppo `proprietari` (sandro, bruna, fabio).
2. Aggiungere le FK `property` **nullable** a tutti i modelli in tabella; backfill con
   l'unica property esistente (`Property.objects.order_by("pk").first()` — legittimo *solo*
   dentro la data-migration).
3. Alterare le FK a **NOT NULL** (+ nuovi vincoli: unique/somma quote per property).
4. Comando di verifica `check_multiproprieta` che asserisce l'integrità post-migrazione
   (nessun record orfano, quote a 1.0 per property, assignment coerenti con la property
   del tenant).

Test della migrazione su un dump di produzione **prima** del deploy (i dati veri sono
l'unico caso di test che conta).

### 2.4 Hardcode da eliminare

| Dove | Cosa | Sostituzione |
|---|---|---|
| `properties/signals.py:110-118` | `nominativo__icontains="sandro"` | `property.owner_anticipa_cessioni` (o `contract.default_pagatore_bollette`) |
| `billing/views.py:468-480` | `Property.objects.first()` fallback | property obbligatoria dal contesto richiesta (§3.2) |
| `billing/management/commands/carica_bollette_scanner.py:87` | `Property.objects.first()` | opzione `--property` obbligatoria |
| `billing/dashboard_views.py:1223-1228` | contratto singleton | contratto attivo **della property del tenant** |
| `seed_demo.py` / `seed_reali.py` | quote globali, gruppi | aggiornare per creare membership + 2ª property demo (utile per testare l'isolamento) |

---

## 3. Permessi e sicurezza

### 3.1 Principio

Ogni richiesta "lato proprietari" opera **nel contesto di una property attiva**, dichiarata
dal client e verificata dal server. Ogni queryset è filtrato due volte:
1. per la property attiva (scoping funzionale),
2. per le membership dell'utente (autorizzazione) — mai fidarsi del solo parametro.

### 3.2 Meccanica: header `X-Property-Id` + mixin DRF

Il client invia la property attiva in un header (`X-Property-Id`), aggiunto una volta sola
da un interceptor axios — così **gli store Pinia esistenti non cambiano firma**. Lato
server:

```python
class PropertyScopedMixin:
    """Risolve request.property e garantisce la membership."""
    def get_property(self):
        pid = self.request.headers.get("X-Property-Id")
        return get_object_or_404(
            Property.objects.filter(memberships__user=self.request.user), pk=pid
        )
```

Nuove permission class in `accounts/permissions.py`:

| Classe | Sostituisce | Semantica |
|---|---|---|
| `IsPropertyMember` | `IsProprietario` | membership qualsiasi (proprietario/gestore) sulla property attiva |
| `IsPropertyProprietario` | — | solo ruolo `proprietario` (gestione membri, quote, cancellazioni) |
| `IsInquilinoSelf` | (resta) | esteso: il ramo "proprietari vedono tutto" diventa "membri della property dell'oggetto vedono tutto" |

Filtri queryset per app (il pattern, non l'elenco esaustivo):
- `properties`: `Room/Contract/OwnershipShare/TenantProfile` → `filter(property=request.property)`; `OwnerProfile` esposti = utenti membri della property attiva.
- `billing`: `Receivable` → `filter(assignment__room__property=...)`; `Expense/UtilityChargePeriod/UtilityBill/AnnualUtilityCost/Supplier/ExpenseCategory` → FK diretta.
- `accounting`: `OwnerLedgerEntry/OwnerSettlement` → FK diretta; `saldi_live`/`settlement` ricevono la property come argomento.
- `notifications`: già per-user; `ReminderRule/MessageTemplate` → FK diretta.
- Lato inquilino (`/i/*`): nessun cambiamento di contratto API — il tenant continua a vedere i propri dati; la property si deduce dal suo profilo.

### 3.3 Casi non ovvi (decisioni proposte)

| Tema | Decisione proposta |
|---|---|
| **BankTransaction** (conto di Sandro usato per due proprietà) | visibile a chi condivide almeno una property col titolare del conto. La riconciliazione alloca su `Receivable` che sono property-scoped, quindi il *risultato* resta coerente per property. Caveat: Bruna vede anche i movimenti del conto di Sandro relativi all'altra casa — accettabile in famiglia, da raffinare con un flag `visibile_solo_al_titolare` se servirà. |
| **Partitario bilaterale** (`InterOwner*`) | *(deciso 2026-07-11)* legato alla proprietà: FK `property`, visibile ai membri di quella property come oggi. Le entry generate da `Expense.riferimento_quota_owner` ereditano la property della Expense. |
| **Impersonation** | attivare il filtro già predisposto in `impersonation.py:50-56`: un membro può impersonare solo inquilini delle proprie property. |
| **Superuser/admin Django** | resta strumento di manutenzione di Sandro (vede tutto). Aggiungere `list_filter` per property ovunque. Nessuna funzione utente deve più richiedere l'admin. |
| **Gruppi Django** | mantenuti per il routing d'area (`homePath` FE). L'aggiunta al gruppo `proprietari` avviene automaticamente alla creazione della prima membership (signal). |
| **Test di sicurezza** | suite pytest dedicata "cross-property": per ogni endpoint, l'utente A (property 1) non deve né leggere né scrivere dati della property 2 — è la rete di protezione dell'intero refactoring. |

---

## 4. Backend: API nuove e modificate

### 4.1 Nuovi endpoint

| Endpoint | Scopo |
|---|---|
| `GET/POST /api/v1/properties/` + `PATCH/DELETE /:id/` | CRUD immobili dell'utente (delete solo `proprietario`, solo se vuota) |
| `GET/POST/DELETE /api/v1/properties/:id/memberships/` | gestione membri e ruoli |
| `GET/POST /api/v1/properties/:id/shares/` | quote di proprietà versionate (UI dedicata, transazione atomica per il cambio quote) |
| `POST /api/v1/properties/:id/inviti/` + `POST /api/v1/inviti/accetta/` | invito co-proprietario/gestore via email (token, riusa il flusso `imposta-password`) |
| `GET /api/auth/user/` (esteso) | include `properties: [{id, nome, ruolo}]` e `default_property_id` |

### 4.2 Endpoint per portare l'admin nel frontend (oggi mancanti)

CRUD DRF completi (oggi read-only o assenti), tutti property-scoped:

- `rooms/` (oggi RO) → CRUD
- `contracts/` (oggi lista) → CRUD
- `room-assignments/` → CRUD + **action `cessione/`** (wizard: chiude assignment, apre il nuovo, gestisce depositi e `costo_cessione` — logica già nei signal, va solo esposta)
- `tenants/` → create/update + action `invita/` (riusa `inviti.py`)
- `bank-accounts/` → CRUD
- `expense-categories/`, `suppliers/` → CRUD
- `reminder-rules/`, `message-templates/` → CRUD
- `annual-utility-costs/` (TARI) → CRUD
- le due viste admin standalone (`genera_receivables_affitto_view`, `genera_settlement_view`) diventano action API (`receivables/genera-mese/`, `owner-settlements/genera/` — la seconda esiste già)

### 4.3 Servizi di calcolo

Firma cambiata da globale a per-property (modifica meccanica ma pervasiva):
- `quote_attive_at(property, data)` — e tutti i chiamanti
- `accounting/services/settlement.py`, `saldi_live.py` → `calcola_saldi_correnti(property, ...)`
- `billing/calc/rent.py::genera_pagamenti_mese(property, ...)`; il task/command mensile itera su tutte le property
- dashboard proprietario, conto economico, quadro annuale → property-scoped
- management command: tutti quelli operativi guadagnano `--property` (obbligatoria dove oggi c'è `.first()`)

---

## 5. Frontend (Quasar)

### 5.1 Infrastruttura property-aware (il grosso del valore con poco codice)

1. **Store `properties`** (`src/stores/properties.ts`): lista property dell'utente (da
   `/api/auth/user/` esteso), `activePropertyId` persistito in `localStorage`,
   getter `activeProperty`, `myRole`.
2. **Interceptor axios** (`boot/axios.ts`): aggiunge `X-Property-Id` a ogni richiesta se
   presente. Gli store esistenti **non cambiano**.
3. **Cambio property = hard reload** (`window.location.assign`), stesso pattern già usato
   per l'impersonation: azzera tutti gli store Pinia senza dover implementare
   l'invalidazione cache in 17 store. Raffinabile in seguito, ma è la scelta robusta.
4. **Guard router** (`router/index.ts`): dopo `fetchMe`, se l'utente è lato proprietari e
   non ha property → redirect a onboarding (`/p/benvenuto`); se `activePropertyId` non è
   tra le sue property → reset alla prima.
5. **Property switcher** in `ProprietarioLayout.vue`: `q-select`/menu in toolbar accanto al
   chip utente (o in testa al drawer). Con **una sola property il switcher non si mostra**:
   la moglie non deve mai accorgersi che l'app è multi-property. Badge del ruolo
   (`gestore`) quando ≠ proprietario.
6. Lato inquilino nessun cambiamento visibile.

### 5.2 Nuove pagine "anagrafiche" (portare l'admin nel FE)

Nuova voce menu **"Impostazioni"** (o "La casa") con sottosezioni, riusando i pattern
esistenti (tabelle + dialog modali già usati in Spese/Utenze):

| Pagina | Contenuto | Priorità |
|---|---|---|
| `/p/impostazioni/proprieta` | dati immobile, conto domiciliazione utenze, owner anticipa cessioni | P1 |
| `/p/impostazioni/membri` | membri, ruoli, **quote versionate**, inviti co-proprietario/gestore | P1 |
| `/p/impostazioni/stanze` | CRUD stanze | P1 |
| `/p/impostazioni/contratti` | CRUD contratti | P1 |
| `/p/inquilini` (estesa) | + "Nuovo inquilino" (wizard: profilo → stanza/canone → invito app), edit, **wizard cessione** | P1 |
| `/p/impostazioni/conti` | conti bancari propri | P2 |
| `/p/impostazioni/spese` | categorie + fornitori | P2 |
| `/p/impostazioni/solleciti` | regole + template messaggi | P2 |
| `/p/impostazioni/tari` | costi annuali (AnnualUtilityCost) | P2 |
| `/p/benvenuto` | onboarding prima property: nome/indirizzo → stanze → contratto → primo inquilino | P1 (serve per l'appartamento della moglie) |

### 5.3 Flusso concreto "appartamento della moglie" (caso di collaudo end-to-end)

1. Sandro (da `/p/`): "Nuova proprietà" → onboarding → property #2 con 1 contratto e N stanze (anche 1 sola: il modello a stanze copre l'appartamento intero con una stanza unica).
2. Da `/p/impostazioni/membri` invita la moglie come **proprietaria** (quota 1.0); lui stesso risulta **gestore** (chi crea una property può scegliere il proprio ruolo: proprietario o gestore).
3. La moglie riceve l'email, imposta la password, entra su `/p/` e vede **solo** il suo appartamento, senza switcher.
4. Sandro con lo switcher passa da Via Palestrina all'appartamento; su quest'ultimo non compare nei saldi fra proprietari (nessuna quota).

---

## 6. Fasi di lavoro

Ogni fase lascia l'app **funzionante e deployabile** (la produzione con la sola Via
Palestrina non deve rompersi mai).

### Fase A — Fondamenta dati (backend only, invisibile agli utenti)
- Nuovi modelli `PropertyMembership` (+ choices ruoli), migrations + backfill (§2.3)
- FK `property` su tutti i modelli in §2.2, vincoli per-property
- `quote_attive_at(property, data)` e servizi di calcolo per-property
- Rimozione hardcode (§2.4), seed aggiornati con 2ª property demo
- Comando `check_multiproprieta`; test migrazione su dump di produzione
- **Stima: 1-1,5 settimane** — è la fase più delicata (tocca i calcoli)

### Fase B — Permessi e API property-scoped
- `PropertyScopedMixin`, nuove permission class, filtro di ogni viewset/dashboard
- Endpoint `properties/`, `memberships/`, `shares/`, `/api/auth/user/` esteso
- Impersonation filtrata per property
- **Suite pytest cross-property** (il criterio di "fatto" della fase)
- **Stima: 1 settimana**

### Fase C — Frontend multi-property
- Store `properties`, interceptor header, guard, switcher, hard-reload al cambio
- Onboarding `/p/benvenuto` + CRUD proprietà + pagina membri/quote/inviti
- **Criterio di "fatto": il flusso §5.3 completo, verificato via agent-browser con screenshot**
- **Stima: 1-1,5 settimane**

### Fase D — Anagrafiche nel frontend (svuotare l'admin)
- Endpoint CRUD di §4.2 + pagine di §5.2 (prima le P1, poi le P2)
- Wizard cessione e wizard nuovo inquilino con invito
- **Stima: 2 settimane** (incrementale, si può rilasciare a pezzi)

### Fase E — Rifiniture multi-utente
- Registrazione self-service nuovi landlord (se si vuole aprire oltre la famiglia — opzionale, decisione separata: finché no, i nuovi utenti nascono solo per invito o da admin)
- Visibilità BankTransaction raffinata, partitario bilaterale ristretto alla coppia
- Notifiche con deep-link property-aware; export commercialista per-property
- **Stima: a consumo**

**Totale realistico per arrivare al caso d'uso della moglie (A+B+C): ~4 settimane; con le anagrafiche complete (D): ~6.**

---

## 7. Rischi e punti d'attenzione

1. **I calcoli sono il cuore**: settlement, saldi live, conguagli e quadro annuale oggi
   aggregano tutto senza filtro. Un filtro dimenticato = numeri sbagliati ma plausibili.
   Mitigazione: test di caratterizzazione *prima* del refactoring (stessi numeri di oggi
   sulla property Palestrina), poi test cross-property.
2. **Migrazione produzione**: i dati storici (2 anni di conguagli, riconciliazioni,
   settlement) devono uscire identici dopo il backfill. Provare su dump reale, confrontare
   il quadro annuale e i saldi prima/dopo.
3. **Vincolo somma quote per property**: il cambio quote (es. uscita di Fabio) va fatto in
   transazione atomica — l'attuale validazione record-per-record va adattata (già oggi è
   fragile, `owner.py:146-149`).
4. **Scope creep sul "SaaS"**: questo piano rende Viapal multi-famiglia, non un prodotto
   pubblico. Niente fatturazione/subscription/limiti/self-signup aperto finché non serve.
5. **Ledger storico e partitario**: le entry esistenti sono tutte di Via Palestrina — il
   backfill è banale; ma la decisione "partitario bilaterale personale (cross-property)"
   va confermata con l'uso reale.

## 8. Decisioni prese (confermate da Sandro il 2026-07-11)

| Decisione | Scelta |
|---|---|
| Chi può creare nuove property? | Qualsiasi utente "lato proprietari" (membro di almeno una property). Il self-signup pubblico resta chiuso. |
| Categorie spesa globali o per-property? | Per-property, seed automatico dei default alla creazione. |
| Visibilità BankTransaction fra co-membri | Sì, come oggi: chi condivide una property col titolare del conto vede i movimenti. Eventuale flag privacy in Fase E. |
| Partitario bilaterale | **Legato alla proprietà** (FK `property`), visibile ai membri di quella property. |
| Denormalizzare `property` su `Receivable`? | No: derivata via `assignment__room__property`. |
| Header `X-Property-Id` vs query param | Header via interceptor axios (zero modifiche agli store esistenti). |
| Via all'implementazione | Fase A approvata e avviata il 2026-07-11. |

## 9. Stato di avanzamento

- ✅ **Fase A** completata (2026-07-11): PropertyMembership, FK property su
  tutti i modelli, migrations con backfill, calcoli per-property, hardcode
  rimossi, seed con 2ª property demo, `check_multiproprieta`.
- ✅ **Fase B** completata (2026-07-11): permission class membership-based
  con ruoli, scoping di tutti i viewset/dashboard, API
  `properties`/membri/quote/inviti, `/api/auth/user/` con elenco immobili,
  suite cross-property (56 test di isolamento). Suite totale: 511 test.
- ✅ **Fase C** completata (2026-07-11): store `properties` + interceptor
  `X-Property-Id`, switcher nel layout proprietari (nascosto con un solo
  immobile, badge ruolo), pagina "Nuova proprietà" (con scelta del ruolo
  del creatore) e pagina "Immobile" (dati, membri con inviti email, quote
  versionate). Verifica browser con screenshot in
  `tests/screenshots/multiproprieta/`.
- ✅ **Fase D** completata (2026-07-11): CRUD via API per stanze,
  contratti, assignment (con action cessione), inquilini (con creazione
  utente e invito), conti bancari, categorie, fornitori, TARI, regole
  solleciti e template (94 test nuovi; suite a 605). Frontend: pagina
  "La casa" (tab Stanze/Contratti/Spese/TARI), "Nuovo inquilino" con
  invito, wizard "Cessione" nel dettaglio inquilino. Restano in admin
  solo operazioni di manutenzione straordinaria.
- ⏭ **Fase E** — rifiniture (visibilità BankTransaction raffinata,
  export commercialista per-property, notifiche deep-link) a consumo.
