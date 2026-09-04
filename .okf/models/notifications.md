---
type: Django App
title: App notifications
description: Template messaggi, regole di reminder, Web Push e notifiche.
resource: backend/apps/notifications/models/notifications.py
resources:
  - backend/apps/notifications/models/notifications.py
  - backend/apps/notifications/push.py
  - backend/apps/notifications/views.py
  - backend/apps/notifications/api_urls.py
tags: [models, notifications, push]
timestamp: 2026-09-05T00:00:00Z
---

# Overview

Notifiche verso utenti (email + Web Push) e regole di promemoria. Il canale push
è descritto in [PWA](/architecture/pwa.md).

# Modelli

| Modello | Campi chiave | Note |
|---------|--------------|------|
| `MessageTemplate` | `property` (FK), `codice` (slug, univoco per immobile), `titolo`, `corpo`, `canale` (`email`/`push`/`sms`) | template messaggio, per immobile dal 2026-07-11 |
| `ReminderRule` | `property` (FK), `applicabile_a` (`affitto`/`conguaglio`/`extra`), `giorni_offset`, `canale` (`email`/`push`/`both`), `destinatario` (`inquilino`/`proprietario`/`entrambi`), `template`, `attiva` | regola promemoria (offset da un evento); il template deve essere dello stesso immobile |
| `PushSubscription` | `user`, `endpoint`, `auth`, `device_label`, `ultima_attivita` | sottoscrizione Web Push |
| `Notification` | `user`, `regola`, `oggetto`, `corpo`, `corpo_html`, `destinatario`, `codice`, `errore`, `inviata_at`, `letta_at`, `canale`, `oggetto_riferimento` (GFK) | comunicazione emessa (o tentata) |

`Notification` è il **registro delle comunicazioni**: archivia anche i
fallimenti. Invariante: `inviata_at` valorizzato = partita, `errore`
valorizzato = fallita (con `inviata_at` nullo). Il `codice` distingue
comunicazioni che condividono la stessa GenericFK (invito inquilino e
riepilogo addebiti puntano entrambi a un `TenantProfile`). Dettagli in
[solleciti](/domain/solleciti.md).

`ReminderRule` esiste come modello + admin + API ma **nessun engine la
consuma**: i solleciti si inviano a mano.

# Endpoint (`/api/v1/`)

| Route | Permesso | Note |
|---|---|---|
| `notifications/` | `IsAuthenticated` | sola lettura, le proprie |
| `comunicazioni/` | `IsPropertyMember` | sola lettura: registro per immobile, filtri attivi/tipo/periodo (pagina "Notifiche addebiti") |
| `message-templates/`, `reminder-rules/` | `IsPropertyMember` | CRUD scoped sull'immobile attivo; `ProtectedDestroyMixin` |
| `push-subscriptions/` | `IsAuthenticated` | CRUD delle proprie + `vapid-public-key/` (GET) e `test/` (POST, push di prova a se stessi) |

# Vedi anche

- [PWA / Web Push](/architecture/pwa.md).
- [Solleciti e registro comunicazioni](/domain/solleciti.md).
- `push.py` — `invia_push`; comando `genera_chiavi_vapid`.
