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

# Media pubblici vs privati

- `/media/` — SOLO contenuti pubblici (galleria annuncio, foto stanze):
  statici (uwsgi `static-map = /media/=/code/media/`, trailing slash
  obbligatorio; dev: `static()` in `core/urls.py`).
- `/media-private/` — file riservati (documenti identità `documenti/`,
  `documenti-proprieta/`, `bollette/`, `ricevute/`, `spese/`): storage
  dedicato `MEDIA_PRIVATE_ROOT` (`core/storages.py`) servito SEMPRE dalla
  vista autenticata `core/media_private.py`, che autorizza cercando il
  record proprietario del file (inquilino interessato / membri della
  property; log su logger `viapal.media_private`). Test:
  `apps/properties/test_media_private.py`. Migrazione file:
  `manage.py migra_media_private`.
- Adempimenti GDPR e documenti da far firmare: `docs/privacy/PIANO-GDPR.md`.

## Media di produzione visibili in dev (proxy S3)

- In prod il servizio `s3` (`andrewgaul/s3proxy`, `docker-compose.yml`) espone
  `data/media` e `data/media-private` come bucket S3 **read-only** su
  `s3.viapal.e-den.it` (chiavi `S3_*` nel `.env` del server).
- In dev `local.py` monta `jmb.core.files.storage.FallbackStorage` su
  `STORAGES["default"]` e `["private"]`: primario = filesystem locale,
  fallback = S3 di prod. Le scritture restano locali; le `delete` creano
  whiteout `.wh.*`. Nei test il blocco è disattivato (guardia su `pytest`).
- **Trappola**: il provider filesystem di jclouds deriva l'ACL *anonima* dai
  bit POSIX — un file/directory leggibile da "others" è servito SENZA firma.
  Perciò: `chmod -R o-rwx` sui dati montati e `FILE_UPLOAD_PERMISSIONS =
  0o640` / `FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750` in `base.py`.

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
