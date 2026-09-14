---
type: Architecture
title: PWA e service worker
description: Service worker Quasar, Web Push, installazione guidata e reload post-deploy.
resource: frontend/src-pwa/custom-service-worker.ts
resources:
  - frontend/src-pwa/custom-service-worker.ts
  - frontend/src-pwa/register-service-worker.ts
  - frontend/quasar.config.ts
  - frontend/src/composables/usePush.ts
  - frontend/src/composables/useInstallPwa.ts
  - frontend/src/boot/pwa-install.ts
  - frontend/src/pages/InstallaApp.vue
  - frontend/src/components/InstallaBanner.vue
  - frontend/src/components/profilo/NotifichePushPannello.vue
  - backend/apps/notifications/push.py
tags: [architecture, pwa, service-worker, push]
generated:
  by: process:okf-migrate
  at: 2026-09-14T11:00:00Z
---

# Overview

Il frontend è una PWA Quasar con service worker in modalità **InjectManifest**
(SW custom che integra il precache Workbox). Due criticità note sono state
risolte e vanno preservate.

# Denylist di navigazione

Il SW ha scope `/` e di default dirottava `/admin` (Django) sulla SPA, mostrando
una pagina beige. Fix: `denylist` della `NavigationRoute` nel SW custom
(`src-pwa/custom-service-worker.ts`, solo `process.env.PROD`) — con
`InjectManifest` la `navigateFallbackDenylist` di `quasar.config.ts` non
si applica più, resta solo un commento che rimanda al SW.

- Esclusi: `/admin`, `/api`, `/static`, `/media` (copre anche
  `/media-private`), `/accounts` (allauth) più `workbox-*.js` e il SW stesso.
- **Restano nel fallback** (sono rotte SPA): `/g/<slug>` (galleria, in prod
  la prima richiesta la serve Django con i meta OG — vedi
  [Galleria pubblica](/domain/galleria-pubblica.md)) e `/d/<token>`
  (pacchetto documenti). Aggiungere una rotta server-side nuova = aggiungerla
  alla denylist.
- In dev (`quasar dev -m pwa`) la `NavigationRoute` non viene registrata
  (blocco sotto `process.env.PROD`): i path Django li serve il proxy del dev
  server Quasar (`/api`, `/admin`, `/static`, `/media-private`, `/media`,
  `/g/` → `VIAPAL_BACKEND_PORT`, default 8020).

# Reload post-deploy

`skipWaiting` fa attivare subito il nuovo SW, che però purga i chunk vecchi
ancora referenziati dal bundle in esecuzione → app piantata dopo un deploy.
Fix: **auto-reload su `controllerchange`** in
`src-pwa/register-service-worker.ts`. Protegge solo i deploy futuri; i
client con bundle pre-fix richiedono una pulizia SW manuale una tantum.

- Il listener si registra solo se esiste già `navigator.serviceWorker.controller`:
  alla prima installazione non c'è controller → nessun reload spurio.
- Flag `reloading` per evitare reload multipli sullo stesso evento.
- `cleanupOutdatedCaches()` nel SW resta: è il reload che rende innocua la
  purga della precache vecchia.

# Installazione guidata (/installa)

Pagina pubblica `/installa` (`PublicLayout`, come `/g/` e `/d/`): il link si
manda a chi non ha ancora fatto il primo accesso, quindi non può richiedere
la sessione.

# Installazione e notifiche sono due cose distinte

Legate **solo su iOS**, dove le push esistono unicamente dentro la PWA
installata (≥ 16.4). Su Android, su Chrome e su Firefox per computer le
notifiche arrivano **senza installare niente**. Presentarle come un
percorso unico che parte dall'installazione è falso quasi ovunque e mette
davanti, a chi legge da un computer, il passo che gli serve meno.

Quindi la pagina ha **due passi**, in quest'ordine:

1. **Accendi le notifiche** — l'accesso è il prerequisito di questo passo e
   vive dentro di esso (`Accedi`), non come passo a sé: altrimenti la
   numerazione cambierebbe con lo stato di login. Su iOS non installato, al
   posto del toggle c'è l'avviso che rimanda al passo 2.
2. **Mettila fra le tue app** — marcata «facoltativo», tranne su iOS dove
   il badge dice «serve per le notifiche».

# Il rilevamento decide l'evidenza, non l'esistenza

