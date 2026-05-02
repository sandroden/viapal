# syntax=docker/dockerfile:1
# Build context = repo root del monorepo (vedi docker-compose.yml).
# Tutti i COPY usano prefisso `frontend/`.

FROM oven/bun:1.2-alpine AS develop-stage
WORKDIR /app

COPY frontend/package.json frontend/bun.lockb ./
RUN bun add -g @quasar/cli

COPY frontend/ .

FROM develop-stage AS build-stage
RUN bun install --frozen-lockfile
RUN bun run build

FROM nginx:1.29.0-alpine AS production-stage
COPY --from=build-stage /app/dist/pwa /usr/share/nginx/html
COPY --from=build-stage /app/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
