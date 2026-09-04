---
type: Django App
title: App accounts
description: Autenticazione, permessi, inviti e impersonation.
resource: backend/apps/accounts/permissions.py
resources:
  - backend/apps/accounts/permissions.py
  - backend/apps/accounts/inviti.py
  - backend/apps/accounts/impersonation.py
  - backend/apps/accounts/serializers.py
  - backend/apps/accounts/urls.py
tags: [models, accounts, auth]
timestamp: 2026-09-05T00:00:00Z
---

# Overview

App trasversale per identità e accessi. Non definisce modelli propri di dominio:
l'anagrafica persona sta in `OwnerProfile`/`TenantProfile` (app properties). Qui
vivono permessi, inviti e impersonation.

# Moduli

| Modulo | Scopo |
|--------|-------|
| `permissions.py` | gate DRF: per gruppo (`IsProprietario`, `IsInquilino`, `IsProprietarioOrReadOnly`) e **per immobile** (`IsPropertyMember`, `IsPropertyProprietario`, `IsInquilinoSelf`) |
| `inviti.py` | `invia_invito_inquilino` (azione admin e `POST /tenants/<id>/invita/`) e `invia_invito_membro` (`POST properties/<id>/inviti/`): creano utente/membership e mandano l'email; il link imposta-password usa il token allauth base36 e va a chi non ha `has_usable_password()` |
| `impersonation.py` / `impersonation_views.py` | gate `puo_impersonare` + endpoint hijack JSON |
| `signals.py` | **solo** i gruppi `proprietari`/`inquilini` al `post_migrate` di `auth`; gli utenti dev li crea `seed_demo` (app properties) |
| `serializers.py` | `UserSerializer` (`role`, `properties[]`, `default_property_id`, `owner_profile_id`, `bank_accounts`, `is_impersonated`, `impersonator_username`) e `SpaPasswordResetSerializer` (link di reset/invito verso la SPA) |
| `views.py`, `urls.py` | `csrf/`, `impersonate/<tenant_id>/`, `impersonate/stop/`, poi `dj_rest_auth.urls` (login/logout/user/password reset-confirm-change): non esiste un modulo `inviti_views` |

# Permessi per immobile

- L'immobile attivo viene da `properties.context.get_request_property`
  (header `X-Property-Id`, messo dall'interceptor axios, o l'unico accessibile);
  `ruolo_su_property` dà il ruolo della membership.
- `IsPropertyMember`: qualsiasi ruolo; `sola_lettura` solo metodi safe.
  Nessun immobile accessibile (es. inquilino) → 403, non 404.
- `IsPropertyProprietario`: solo ruolo `proprietario` (membri, quote,
  cancellazione immobile, chiusura campagna lead).
- `IsInquilinoSelf` (object-level): superuser tutto; membro dell'immobile
  dell'oggetto tutto; inquilino solo i propri oggetti.

# Vedi anche

- [Auth e ruoli](/architecture/auth-e-ruoli.md) — descrizione completa del flusso.
