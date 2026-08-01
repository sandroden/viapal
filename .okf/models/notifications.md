---
type: Django App
title: App notifications
description: Template messaggi, regole di reminder, Web Push e notifiche.
resource: backend/apps/notifications/models/
tags: [models, notifications, push]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

Notifiche verso utenti (email + Web Push) e regole di promemoria. Il canale push
è descritto in [PWA](/architecture/pwa.md).

# Modelli

| Modello | Campi chiave | Note |
|---------|--------------|------|
| `MessageTemplate` | `codice`, `titolo`, `corpo`, `canale` | template messaggio |
| `ReminderRule` | `applicabile_a`, `giorni_offset`, `canale`, `destinatario`, `template`, `attiva` | regola promemoria (offset da un evento) |
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

# Vedi anche

- [PWA / Web Push](/architecture/pwa.md).
- [Solleciti e registro comunicazioni](/domain/solleciti.md).
- `push.py` — `invia_push`; comando `genera_chiavi_vapid`.
