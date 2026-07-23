# Viapal — comandi locali
# Esegui `just` per la lista, `just <target>` per eseguire.

set shell := ["bash", "-cu"]

# default: mostra help
default:
    @just --list

# === Backend ===

# Avvia il backend Django in dev (Postgres dev :5434, db viapal)
backend:
    cd backend && ENV=dev uv run python manage.py runserver 0.0.0.0:8000

# Esegui le migrazioni
migrate:
    cd backend && ENV=dev uv run python manage.py migrate

# Crea/aggiorna le migrazioni
makemigrations *args="":
    cd backend && ENV=dev uv run python manage.py makemigrations {{args}}

# Apri shell Django
shell:
    cd backend && ENV=dev uv run python manage.py shell

# Test backend (pytest)
test-backend *args="":
    cd backend && ENV=dev uv run pytest {{args}}

# Lint backend (ruff)
lint-backend:
    cd backend && uv run ruff check .

# === Frontend ===
# NB: Quasar @quasar/app-vite richiede Node >= 22.22; lo selezioniamo via nvm
# (lo script .nvmrc in frontend/ fissa la versione)

# Avvia Quasar dev server (proxy verso backend :8000)
frontend:
    #!/usr/bin/env bash
    set -euo pipefail
    source ~/.nvm/nvm.sh
    cd frontend && nvm use > /dev/null && bun run dev

# Build PWA produzione
build-frontend:
    #!/usr/bin/env bash
    set -euo pipefail
    source ~/.nvm/nvm.sh
    cd frontend && nvm use > /dev/null && bun run build

# Lint frontend
lint-frontend:
    #!/usr/bin/env bash
    set -euo pipefail
    source ~/.nvm/nvm.sh
    cd frontend && nvm use > /dev/null && bun run lint

# Type-check frontend
type-check:
    #!/usr/bin/env bash
    set -euo pipefail
    source ~/.nvm/nvm.sh
    cd frontend && nvm use > /dev/null && bunx vue-tsc --noEmit

# Install dipendenze frontend
install-frontend:
    #!/usr/bin/env bash
    set -euo pipefail
    source ~/.nvm/nvm.sh
    cd frontend && nvm use > /dev/null && bun install

# === MailHog (SMTP catcher per email in dev) ===
# UI web: http://localhost:8025 (login sandro/vicie) — SMTP su :1025 (vedi local.py)

# Avvia MailHog (crea il container se non esiste, altrimenti lo riavvia)
mailhog:
    #!/usr/bin/env bash
    set -euo pipefail
    if docker ps -a --format '{{ '{{' }}.Names{{ '}}' }}' | grep -qx viapal-mailhog; then
        docker start viapal-mailhog
    else
        docker run -d --name viapal-mailhog -p 1025:1025 -p 8025:8025 \
            -v ~/.config/mailhog/auth.txt:/tmp/auth.txt:ro mailhog/mailhog \
            -auth-file=/tmp/auth.txt
    fi
    echo "MailHog attivo: UI http://localhost:8025 (sandro/vicie), SMTP :1025"

# Ferma MailHog
mailhog-stop:
    docker stop viapal-mailhog

# === Stack completo ===

# Avvia backend + frontend in parallelo (Ctrl-C per fermare entrambi)
up:
    #!/usr/bin/env bash
    set -euo pipefail
    just backend & B=$!
    just frontend & F=$!
    trap "kill $B $F 2>/dev/null || true" EXIT INT TERM
    wait

# Lint completo
lint: lint-backend lint-frontend

# Test completo
test: test-backend

# === Docker / produzione (no docker in dev) ===

# Build immagini Docker locali (build context = repo root)
build:
    docker build -f backend/Dockerfile -t viapal-backend:local .
    docker build -f frontend/Dockerfile -t viapal-frontend:local .

# Avvia stack docker-compose locale
up-docker:
    docker compose up --build

# Stop stack docker
down-docker:
    docker compose down

# === Deploy (placeholder; il vero deploy va via GitHub Actions) ===

# Deploy: push immagini e ricarica server (TBD)
deploy:
    @echo "Deploy via GitHub Actions: push su main triggera workflow"