Errore commesso e corretto il 14/09/2026: il rilevamento di piattaforma e
browser era usato come **filtro esclusivo**, e il passo di installazione
aveva sei esiti mutuamente esclusivi (fino a nessuna istruzione del tutto,
su Firefox desktop). Ma questa pagina ha **due lettori**: chi la segue sul
proprio telefono e chi la guarda da un computer per sapere cosa dire agli
altri. Nascondere le altre piattaforme rende la pagina inutile al secondo,
e nessuno può vedere cosa vedono gli altri.

Ora le **tre sezioni** (iPhone · Android · computer) ci sono sempre, in
`q-expansion-item`: quella rilevata è aperta e marcata «stai leggendo da
qui», le altre sono a un tocco. `default-opened`, **non** `model-value`:
legata al valore la sezione resterebbe bloccata e le altre non si
aprirebbero.

Regola del contenuto: ogni sezione ha un testo **predefinito** (il browser
più diffuso su quella piattaforma) e usa la variante del browser reale
**solo se è la piattaforma rilevata** — degli altri dispositivi non
sappiamo il browser, e indovinarlo darebbe istruzioni sbagliate con l'aria
di essere giuste.

- **Firefox su computer non installa** le app web (serve un'estensione; il
  nativo è sperimentale e solo su Windows). L'avviso sta **accanto** alle
  istruzioni di Chrome/Edge, non al posto loro, con una riga che dice a
  quale browser si riferiscono i passi che seguono. Su Android Firefox
  installa benissimo: la condizione è `desktop && firefox`.
- **Safari su Mac**: Archivio → Aggiungi al Dock, solo da macOS 14.
- **Su iOS sono tutti WebKit** per obbligo di piattaforma: una sola
  istruzione, cambia solo dove sta il pulsante Condividi.
- `beforeinstallprompt` **batte lo user agent**: se il browser ha offerto
  l'installazione sa installare, e l'euristica (che legge stringhe) non
  deve poter nascondere un bottone che funziona.

# Il resto del passo installazione

- **`beforeinstallprompt` va intercettato nel boot**, non nella pagina:
  Chromium lo spara all'avvio dell'app, molto prima che la rotta lazy sia
  montata. Ascoltarlo in `onMounted` significa perderlo a ogni caricamento
  a freddo e non abilitare mai il bottone. `boot/pwa-install.ts` registra
  gli ascoltatori, `composables/useInstallPwa.ts` tiene l'evento in stato di
  modulo. Serve `preventDefault()`, o Chrome si tiene l'evento per la sua
  infobar. `prompt()` è **usa e getta**: si consuma alla prima chiamata.
