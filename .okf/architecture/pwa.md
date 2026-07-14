---
type: Architecture
title: PWA e service worker
description: Service worker Quasar, Web Push e gestione del reload post-deploy.
resource: frontend/
tags: [architecture, pwa, service-worker, push]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

Il frontend è una PWA Quasar con service worker in modalità **InjectManifest**
(SW custom che integra il precache Workbox). Due criticità note sono state
risolte e vanno preservate.

# Denylist di navigazione

Il SW ha scope `/` e di default dirottava `/admin` (Django) sulla SPA, mostrando
una pagina beige. Fix: `navigateFallbackDenylist` in `quasar.config.ts` per
escludere le rotte server-side (`/admin`, `/api`, ...).

# Reload post-deploy

`skipWaiting` fa attivare subito il nuovo SW, che però purga i chunk vecchi
ancora referenziati dal bundle in esecuzione → app piantata dopo un deploy.
Fix: **auto-reload su `controllerchange`**. Protegge solo i deploy futuri; i
client con bundle pre-fix richiedono una pulizia SW manuale una tantum.

# Web Push

- VAPID + funzione `invia_push`; SW gestisce l'evento `push`.
- Sottoscrizione modellata da `PushSubscription`; toggle in `/i/profilo`.
- In produzione servono solo le chiavi VAPID in `local.py`
  (comando `genera_chiavi_vapid`).

# Vedi anche

- [Reference modelli notifications](/models/notifications.md)
