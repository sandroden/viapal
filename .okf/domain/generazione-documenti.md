---
type: Domain Logic
title: Generazione documenti
description: Atto di subentro nel contratto e comunicazione di cessione di fabbricato generati in PDF dai dati già in archivio; il testo è un modello caricato per immobile, e i dati che mancano vengono elencati con il posto in cui compilarli.
resource: backend/apps/properties/documenti/
tags: [domain, documenti, pdf, proprietari]
timestamp: 2026-08-03T00:00:00Z
---

# Overview

Due documenti che si compilavano a mano fuori dall'applicazione:

* **Atto di subentro nel contratto di locazione** — il subentrante prende il
  posto dell'uscente nel contratto già registrato, alle stesse condizioni;
* **Comunicazione di cessione di fabbricato** (art. 12 D.L. 21.3.1978 n. 59)
  — il modulo da consegnare all'autorità per ogni nuovo occupante.

Il vincolo che dà forma a tutto: **i dati non si chiedono in un form**.
Vengono dall'archivio, e dove non esisteva il posto per metterli è stato
creato (vedi [Modelli properties](/models/properties.md)). Quando un dato
manca, l'applicazione non lo domanda: dice *dove* si compila e ci porta.

# I campi sono la dichiarazione

Ogni documento è una tupla di `Campo` (`documenti/base.py`). Da quella lista
discendono **entrambe** le cose che servono:

* il **contesto** passato al modello (chiave del campo → valore formattato);
* l'elenco dei **dati mancanti**.

Nessuna delle due è scritta a mano, quindi non possono divergere: aggiungere
un campo al documento lo fa comparire da solo fra i segnaposto disponibili e
fra i dati da compilare.

Attributi che governano il comportamento:

| Attributo | Effetto |
|---|---|
| `derivato` | composto da altri campi già controllati (riga anagrafica, blocco firme): non entra mai fra i mancanti |
| `obbligatorio=False` | casella che può restare in bianco (scala, interno, accessori) |
| `richiede` | predicato: se falso il campo non si applica a questo caso |
| `campo_db`, `oggetto` | servono a costruire il link al punto di compilazione |

`richiede` esiste per non elencare quattro dati quando a mancare è il
**collegamento**: se non si sa a chi si subentra, la riga mancante è una
sola («Inquilino uscente»), non le quattro che ne discendono. Stesso schema
per il firmatario della cessione.

## Le omissioni: lo stesso documento senza nessuno dentro

`Fonti.omissioni` è un insieme di token che valgono sia come **fonte** di un
campo (`tenant`, `uscente`, `assignment`, `deposito`) sia come singola
**chiave** di segnaposto (`oneri_accessori`). Un campo che ci ricade non
viene nemmeno letto — al suo posto va `OMISSIS` — **e non entra fra i dati
mancanti**. Quest'ultima metà è quella che conta: senza, un fac-simile non si
genererebbe perché «manca l'uscente», che è esattamente ciò che non deve
esserci.

`fonti_facsimile(immobile)` costruisce le fonti senza inquilino e senza
assegnazione: restano immobile, locatori, contratto registrato e clausole.
Il risultato si manda a chi deve ancora decidere — vedi
[Link di lettura](/domain/link-lettura.md).

## `Property.via` contiene già la denominazione

Il campo si chiama «via/piazza» e vale `"Via Palestrina"`, non `"Palestrina"`
(ci sta dentro anche `"Piazza Trento"`). La comunicazione di cessione lo usava
già così; l'atto di subentro anteponeva un altro `Via` e produceva
`"Monza, Via Via Palestrina n. 20"`. Corretto il 2026-08-26.

# Dove si compila

`DOVE` + `link_per` in `base.py` mappano ogni fonte al suo posto:

| Fonte | Dove | Esterno |
|---|---|---|
| `tenant` / `uscente` | scheda inquilino → Profilo, dialog anagrafica sul campo indicato | no |
| `property` | Immobile → Dati, sul campo indicato | no |
| `contract` | Immobile → Contratti, col dialog del contratto aperto | no |
| `assignment` | assegnazione stanza (admin) | **sì** |
| `deposito` | scheda inquilino (admin): nasce da `deposito_versato` o dalle rate della prima assegnazione, non dal form anagrafica | **sì** |
| `owner` | Immobile → Membri, dialog anagrafica sul campo indicato (`?tab=membri&modifica=anagrafica&owner=<pk>&campo=<campo>`) | no |
| `modello` | Immobile → Modelli documenti | no |

Tutti i punti di compilazione della PWA stanno su un'unica pagina a tab
(`/p/impostazioni`, «Immobile»); le vecchie route `/p/impostazioni/proprieta`
e `/p/impostazioni/casa` sopravvivono come redirect che preservano
`campo`/`contratto`.

L'anagrafica owner si scrive con `PATCH /owners/<pk>/`: il titolare la
propria (qualunque ruolo, anche sola_lettura), i proprietari dell'immobile
quella di tutti i membri; il gestore no, coerente con membri e quote.
L'anagrafica è del profilo, non della membership: vale per tutti gli
immobili in cui la persona compare.

`esterno: true` è l'unica eccezione consapevole alla regola «mai una nuova
scheda» del fascicolo: l'admin Django è fuori dalla PWA.

