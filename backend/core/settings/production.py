# utf-8
"""Production settings — usato quando ENV=production.

Valori sensibili da env vars (DJANGO_*) o da local.py iniettato dal container.
"""
import os

DEBUG = False

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'viapal.e-den.it').split(',')

CSRF_TRUSTED_ORIGINS = [
    f"https://{h.strip()}" for h in ALLOWED_HOSTS if h.strip()
]

# Stessa-origine in produzione (Traefik routing): no CORS necessario
CORS_ALLOWED_ORIGINS = []
CORS_ALLOW_CREDENTIALS = True

# Cookie session sicuri
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # frontend deve leggerlo per X-CSRFToken

# Hardening
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Database via env (DATABASE_URL non parsata: usiamo singoli campi)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'viapal'),
        'USER': os.environ.get('POSTGRES_USER', 'viapal'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
        'HOST': os.environ.get('POSTGRES_HOST', 'postgres'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}
