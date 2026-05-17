# Development settings — usato quando ENV=dev

DEBUG = True

ALLOWED_HOSTS = ['*']

# Iframe stessa-origine permessi (per l'anteprima PDF nel frontend via proxy)
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Frontend Quasar dev su :9000
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:9000',
    'http://127.0.0.1:9000',
    'http://localhost:9200',
    'http://127.0.0.1:9200',
]

# CORS per dev cross-origin (Quasar :9000 -> Django :8000)
CORS_ALLOWED_ORIGINS = [
    'http://localhost:9000',
    'http://127.0.0.1:9000',
    'http://localhost:9200',
    'http://127.0.0.1:9200',
]
CORS_ALLOW_CREDENTIALS = True

# Cookie session: SameSite=Lax in dev (stesso host localhost), no Secure
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
# CSRF cookie leggibile da JS per inviarlo con XSRF-TOKEN nelle richieste API
CSRF_COOKIE_HTTPONLY = False

# Admin tinto di rosso + badge "LOCALE": inconfondibile rispetto al remoto
ADMIN_TOOLS_THEMING_CSS = 'viapal/admin/dashboard-dev.css'
