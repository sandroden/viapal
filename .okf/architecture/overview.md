---
type: Architecture
title: Architecture overview
description: Stack, monorepo, deploy e convenzioni del progetto Viapal.
resource: https://github.com/sandroden/viapal
tags: [architecture, stack, deploy]
timestamp: 2026-07-08T00:00:00Z
---

# Overview

Viapal è un gestionale PWA per l'affitto a stanze di un appartamento di ~180 m²
in Via Palestrina (Monza), di proprietà di tre fratelli e affittato a più
inquilini. Serve due tipi di utente: **proprietari** (`/p/`) e **inquilini** (`/i/`).

# Stack

| Livello | Tecnologia |
|---------|------------|
| Backend | Django 6 + DRF + dj-rest-auth (gestito con `uv`) |
| Frontend | Quasar 2, Vue 3 + TypeScript, Pinia (gestito con `bun`) |
| DB | Postgres (dev: cluster locale porta 5434; prod: container) |
| Cache/queue | Redis |
| Reverse proxy | Traefik (dominio `viapal.e-den.it`, TLS Let's Encrypt) |

# Monorepo

- `backend/` — Django. App in `backend/apps/`: `accounts`, `properties`,
  `billing`, `accounting`, `notifications`.
- `frontend/` — Quasar PWA. Pagine in `src/pages/`, store Pinia in `src/stores/`.
- `design/` — design system (`tokens.css`, logo, prototipi).
- `docker-compose.yml`, `justfile`, `.github/workflows/` — infra e CI/CD.

# Deploy

- CI GitHub Actions su push a `main`: build di 2 immagini Docker
  (`viapal-backend`, `viapal-frontend`) con build context = repo root, push su GHCR.
- Stack di produzione via `docker-compose.yml` (backend + frontend + postgres + redis).
- In dev locale **non si usa Docker**: backend e frontend partono nativi (`just up`).

# Convenzioni

- Lingua: tutto l'UI/copy/log/commit in **italiano**.
- Nomi modelli/classi Django in inglese (`OwnerProfile`, `RoomAssignment`);
  funzioni di dominio in italiano quando più chiaro (`calcola_conguaglio_periodo`).
- Design tokens: `design/project/tokens.css` riportato 1:1 in `frontend/src/css/tokens.css`.

# Vedi anche

- [Modello dati](/architecture/modello-dati.md)
- [Auth e ruoli](/architecture/auth-e-ruoli.md)
- [PWA](/architecture/pwa.md)
- [Playbook dev setup](/playbooks/dev-setup.md)
