---
type: Architecture
title: Auth e ruoli
description: Autenticazione a sessione, gruppi proprietari/inquilini, inviti e impersonation.
resource: backend/apps/accounts/
tags: [architecture, auth, permissions]
timestamp: 2026-08-03T00:00:00Z
---

# Overview

Autenticazione **session-based** Django con `dj-rest-auth` (niente JWT). Il ruolo
è determinato dall'appartenenza ai gruppi `proprietari` / `inquilini`, creati
automaticamente al primo `migrate`.

# Endpoint

| Endpoint | Scopo |
|----------|-------|
| `POST /api/auth/login/` | login (username **o** email) |
| `GET /api/auth/user/` | utente corrente + gruppi |
| `POST /api/auth/logout/` | logout |
| `GET /api/auth/csrf/` | token CSRF |

Frontend: store Pinia `src/stores/auth.ts`, guard in `src/router/`. Al login il
redirect è automatico in base al gruppo: proprietari → `/p/`, inquilini → `/i/`.

# Inviti e password

- Invito inquilino da azione admin; token allauth (base36) riusato come token d'invito.
- Invito membro (`POST properties/<id>/inviti/`): crea utente + membership e
  manda l'email. Il link imposta-password si manda a chi **non ha una
  password utilizzabile** (`has_usable_password()`), non solo a chi è appena
  stato creato: altrimenti chi era stato invitato in precedenza e non aveva
  mai completato l'attivazione riceveva un avviso senza modo di entrare.
- Self-service: reset / cambio / imposta-password.
- Doppio login: username **oppure** email.

# Impersonation ("vedi come inquilino")

- Basata su `django-hijack`, esposta come endpoint DRF JSON.
- Gate centralizzato `puo_impersonare` (estendibile a scenari multiproprietà).
- UI: bottone nel dettaglio inquilino (lato proprietario) + banner nel frontend impersonato.

# Vedi anche

- [Reference modelli accounts](/models/accounts.md)
- [Documenti inquilino](/models/properties.md)
