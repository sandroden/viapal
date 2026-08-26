---
type: Feature
title: Galleria pubblica (annuncio affitto)
description: Pagina pubblica /g/<slug> con foto per stanza/spazi comuni, editabile in-place dal proprietario.
resource: backend/apps/properties/
tags: [feature, public, gallery, frontend]
timestamp: 2026-07-23T00:00:00Z
---

# Overview

Pagina **pubblica senza login** che presenta la casa/stanze in affitto come annuncio
(hero, planimetria, sezioni stanza con foto, posizione). Unica area pubblica dell'app.
Editabile **in-place** dal proprietario loggato (stessa pagina, toggle "Modifica").
Sviluppata sul branch `galleria-pubblica` staccato da `main` (indipendente dalla
multiproprietà non ancora validata); legata a `Property`, compatibile col merge futuro.

# Modello dati

Estende [properties](/models/properties.md):

- **`Property`**: `slug` (URL pubblico), `pubblica` (toggle), immagini singleton
  `foto_hero`/`foto_planimetria`/`foto_mappa`, `testi_pubblici` (JSONField: hero, `facts`
  mq/camere/bagni/letti, `posizione` indirizzo/mezzi/parcheggio/regole). Slug auto in
  `save()`; migration 0015 popola gli esistenti.
- **`Room`** (= **oggetto d'affitto**, la camera): campi d'annuncio espliciti `colore`,
  `descrizione`, `disponibile`, `libera_dal`, `prezzo_mensile`, `pubblica` — **indipendenti**
  dalle `RoomAssignment` contabili. **Il toggle `disponibile` è il comando principale di
  visibilità**: se spento → badge "Non disponibile", **niente foto e data ignorata** (a
  prescindere da `libera_dal`). Se acceso, `libera_dal` è solo un'etichetta: con una data
  **futura** mostra "Libera dal &lt;data&gt;" (stanza in annuncio con ingresso posticipato,
  messa alla disdetta ~2 mesi prima), altrimenti nessun badge. La regola "data futura" è nel
  frontend (`liberaDalFutura`), la visibilità foto nel serializer (`if not obj.disponibile`).
- **`GalleryArea`** (= **ambiente comune**: cucina, soggiorno, bagni…): `property`, `nome`,
  `colore`, `descrizione`, `ordinamento`, `pubblica`. **NON** è un oggetto d'affitto (niente
  assegnazioni/canone): è solo un raggruppamento di foto. Scelta deliberata per non assimilare
  la classificazione di una foto all'oggetto della locazione.
- **`GalleryImage`**: foto multiple, `property` FK + UNO fra `room` FK (camera) e `area` FK
  (ambiente comune), entrambi nullable, mutuamente esclusivi (validati). Upload in
  `media/galleria/<slug>/`. Campi d'annuncio: `didascalia`, `ordinamento` e **`formato`**
  (`quadrato`/`orizzontale`/`verticale`, default `quadrato`) — il formato governa lo span nella
  griglia (aspect-ratio + `grid-column`), **sostituendo il vecchio mosaico automatico**. Nuove
  foto vanno **in coda** alla sezione (`perform_create` assegna `max(ordinamento)+1`).

# API

- **Pubblica**: `GET /api/v1/public/galleria/<slug>/` — **AllowAny** (unica del progetto),
  `PublicGallerySerializer` dedicato, 404 se `pubblica=False`. Espone solo campi pubblici.
- **Scrittura** (membri operativi): `PATCH` su `properties`/`rooms` (testi, campi, immagini
  singleton), `gallery-areas` CRUD (ambienti comuni), `GalleryImageViewSet` CRUD foto.
  Quest'ultimo accetta **sia MultiPart (upload file) sia JSON** (`JSONParser`) per i PATCH di
  metadati — formato/didascalia/ordinamento — senza reinviare l'immagine. Clear di un'immagine
  singleton = PATCH con `null` (non `''` → 400).
