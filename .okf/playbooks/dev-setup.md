---
type: Playbook
title: Dev setup
description: Avviare backend e frontend in locale (senza Docker).
resource: justfile
tags: [playbook, dev, setup]
timestamp: 2026-07-08T00:00:00Z
---

# Prerequisiti

`uv` ≥ 0.8, `bun` ≥ 1.2, `node` ≥ 22.22, `just`, `agent-browser` (validazione
visuale). Postgres: cluster `dev` su porta 5434, db `viapal`, utente `sandro`
(peer auth via socket). In dev **niente Docker**.

# Avvio

```bash
# Backend
cd backend && uv sync
ENV=dev uv run python manage.py migrate
# Frontend
cd ../frontend && bun install
# Tutto in parallelo
cd .. && just up
```

- Backend admin: <http://localhost:8000/admin/> (`admin` / `admin`)
- Frontend: <http://localhost:9000/login>

# Utenti dev (creati al migrate)

| Username | Password | Ruolo |
|---|---|---|
| `admin` | `admin` | superuser |
| `sandro` / `bruna` / `fabio` | `<username>pwd` | proprietari |
| `mariasevera` / `davide` / `diana` / `arun` / `eshani` | `<username>pwd` | inquilini |

# Comandi just

`just backend` · `just frontend` · `just up` · `just migrate` · `just test` ·
`just lint` · `just build`.

# Email in dev (MailHog)

SMTP catcher Docker su `:1025` (SMTP) e `:8025` (UI), configurato in `local.py`.

# Vedi anche

- [Architecture overview](/architecture/overview.md), [Validazione](/playbooks/validazione.md).
