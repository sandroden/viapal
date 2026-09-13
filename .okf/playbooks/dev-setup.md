---
type: Playbook
title: Dev setup
description: Avviare backend e frontend in locale (senza Docker).
resource: justfile
resources:
  - justfile
  - backend/core/settings/dev.py
  - frontend/quasar.config.ts
  - backend/apps/properties/management/commands/seed_demo.py
tags: [playbook, dev, setup]
generated:
  by: process:okf-migrate
  at: 2026-09-13T00:00:00Z
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
# Dati e utenti demo (il migrate crea solo i gruppi)
ENV=dev uv run python manage.py seed_demo   # --reset azzera le app di dominio
# Frontend
cd ../frontend && bun install
# Tutto in parallelo
cd .. && just up
```

- Backend admin: <http://localhost:8020/admin/> (`admin` / `admin`)
- Frontend: <http://localhost:9020/login> (host alternativi in
  `quasar.config.ts: allowedHosts` + `settings/dev.py: _ORIGINI_DEV`:
  `viapal.local:9020` e `viapal.localhost:9020`)
  - Per le **notifiche push** serve un contesto sicuro: usare
    `viapal.localhost` (o `localhost` nudo), mai `viapal.local`, che essendo
    http su nome non speciale spegne `serviceWorker`/`PushManager`.
  - `viapal.localhost` va messo in `/etc/hosts` puntato a `127.0.0.1`: il
    resolver di sistema lo risolve a `::1`, ma i dev server ascoltano su IPv4.
- I superuser hanno i link "→ App Viapal" (admin) e "Admin Django" (drawer
  proprietario); il primo passa da `APP_BASE_URL`, perché in dev le due
  porte sono diverse.

# Porte e worktree paralleli

- `VIAPAL_BACKEND_PORT` sposta il target del proxy Quasar (default 8020),
  `VIAPAL_FRONTEND_PORT` aggiunge un'origine CSRF/CORS fidata (default
  9020, anche 9200): un secondo worktree parte senza toccare i file.
- `VIAPAL_DB_NAME` sceglie un database (e quindi un test DB) distinto per
  pytest in parallelo.
- Il dev server Quasar proxa `/api`, `/admin`, `/static`, `/media-private`,
  `/media` e `/g/` verso Django.

# Utenti dev (creati da `seed_demo`, non dal migrate)

| Username | Password | Ruolo |
|---|---|---|
| `admin` | `admin` | superuser |
| `sandro` / `bruna` / `fabio` | `<username>pwd` | proprietari |
| `mariasevera` / `davide` / `diana` / `arun` / `eshani` | `<username>pwd` | inquilini |

# Comandi just

`just backend` · `just frontend` · `just up` · `just migrate` · `just test` ·
`just lint` · `just build`.

# Email in dev (MailHog)

SMTP catcher Docker su `:1025` (SMTP) e `:8025` (UI), configurato in `local.py`;
`just mailhog` / `just mailhog-stop` lo avviano e fermano (container
`viapal-mailhog`, auth-file in `~/.config/mailhog/auth.txt`).

# Media di produzione in locale

`jmb.core` `FallbackStorage`, configurato in `local.py` (`MEDIA_FALLBACK_S3_*`):
legge prima dal filesystem locale e, se il file manca, dal proxy S3 read-only
di prod. Spento sotto pytest. Non richiede di copiare la `media/`.

# Vedi anche

- [Architecture overview](/architecture/overview.md), [Validazione](/playbooks/validazione.md).