- **Scoping multiproprietà** (dal merge 2026-07-23): i viewset galleria lavorano
  sempre sull'**immobile attivo** della richiesta (`get_request_property`, permesso
  `IsPropertyMember`); il `property` inviato dal client è validato contro l'attivo
  e forzato server-side in create. La suite `test_cross_property.py` copre
  `gallery-areas` e `gallery-images`. Il link "Galleria annuncio" nel menu
  proprietari usa lo slug dell'immobile attivo, mai `list[0]`.

# Frontend

Route `/g/:slug` `meta.public`, `GalleriaPubblica.vue` (sola lettura per anonimi). Edit-mode
per proprietario: `ImageSlot.vue` (upload file/drag/**paste Ctrl-V** via listener `document`
+ hover; prop `multiple` opt-in → evento `upload-many` per l'**upload multiplo simultaneo**,
i singleton restano a file singolo), `EditableText.vue` (`q-popup-edit`, **no contenteditable**).

**Ritorno alla gestione**: per l'utente autenticato il wordmark "Viapal · annuncio" è un
link (per l'anonimo resta un `<div>` inerte). Destinazione calcolata sull'**appartenenza**,
non sul ruolo — anche il gestore lavora da `/p/`: se l'immobile della galleria è fra le
membership si va a `/p/` **su quell'immobile**, via `propertiesStore.cambia(id)` quando non
è già l'attivo (hard reload voluto, azzera gli store dell'immobile precedente); altrimenti
`auth.homePath` (inquilino → `/i/`). Se la home risolve a `/login` il link non compare:
meglio nessun link che rimandare al login uno che è già dentro.

**Ridimensionamento lato client**: `handleFiles` di `ImageSlot` è l'unico imbuto per
picker/drag/paste e vi passa ogni file per `resizeImageFile` (`utils/image.ts`, portata dal
progetto "nicolas"): canvas → max 1920px di lato → **WebP** q 0.85 (fallback JPEG se il
browser non supporta WebP da canvas). Copre quindi sia i singleton sia le foto di sezione.
Un file non decodificabile (HEIC di iPhone: passa `image/*`, nessun decoder) viene caricato
**tale e quale**, così l'errore lo dà il validatore backend invece di sparire. Poiché l'emit
diventa async, `ImageSlot` ha un flag `processing` proprio (`uploading` è dello store e
resterebbe spento durante l'elaborazione). Backend invariato: `webp` è già in
`FileExtensionValidator`. Conseguenza: le foto nuove non sono più gli originali di camera.

**Scarica foto** (`ScaricaFotoDialog.vue`, bottone in navbar `v-if="canEdit"`): miniature di
tutte le foto raggruppate per sezione, selezione singola/sezione/totale, nomi
`<slug>-<sezione>-NN.<ext>` (l'attributo `download` di `<a>` è ignorato cross-origin e non
rinomina i file opachi di `/media`, da cui `fetch`→blob). **Una foto** → file singolo;
**più foto** → un unico **ZIP** costruito lato client da `utils/zip.ts` — implementazione
propria, metodo *store* senza compressione (le foto sono già JPEG/WebP: deflate non
guadagnerebbe nulla e servirebbe una libreria nel bundle). Lo ZIP evita anche il prompt
"consenti download multipli" di Chrome. Nessun endpoint nuovo: gli URL sono nel payload
pubblico. Limite noto: le foto delle stanze `disponibile=False` non sono nel payload
pubblico, quindi non compaiono nell'elenco.
Store `galleria.ts` (`uploadImages` batch = N POST + 1 refresh; `patchImage`; `reorderImages`).
Per ogni foto in edit: controlli **formato** (3 pulsanti crop), **didascalia** (overlay in basso,
editabile), **riordino** con frecce laterali `‹ ›` (scelta deliberata vs drag: robusta con le
celle a span variabile dei formati e verificabile). **Lightbox** navigabile (frecce, tasti
← → Esc, contatore, didascalia); scope = la sezione da cui si apre.

# Anteprime social (Open Graph)

Condividere `/g/<slug>` su WhatsApp, Facebook o Telegram mostrava un URL
nudo: quei crawler **non eseguono JavaScript**, e l'`index.html` della SPA
non ha meta tag. Perciò `/g/` **non è più servito da nginx ma da Django**
(label Traefik nel `docker-compose.yml`, proxy `/g/` in `quasar.config.ts`
per il dev): `properties/og.py` scarica l'`index.html` dal frontend
(`SPA_INDEX_URL`, cache 60") e vi inietta titolo e meta prima di `</head>`.
Il `<title>` originale viene sostituito, il resto della pagina è intatto —
la SPA parte come sempre.

- **Ripiego**: se il frontend non risponde (o `SPA_INDEX_URL` è vuoto, come
  nei test) la vista rende una pagina minimale con i soli meta: i crawler
  funzionano comunque. Slug sconosciuto → 404 **con** l'HTML della SPA, così
  il visitatore legge "Galleria non disponibile" e non l'errore di Django.
- **`SPA_INDEX_URL`**: in prod `http://viapal-quasar/` — alias di rete
  esplicito, perché sulla rete `web` condivisa col resto del server il nome
  di servizio `quasar` appartiene a una decina di progetti. In dev punta al
  dev server `:9020` (vuoto sotto pytest: niente rete nei test).
  **In deploy l'alias si applica solo ricreando il container**: serve
  `docker compose up -d quasar django`, non il solo `django`. Se l'alias non
  c'è il guasto è silenzioso — le anteprime social continuano a funzionare e
  solo chi apre il link vede la pagina di ripiego. Verifica in un colpo:
  `curl -s https://viapal.e-den.it/g/viapal | grep -c '/assets/'` — l'index
  vero ha i link agli asset, la pagina minimale no.
- **L'immagine non può essere la foto**: dal ridimensionamento lato client le
  foto sono **WebP**, che WhatsApp non renderizza. `og_image`
  (`/api/v1/public/og-image/<slug>.jpg`) ne deriva un **JPEG 1200×630**
  (ritaglio centrale, q78, ~250 KB: sopra i ~300 KB WhatsApp lascia perdere)
  e lo tiene in cache in `media/og/`. L'URL porta l'impronta del file
  sorgente (`?v=…`): Facebook ricorda uno scrape per settimane, cambiare
  foto deve cambiare l'URL. Sta sotto `/api/` per non aggiungere regole di
  routing.
- **Un link per camera**: `/g/<slug>?stanza=<camera>` dà titolo, descrizione
  e foto della singola camera. Il riferimento è il **nome in forma di slug**
  (`?stanza=camera-3`), leggibile da chi riceve il link; l'id numerico resta
  accettato per non rompere i link già condivisi, e il frontend risolve
  entrambi. Il pulsante "Copia link" accanto a ogni camera disponibile
  (solo proprietario) evita di doverlo comporre a mano: ripiega sull'id se
  il nome non dà uno slug utile (vuoto, o due camere omonime). Query e non fragment: `#room-3` il server non lo
  vedrebbe mai. `og:url` **deve** riportare il parametro, altrimenti i social
  deduplicano i cinque link e mostrano tutti la stessa card. Il frontend usa
  il parametro per scorrere alla sezione e darle un lampo di colore.
- **Service worker**: `/g/` resta fuori dalla denylist. I crawler non hanno
  SW; a un umano che ritorna, l'index dalla cache (senza meta iniettati) non
  toglie nulla.
- **Verifica**: `curl -s http://localhost:8020/g/<slug> | grep og:` e aprire
  il JPEG generato — la card si valuta guardandola. Dopo un cambio di foto in
  produzione, forzare il re-scrape con il Debugger di Facebook o
  `@WebpageBot` di Telegram.

# Note operative

- `/media` è servito pubblicamente (dev `static()`, prod Traefik→Django) — le foto galleria
  stanno in sottocartella dedicata `galleria/`. (Nota preesistente: anche i documenti privati
  sotto `/media` sono raggiungibili — fuori scope qui.)
- Per pubblicare: deploy + `Property.pubblica=True` via admin.

# Vedi anche

- [properties](/models/properties.md), [Auth e ruoli](/architecture/auth-e-ruoli.md),
  [PWA](/architecture/pwa.md) (route SPA non in denylist SW).