**Trappola**: i dialog aperti da un parametro della query vogliono
`no-route-dismiss`. La pagina riscrive subito la query per consumare il
parametro, e Quasar chiude i dialog al cambio rotta. Se poi il link punta
alla pagina in cui si è già, serve anche un `watch` sulla query: la rotta
non cambia e il componente non si rimonta.

# Il modello è un dato, non codice

Il testo dei documenti sta in `DocumentTemplate` (uno per immobile, `codice`
univoco), sul modello di `MessageTemplate`. Cambia da proprietà a proprietà
e a cambiarlo è il proprietario, non chi sviluppa. Nel repository restano
solo gli **esempi** (`documenti/esempi/*.html`), scaricabili e da adattare.

Per la prima configurazione di un immobile c'è
`manage.py carica_modelli_documenti --property <id>`: carica gli esempi in un
passo solo e **non tocca** i modelli già presenti (`--force` per sovrascriverli),
perché la copia in tabella è quella che il proprietario ha adattato.

Se il modello non è caricato il documento non si genera, e la cosa compare
fra i dati mancanti come tutto il resto.

Il corpo è un documento HTML completo, `<style>` incluso, con segnaposto
`{{chiave}}` sostituiti con `str.replace` — **non** un template engine:
l'HTML lo carica un utente e non deve poter leggere variabili o includere
file. Per la stessa ragione WeasyPrint gira con un `url_fetcher` che rifiuta
ogni risorsa esterna: senza, un `<img src="file:///…">` finirebbe nel PDF.

Conseguenza inerente alla scelta: la copia in tabella **non segue** le
correzioni successive all'esempio nel repository. Chi aggiorna un esempio
deve ricaricarlo dove serve.

# Persistenza e rigenerazione

Il PDF è un `TenantDocument` come gli altri: eredita storage privato,
autorizzazioni `/media-private/`, visore interno e fascicolo. Il campo
`generato=True` lo distingue dai file caricati a mano.

**Rigenerare sostituisce solo i documenti con `generato=True`.** Il flusso
reale è genera → stampa → firma → scansiona → ricarica sotto lo stesso tipo:
senza quel filtro un "Rigenera" distruggerebbe l'unico originale firmato,
dal database e dallo storage, senza undo.

# Da dove si parte

L'azione **"Genera"** sta nel pannello del fascicolo, accanto a "Carica
documento" (scheda inquilino → Documenti, lato proprietario): apre l'elenco
dei documenti producibili e da lì il dialog di anteprima. Fino al 2026-08-03
i due documenti erano invece righe *in attesa* dentro il fascicolo — vedi
[Fascicolo documenti](/domain/fascicolo-documenti.md) per il perché sono
state tolte. Sulle voci già generate resta la scorciatoia "Rigenera".

# API

`GET /api/v1/tenant-documents/generabili/?tenant=<id>` — cosa si può
produrre (`codice`, `titolo`, `tipo`, `tipo_display`, `esistente`). Nessun
render, nessuna riga scritta: è la sorgente dell'elenco.

`POST /api/v1/tenant-documents/genera/` (header `X-Property-Id`,
`IsPropertyMember`), body `{tenant, documento, dry_run=true, assignment?}`.

* `dry_run` → 200 con `completo`, `mancanti[]`, `riepilogo`, `esistente`;
  il `riepilogo` è **dichiarato dal singolo documento** (`Documento.riepilogo`,
  base vuota): l'atto di subentro riporta le condizioni economiche, la
  cessione di fabbricato data, cedente e indirizzo — e nient'altro, perché
  quel modulo non dice a che prezzo si è ceduto (2026-08-03);
* `dry_run=false` e completo → 201 col `TenantDocument` e `sostituito`;
* 400 documento sconosciuto, tenant assente, nessuna assegnazione, dati
  incompleti (con l'elenco); 403 `sola_lettura`; 404 tenant di altro
  immobile.

Essendo una POST, `sola_lettura` non vede nemmeno l'anteprima — stesso
compromesso già accettato per l'invio dei riepiloghi addebiti.

`/api/v1/document-templates/` gestisce i modelli, con `esempio/` e
`segnaposto/` derivate dal generatore.

# Fonti dei dati

| Dato | Da dove |
|---|---|
| comproprietari alla data | `quote_attive_at()` |
| contratto in vigore | `Property.contratto_attivo()` |
| uscente | `assignment.subentra_a.tenant` — **mai** dedotto dalle date |
| oneri accessori | `TenantCondominioRate`, quota del singolo inquilino preferita alla generica |
| deposito e numero di rate | `Receivable` di causale `DEPOSITO` positivi |

Il subentro non si deduce: nel caso reale l'uscente chiude il 30/06 e
l'entrante parte il 22/07. L'action `cessione` valorizza `subentra_a` da sé,
perché lì il legame è certo.

# Vedi anche

- [Fascicolo documenti](/domain/fascicolo-documenti.md) — le voci generabili
  nella checklist.
- [Modelli properties](/models/properties.md) — anagrafiche, indirizzo
  strutturato, estremi di registrazione, `DocumentTemplate`.
- [Link di lettura](/domain/link-lettura.md) — il fac-simile e come finisce
  in un pacchetto da mandare fuori.
