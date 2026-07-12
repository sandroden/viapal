# Viapal — la casa, in tasca

Gestionale (PWA) per l'affitto a stanze di un appartamento di 180 m² in Via Palestrina (Monza).
Vedi [`PLAN.md`](PLAN.md) per il quadro completo del progetto.

## Struttura monorepo

```
viapal/
├── PLAN.md                    # Piano di progetto consolidato
├── README.md                  # questo file
├── design/                    # Bundle Claude Design (tokens.css, logo, prototipi)
├── backend/                   # Django 6 + DRF + dj-rest-auth (uv)
├── frontend/                  # Quasar 2 PWA (Vue 3 TS, Pinia, bun)
├── docker-compose.yml         # Stack di produzione (Traefik, Postgres, Redis)
├── justfile                   # Comandi locali (`just up`, `just test`)
├── .env.example               # Variabili d'ambiente di produzione
├── .github/workflows/         # CI (lint+test) + Build & Deploy GHCR
└── tests/screenshots/         # Screenshot di validazione (agent-browser)
```

## Prerequisiti dev

| Tool | Versione |
|---|---|
| `uv` | ≥ 0.8 |
| `bun` | ≥ 1.2 |
| `node` | ≥ 22.22 (richiesto da Quasar) |
| `just` | qualsiasi |
| `agent-browser` | per la validazione visuale |
| Postgres | cluster `dev` su porta `5434`, db `viapal`, utente `sandro` (peer auth via socket) |

In dev locale **non si usa Docker**: backend e frontend partono nativi.

## Avvio rapido

```bash
# 1. Backend: virtualenv + migrazioni
cd backend && uv sync
ENV=dev uv run python manage.py migrate
cd ..

# 2. Frontend: dipendenze
cd frontend && bun install
cd ..

# 3. Avvia tutto in parallelo
just up
```

- Backend Django:   <http://localhost:8000/admin/>  (admin: `admin` / `admin`)
- Frontend Quasar:  <http://localhost:9000/login>

### Utenti dev

Creati al `migrate` insieme ai gruppi `proprietari` e `inquilini`:

| Username | Password | Ruolo |
|---|---|---|
| `admin` | `admin` | superuser |
| `sandro` / `bruna` / `fabio` | `<username>pwd` | proprietari Via Palestrina (sandro anche gestore di Casa Lago) |
| `chiara` | `chiarapwd` | proprietaria Casa Lago (2ª property demo) |
| `mariasevera` / `davide` / `diana` / `arun` / `eshani` | `<username>pwd` | inquilini Via Palestrina |
| `luca_lago` | `lucalagopwd` | inquilino Casa Lago |

Il login frontend redirige automaticamente in base al gruppo:
proprietari → `/p/`, inquilini → `/i/`.

## Comandi `just`

```bash
just                      # mostra l'elenco
just backend              # solo Django dev (porta 8000)
just frontend             # solo Quasar dev (porta 9000)
just up                   # entrambi in parallelo
just migrate              # uv run manage.py migrate
just test                 # pytest backend
just lint                 # ruff + eslint
just build                # build immagini Docker (per test locali)
```

## Test e validazione

Per ogni feature lavoriamo a **due livelli** (vedi `PLAN.md` § 7 "Validazione obbligatoria"):

1. **Test pytest backend**:
   ```bash
   just test-backend
   ```
2. **Verifica funzionale via agent-browser** con screenshot in `tests/screenshots/<feature>/`:
   ```bash
   # Esempio: vedi gli screenshot del flow auth
   ls tests/screenshots/auth/
   ```

Gli screenshot sono il modo principale per vedere visualmente lo stato del lavoro.

## Auth

- **Session-based** Django + `dj-rest-auth` (no JWT).
- Endpoint principali: `POST /api/auth/login/`, `GET /api/auth/user/`, `POST /api/auth/logout/`, `GET /api/auth/csrf/`.
- Frontend Quasar: store Pinia in `src/stores/auth.ts`, guard router in `src/router/index.ts`.
- I gruppi `proprietari`/`inquilini` sono creati automaticamente al primo `migrate`.

## Produzione

- 2 immagini Docker (`viapal-backend`, `viapal-frontend`) costruite dal CI con build context = repo root.
- Reverse proxy: Traefik già configurato sul server Docker di Sandro. Dominio: `viapal.e-den.it` (TLS Let's Encrypt).
- Stack `docker-compose.yml`: `viapal-backend` + `viapal-frontend` + `postgres` + `redis`.
- Deploy via GitHub Actions su push a `main` (vedi `.github/workflows/build-and-deploy.yml`).

Variabili da settare nel `.env` di produzione (vedi `.env.example`):
`DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `DJANGO_ALLOWED_HOSTS`.

## Convenzioni

- Lingua: tutto in italiano (UI, copy, log, commit messages, descrizioni PR).
- Nomi modelli/classi Django: inglese (`OwnerProfile`, `RoomAssignment`).
- Nomi funzioni di dominio: italiano se più chiaro (`calcola_conguaglio_periodo`).
- Design system: `design/project/tokens.css` riportato 1:1 in `frontend/src/css/tokens.css`.
- Palette di brand applicata via `framework.config.brand` in `quasar.config.ts`.

## Stato

✅ **Fase 0 — Setup tecnico**: hello-world login funzionante, gruppi e ruoli, dev locale OK.

🚧 **Fase 1 — MVP funzionale**: vedi `PLAN.md` § 6.