- **Da computer il riquadro «Portala sul telefono»**: QR della pagina più
  il link da copiare. È l'uso vero da desktop — l'app serve in tasca — e il
  QR si genera con `qrcode`, già dipendenza per il GiroCode dei bonifici
  (`useEpcQr` resta specifico dell'EPC, non si tocca).
- **Stato dedotto dal vivo**, mai memorizzato: `display-mode: standalone`
  (più `navigator.standalone` per iOS) e l'evento `appinstalled`. Così la
  stessa URL, riaperta dall'icona, riconosce da sé di essere nell'app.
- **Browser in-app** (WhatsApp, Facebook): da lì non si installa nulla.
  Rilevato **solo** per marcatori espliciti nello user agent (`FBAN`,
  `Instagram`, …) e per il `; wv)` delle WebView Android. Su iOS si
  potrebbe dedurlo dall'assenza di `navigator.standalone`, ma quella prova
  pesca dentro anche Chrome e Firefox per iOS, dove installare si può.
- **Testi anfibi, nessuna variante per ruolo**: la pagina si apre quasi
  sempre prima del login, quando il ruolo non si sa.
- Il passo 1 riusa `NotifichePushPannello.vue` — è il terzo punto in cui
  compare, dopo `/i/profilo` e `/p/profilo`. La notifica di **prova** resta
  l'unica a non scrivere nel registro (`salva_notification=False`): è una
  verifica su di sé, non una comunicazione.

**Il collo di bottiglia è la scoperta, non la pagina**: nessuno cerca
`/installa` da solo. La striscia `InstallaBanner.vue` sta nei layout di
inquilino e proprietario e porta lì.

- Va **dentro `q-page-container`**, non accanto: fuori di lì il drawer
  persistente del layout proprietario copre icona e testo.
- Sparisce da sé quando l'app è installata (`display-mode: standalone`), ma
  **compare anche dove installare non si può**: la pagina a cui porta offre
  comunque le notifiche e le istruzioni da girare a chi ha un telefono.
- Nomina le **notifiche**, che valgono ovunque, e l'app come secondo
  motivo: promettere l'una attraverso l'altra è vero solo su iPhone.
- Chiuderla la rinvia di **30 giorni**, non per sempre: chi la chiude di
  fretta è esattamente chi non ha ancora installato niente. Scadenza in
  `localStorage` (`vp-installa-rinviato`), letta e scritta in `try/catch` —
  in navigazione privata può sollevare, e allora il banner compare e basta.

# Web Push

- VAPID + funzione `invia_push` (`notifications/push.py`); SW gestisce
  `push` (mostra la notifica) e `notificationclick` (apre/focalizza l'app).
- `push_configurato()` = chiavi VAPID presenti; senza chiavi il canale è un
  **no-op silenzioso**, non un errore.
- Sottoscrizione modellata da `PushSubscription`: una riga **per dispositivo**
  (non per persona), rimossa al primo 404/410 del push service.
- Il toggle è il componente `NotifichePushPannello.vue`, che incapsula
  `usePush.ts` (`GET /api/v1/push-subscriptions/vapid-public-key/`,
  `POST/DELETE /api/v1/push-subscriptions/`, `POST .../test/` per l'invio di
  prova a se stessi). Compare in **tre** posti, perché l'endpoint è
  `IsAuthenticated` e non riguarda solo gli inquilini: `/i/profilo`,
  `/p/profilo` (area personale del proprietario, dal menu sul proprio nome in
  testata) e il passo 3 di `/installa`.
- `disponibile` = **il server** ha le chiavi (o non si è potuto chiedere): senza
  canale il pannello non si disegna affatto, invece di offrire un toggle inerte.
  Quando invece il canale c'è ma questo browser non può usarlo, il pannello
  compare e **dice perché** — l'assenza muta non si distingue da un bug.
- Tre cause producevano la stessa pagina vuota, ora separate in `usePush`:
  - **contesto non sicuro** (`isSecureContext`): fuori da HTTPS/localhost il
    browser non espone affatto `serviceWorker`/`PushManager`. È la causa più
    comune e non dipende dal browser ma dall'indirizzo: `viapal.local:9020`
    non è sicuro, `viapal.localhost:9020` sì (per specifica, **qualsiasi**
    nome che finisce in `.localhost` lo è). Il banner riporta l'origine in chiaro.
  - **API assenti in contesto sicuro**: finestra in navigazione privata.
  - **verifica fallita** (`verificaFallita`): la GET `vapid-public-key` non è
    arrivata a destinazione — backend in riavvio. `init` ritenta 3 volte con
    backoff prima di arrendersi; gira una volta sola in `onMounted`, quindi
    senza ritentativi il toggle spariva fino al reload successivo. Un 4xx del
    server è invece una risposta vera: niente canale per quell'utente, non si insiste.
- Chiavi VAPID presenti sia in dev (`core/settings/dev.py`) sia in produzione
  (`local.py`, generate con `genera_chiavi_vapid`).

# La sottoscrizione è del browser, non della persona

`PushSubscription.endpoint` è **unique** e l'upsert dell'API riassegna
`user` a chi sta facendo la POST. Sullo stesso profilo browser, quindi,
chi attiva le notifiche per secondo **si prende la sottoscrizione del
primo**, che da quel momento non riceve più nulla — il logout non chiama
`unsubscribe()`, così `getSubscription()` restituisce sempre lo stesso
endpoint. Sul telefono personale è il comportamento giusto (stesso device
dopo un cambio password); è una trappola sul browser dove ci si alterna, e
per provare i due lati servono **due profili browser distinti**.

Il caso reale (13/09/2026): Sandro attiva, poi Arun attiva sullo stesso
Chrome; Arun dichiara un pagamento e ai proprietari non arriva niente,
perché Sandro non ha più device. Due contromisure, nessuna delle quali
cambia l'upsert:

- `invia_push` **registra ogni tentativo**, anche «nessun dispositivo
  registrato» (vedi [registro](/models/notifications.md)): prima quel caso
  non lasciava traccia da nessuna parte, ed è proprio quello da leggere.
- Il pannello elenca i **dispositivi attivi** dell'utente (`GET
  /api/v1/push-subscriptions/`, riga «questo» per endpoint, `×` per
  disattivarne uno): la lista vuota, o senza il proprio browser, si vede
  prima che manchi una notifica. La notifica di **prova** resta l'unica a
  non scrivere nel registro (`salva_notification=False`): è una verifica su
  di sé, non una comunicazione.

# Vedi anche

- [Reference modelli notifications](/models/notifications.md)
