---
type: Architecture
title: PWA e service worker
description: Service worker Quasar, Web Push e gestione del reload post-deploy.
resource: frontend/src-pwa/custom-service-worker.ts
resources:
  - frontend/src-pwa/custom-service-worker.ts
  - frontend/src-pwa/register-service-worker.ts
  - frontend/quasar.config.ts
  - frontend/src/composables/usePush.ts
  - frontend/src/components/profilo/NotifichePushPannello.vue
  - backend/apps/notifications/push.py
tags: [architecture, pwa, service-worker, push]
generated:
  by: process:okf-migrate
  at: 2026-09-13T00:00:00Z
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
  prova a se stessi). Compare in **due** posti, perché l'endpoint è
  `IsAuthenticated` e non riguarda solo gli inquilini: `/i/profilo` e
  `/p/profilo` (area personale del proprietario, dal menu sul proprio nome in
  testata).
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

# Vedi anche

- [Reference modelli notifications](/models/notifications.md)
