# Demo settings — usato quando ENV=demo (`just demo`)
#
# Ambiente per riprese e presentazioni: DB `viapal_demo` (copia anonimizzata
# della produzione, vedi il comando `anonimizza_demo`) e media in cartelle
# proprie. A differenza di dev, local.py NON viene letto (vedi __init__.py):
# niente FallbackStorage verso il proxy S3 di produzione, che altrimenti
# servirebbe i documenti veri degli inquilini dietro ai nomi finti.
import os

exec(compile(open(os.path.join(SETTINGS_DIR, 'dev.py'), encoding='utf-8').read(),  # noqa: F821
             os.path.join(SETTINGS_DIR, 'dev.py'), 'exec'), globals())

DEMO = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'viapal_demo',
        'USER': 'sandro',
        'HOST': '/var/run/postgresql',
        'PORT': '5434',
    }
}

SECRET_KEY = 'demo-non-segreta-solo-per-le-riprese-locali'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media-demo')  # noqa: F821
MEDIA_PRIVATE_ROOT = os.path.join(BASE_DIR, 'media-private-demo')  # noqa: F821

# Porte demo: backend 8022, frontend 9022 (dev resta su 8020/9020)
_PORTE_FRONTEND.append('9022')  # noqa: F821
_ORIGINI_DEMO = [f'http://{host}:9022' for host in ('localhost', '127.0.0.1')]
CSRF_TRUSTED_ORIGINS = CSRF_TRUSTED_ORIGINS + _ORIGINI_DEMO  # noqa: F821
CORS_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS + _ORIGINI_DEMO  # noqa: F821
# Link nelle email: nel video si vedono, niente localhost
APP_BASE_URL = 'https://viapal.e-den.it'
SPA_INDEX_URL = 'http://localhost:9022/'

# Le email non escono: finiscono sulla console del runserver
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'Viapal <noreply@viapal.local>'
