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
  - backend/apps/notifications/push.py
tags: [architecture, pwa, service-worker, push]
timestamp: 2026-09-05T00:00:00Z
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
- Sottoscrizione modellata da `PushSubscription`; toggle in `/i/profilo` via
  composable `usePush.ts`: `GET /api/v1/push-subscriptions/vapid-public-key/`,
  `POST/DELETE /api/v1/push-subscriptions/`, `POST .../test/` (invio di prova
  a se stessi).
- In produzione servono solo le chiavi VAPID in `local.py`
  (comando `genera_chiavi_vapid`).

# Vedi anche

- [Reference modelli notifications](/models/notifications.md)
