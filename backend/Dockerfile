# syntax = docker/dockerfile:1
# Build context = repo root del monorepo (vedi docker-compose.yml).
# Tutti i COPY usano prefisso `backend/`.
FROM thuxit/upython:3.13-18-uv-bookworm AS production-stage
ARG APP_USER=www-data

WORKDIR /code/

COPY backend/pyproject.toml backend/uv.lock /code/
ENV UV_SYSTEM_PYTHON=1
ENV UV_PROJECT_ENVIRONMENT=/usr/local
RUN uv sync --inexact

COPY backend/ /code/

EXPOSE 8000

ENV DJANGO_SETTINGS_MODULE=core.settings
ENV ENV=production

RUN python /code/manage.py check \
  && python /code/manage.py collectstatic --noinput --link \
  && mkdir -p /code/media \
  && chown -R ${APP_USER} /code/core/settings /code/media /code/static \
  && mv uwsgi.ini /etc

USER ${APP_USER}:${APP_USER}

CMD ["uwsgi", "--ini=/etc/uwsgi.ini", "--show-config"]
