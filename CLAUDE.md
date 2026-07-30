# Viapal — istruzioni progetto

## Porte dev dedicate

Per evitare conflitti di porta con altri progetti attivi in parallelo, questo
progetto usa porte dedicate (NON i default 8000/9000):

- **Django (backend): 8020** — `just backend` fa `runserver 0.0.0.0:8020`
- **Quasar (frontend): 9020** — `devServer.port` in `frontend/quasar.config.ts`

Il proxy del dev server Quasar (`/api`, `/admin`, `/static`, `/media`) punta a
`http://localhost:8020`. Anche CSRF/CORS in `backend/core/settings/dev.py` e
`APP_BASE_URL` in `local.py` usano :9020.

Quando avvii server di sviluppo o fai validazioni con agent-browser, usa
sempre queste porte: frontend <http://localhost:9020/>, admin
<http://localhost:8020/admin/>.
