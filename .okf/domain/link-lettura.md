---
type: Feature
title: Link di lettura dei documenti
description: Pacchetto di documenti aperto da un token, senza account, per chi deve ancora firmare; copie oscurate riusabili e chiarimenti in markdown.
resource: backend/apps/properties/models/share.py
tags: [feature, public, documenti, privacy, token]
timestamp: 2026-08-26T00:00:00Z
---

# Overview

Mandare a un inquilino in arrivo un indirizzo che apre le carte da leggere
prima della firma — **senza account** e **senza i dati personali di chi ha
firmato prima**. Seconda area pubblica dell'app dopo la
[galleria](galleria-pubblica.md), e come quella `AllowAny` con
`authentication_classes = []`.

Il piano approvato è in `docs/piano-link-lettura.md`; qui sta ciò che il
codice da solo non racconta.

# Due campi, due significati distinti

Su `PropertyDocument`:

- **`copia_di`** (FK a sé stesso) — «questo non è un originale, è la copia
  per la lettura di quell'altro». Valorizzato ⇒ **fuori da tutte le liste
  ufficiali** (chip del contratto, «Altri documenti», pagina
  `/i/documenti` dell'inquilino), dentro la sezione «Copie per la lettura».
- **`esponibile`** (bool) — «può stare in un link». Serve alle regole di
  convivenza, che sono un documento ufficiale a tutti gli effetti e vanno
  esposte così come sono. Una copia nasce con la spunta già messa.

«Non è ufficiale» e «si può mandare fuori» sono cose diverse: un documento
può essere la seconda senza essere la prima. Un flag unico avrebbe confuso i
due casi.

**`copia_di` è `PROTECT`, non `SET_NULL`** (il piano diceva `SET_NULL`):
azzerandolo, eliminando l'originale, la copia oscurata diventerebbe un
documento ufficiale a tutti gli effetti — comparirebbe in «Altri documenti»
e, se `visibile_inquilini`, nella pagina degli inquilini. Esattamente
l'esito che il campo esiste per impedire. Con `PROTECT` l'eliminazione
dell'originale dà 409 (`ProtectedDestroyMixin` sul viewset).

Una copia non può avere copie: un livello solo (`valida_copia`).

**Un documento `esponibile` legato a un contratto è ammesso, ed è il caso
normale**: la copia oscurata eredita il `contract` dell'originale, e in un
pacchetto ci va proprio quella. Il gate `contract` che regola cosa vede un
inquilino (`RoomAssignment.contract`) non si applica qui — chi apre il link
non è un inquilino e non ha assegnazioni. Ciò che tiene è `esponibile`, e
nient'altro: marcare a mano una side letter come esponibile la manda fuori
davvero. È voluto (serve per le regole di convivenza), ma va saputo.

# Invarianti

1. **Nel link entra solo ciò che è `esponibile`, e il controllo è al momento
   di servire**, non solo quando si compone: `DocumentShare.voci_servibili()`
   filtra l'elenco e `PublicShareFileView` ricontrolla prima del file.
   Togliere la spunta è quindi una **revoca a grana fine** sui link già
   mandati.
2. **Il pacchetto referenzia, non copia.** La stessa copia oscurata si riusa
   per ogni destinatario. Rovescio della medaglia: sostituire il file la
   cambia in tutti i link già mandati — voluto (correggi un'omissione una
   volta sola). Se un giorno servisse congelare un pacchetto, si aggiunge
   allora.
3. **Una voce è un documento oppure un testo**, mai entrambi né nessuno
   (`ShareItem.valida_voce`, in `clean()` e nel serializer).
4. **La copia oscurata non arriva all'inquilino.** Il filtro sta in due
   punti che vanno tenuti allineati: il ramo inquilino di
   `PropertyDocumentViewSet.get_queryset` e `_autorizza_documento_proprieta`
   in `core/media_private.py` — con l'URL in mano è il secondo che conta.

# Il token

`DocumentShare.token` = `secrets.token_urlsafe(32)`, `unique`, senza
scadenza, revocabile con `attivo`. `default=genera_token` è una **funzione a
livello di modulo**: `default=secrets.token_urlsafe(32)` verrebbe valutato
una volta sola alla definizione della classe e ogni riga avrebbe lo stesso
token (un link aprirebbe qualunque pacchetto); una lambda non è
serializzabile nelle migration.

Log minimo: `visite` e `ultima_visita`, incrementati con
`update(visite=F("visite")+1)`. Niente IP né user-agent — sono dati di un
terzo che non serve conservare.

# Il testo di chiarimento

`ShareItem.corpo_md` (markdown scritto a mano) → `corpo_html` reso e
sanitizzato **nel `save()` del modello**, con `markdown` + `nh3` e allowlist
stretta (niente `img`, niente attributi di stile, schemi `http/https/mailto`).
La pagina pubblica mostra solo HTML già passato dal sanitizzatore.

Il progetto ha la regola «HTML scritto da un utente non va in `v-html`»
(`ComunicazioniPannello` mette i `MessageTemplate` in un iframe
`sandbox=""`): sanitizzando a monte la si rispetta senza chiudere il testo
in un iframe, che in mezzo a una pagina sarebbe scomodo.

L'anteprima del compositore passa da `POST document-shares/anteprima-markdown/`
e **non** da un renderer JS: due renderer significherebbero un'anteprima che
mente.

# Serving del file

`PublicShareFileView` è una **vista sorella** di `core/media_private.py`, non
un suo ramo. Quella vista ha una dottrina sola — «autorizzazione dal record
che possiede il file, utente autenticato» — e chiude con
`if not request.user.is_authenticated: raise PermissionDenied`. Qui il record
che autorizza è il token: separarle lascia intatta l'invariante dell'altra.

`FileResponse(..., as_attachment=False)` + `X-Robots-Tag: noindex, nofollow`.
I file restano sotto `documenti-proprieta/` in `media-private`, quindi
restano raggiungibili anche dalla vista autenticata per i membri: giusto,
sono documenti dell'immobile. **Mai sotto `media/`**, che è servito
pubblicamente e darebbe un link funzionante gratis — enumerabile,
indicizzabile, non revocabile.

# API

Pubbliche (`AllowAny`, nessuna sessione):

| Endpoint | Cosa dà |
|---|---|
| `GET /api/v1/public/documenti/<token>/` | `{casa, destinatario, introduzione, voci}`; 404 se sconosciuto o revocato; incrementa `visite` |
| `GET /api/v1/public/documenti/<token>/file/<item_id>/` | il PDF inline; 404 se la voce non è di quello share o il documento non è più esponibile |

Gestione (`IsPropertyMember`): `document-shares/` (+ `revoca/`, `riattiva/`,
`riordina/`, `anteprima-markdown/`), `share-items/`, e su
`property-documents/<pk>/` l'azione `copia-lettura/` (upload del file
oscurato, con `copia_di` ed `esponibile` valorizzati dal server —
`copia_di` è read-only nel serializer, non lo si imposta con un POST
generico).

