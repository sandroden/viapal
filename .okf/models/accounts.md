---
type: Django App
title: App accounts
description: Autenticazione, permessi, inviti e impersonation.
resource: backend/apps/accounts/
tags: [models, accounts, auth]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

App trasversale per identità e accessi. Non definisce modelli propri di dominio:
l'anagrafica persona sta in `OwnerProfile`/`TenantProfile` (app properties). Qui
vivono permessi, inviti e impersonation.

# Moduli

| Modulo | Scopo |
|--------|-------|
| `permissions.py` | gate DRF (gruppi proprietari/inquilini) |
| `inviti.py` / `inviti_views` | invito inquilino + set/reset password (token allauth base36) |
| `impersonation.py` / `impersonation_views.py` | gate `puo_impersonare` + endpoint hijack JSON |
| `signals.py` | creazione gruppi e utenti dev al `migrate` |
| `serializers.py`, `views.py`, `urls.py` | endpoint auth DRF |

# Vedi anche

- [Auth e ruoli](/architecture/auth-e-ruoli.md) — descrizione completa del flusso.
