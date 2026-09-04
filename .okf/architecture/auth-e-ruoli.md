---
type: Architecture
title: Auth e ruoli
description: Autenticazione a sessione, gruppi proprietari/inquilini, inviti e impersonation.
resource: backend/apps/accounts/permissions.py
resources:
  - backend/apps/accounts/permissions.py
  - backend/apps/accounts/serializers.py
  - backend/apps/accounts/inviti.py
  - backend/apps/accounts/impersonation.py
  - frontend/src/router/index.ts
tags: [architecture, auth, permissions]
timestamp: 2026-09-05T00:00:00Z
---

# Overview

Autenticazione **session-based** Django con `dj-rest-auth` (niente JWT). Il ruolo
(`UserSerializer.get_role`) è **lato gestione** (`proprietario`) se l'utente è
superuser o ha almeno una `PropertyMembership`; altrimenti decide il gruppo
`proprietari` / `inquilini` (legacy, creati al primo `migrate`). Dentro un
immobile il ruolo fine è quello della membership: `proprietario`, `gestore`,
`sola_lettura` — vedi [Permessi per immobile](/models/accounts.md).

# Endpoint

| Endpoint | Scopo |
|----------|-------|
| `POST /api/auth/login/` | login (username **o** email) |
| `GET /api/auth/user/` | utente corrente: `role`, `properties[]` (con ruolo e `tipo_gestione`), `default_property_id`, `owner_profile_id`, `bank_accounts`, `is_impersonated` |
| `POST /api/auth/logout/` | logout |
| `GET /api/auth/csrf/` | token CSRF |
| `POST /api/auth/password/reset/`, `.../reset/confirm/`, `.../change/` | dj-rest-auth; il link nella mail punta alla SPA `/imposta-password/:uid/:token` (`SpaPasswordResetSerializer`) |
| `POST /api/auth/impersonate/<tenant_id>/`, `.../impersonate/stop/` | hijack JSON |

Frontend: store Pinia `src/stores/auth.ts`, guard in `src/router/index.ts`. Al login il
redirect è automatico in base al ruolo: proprietari → `/p/`, inquilini → `/i/`
(`auth.homePath`). Rotte `meta.public` (niente login): `/login`,
`/password-dimenticata`, `/imposta-password/:uid/:token`, `/g/:slug`,
`/d/:token`, `/privacy`; `meta.role` rimanda a `homePath` chi ha il ruolo
sbagliato. Le API property-scoped ricevono `X-Property-Id` dall'interceptor
axios (immobile attivo dello store `properties`).

# Inviti e password

- Invito inquilino da azione admin **o** da `POST /tenants/<id>/invita/` (FE);
  token allauth (base36) riusato come token d'invito.
- Invito membro (`POST properties/<id>/inviti/`): crea utente + membership e
  manda l'email. Il link imposta-password si manda a chi **non ha una
  password utilizzabile** (`has_usable_password()`), non solo a chi è appena
  stato creato: altrimenti chi era stato invitato in precedenza e non aveva
  mai completato l'attivazione riceveva un avviso senza modo di entrare.
- Self-service: reset / cambio / imposta-password.
- Doppio login: username **oppure** email.

# Impersonation ("vedi come inquilino")

- Basata su `django-hijack`, esposta come endpoint DRF JSON.
- Gate centralizzato `puo_impersonare`: attore = superuser (nessun limite) o
  membro **operativo** (`proprietario`/`gestore`, non `sola_lettura`) di un
  immobile di cui il target è inquilino; target mai superuser né proprietario.
- La notification nativa di hijack è disattivata (dava 500 in admin, 2026-07-29).
- UI: bottone nel dettaglio inquilino (lato proprietario) + banner nel frontend impersonato.

# Vedi anche

- [Reference modelli accounts](/models/accounts.md)
- [Reference modelli properties](/models/properties.md) — `PropertyMembership`.