# Frontend

- Gestione: nel tab «Contratti e documenti» due sezioni nuove,
  `CopieLetturaPannello` e `LinkLetturaPannello` (+ `ComponiLinkDialog`,
  `CopiaLetturaDialog`). La separazione delle tre liste è **client-side**
  sul campo `copia_di`: il queryset di gestione le restituisce tutte.
- Pubblico: route `/d/:token`, `PublicLayout`, `PacchettoDocumenti.vue`.
  `/api` è già nella `navigateFallbackDenylist` del service worker, `/d/`
  no — ed è giusto così, è una rotta SPA.

# Fuori dall'applicazione, per scelta

**L'oscuramento dei PDF lo fa Sandro**, fuori dall'app. Niente comando
PyMuPDF: sul contratto reale coprirebbe una pagina su sette (le altre sono
scansioni senza strato di testo) e darebbe una falsa sicurezza sulle altre
sei. L'applicazione si limita all'avvertenza nel dialog di caricamento —
il rettangolo nero non cancella il testo sotto, va appiattito in immagini,
e i metadati vanno controllati.

# Non fatto

- Variante **anonima dell'atto di subentro** (`OMISSIS` sui campi
  dell'uscente) generata direttamente come copia esponibile: fase 4 del
  piano, non implementata.
- Segnaposto `{{quota_condominio}}` nei chiarimenti: per ora il valore lo si
  scrive a mano, e resta quello del giorno in cui il link è stato mandato —
  che per un chiarimento è probabilmente giusto.
