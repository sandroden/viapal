"""
Django base settings.

Settings comuni a tutti gli ambienti.
SECRET_KEY e DEBUG vanno definiti in dev.py/staging.py/production.py o local.py
"""

# Shim per django-admin-tools: reintroduce django.utils.itercompat (rimosso
# in Django 5.0). Va eseguito PRIMA che apps.populate() carichi admin_tools.
import core._dat_compat  # noqa: F401

import os

SETTINGS_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_DIR = os.path.dirname(SETTINGS_DIR)
BASE_DIR = os.path.dirname(PROJECT_DIR)


# Application definition

INSTALLED_APPS = [
    # django-admin-tools PRIMA di tutti gli admin (override admin/index.html etc).
    # NB: NON installare 'admin_tools.menu' e NON chiamare mai
    # admin_tools.dashboard.autodiscover() — quella funzione fa `import imp`
    # che non esiste piu' in Python 3.12+. Le classi dashboard sono dichiarate
    # esplicitamente via ADMIN_TOOLS_INDEX_DASHBOARD / ADMIN_TOOLS_APP_INDEX_DASHBOARD.
    'admin_tools',
    'admin_tools.theming',
    'admin_tools.dashboard',

    # jmb.filters PRIMA di contrib.admin (template loader)
    'jmb.filters',
    'jmb.jadmin',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Third-party
    'django_filters',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'allauth',
    'allauth.account',
    'dj_rest_auth',

    # Local apps
    'accounts',
    'properties',
    'billing',
    'accounting',
    'notifications',
]

SITE_ID = 1

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # core/templates: override di template di terze parti (es. oggetto
        # email allauth). Il filesystem.Loader gira prima dell'app_directories,
        # così questi hanno la precedenza a prescindere dall'ordine delle app.
        'DIRS': [os.path.join(PROJECT_DIR, 'templates')],
        # NB: con loader espliciti, NIENTE 'APP_DIRS': True (Django lo vieta).
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'loaders': [
                # Risolve 'filters:...' e 'admin:...' usati da jmb.jadmin/jmb.filters
                'jmb.filters.admin.templateloader.Loader',
                # Loader di django-admin-tools (per template di moduli dashboard customizzati)
                'admin_tools.template_loaders.Loader',
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database (Postgres dev cluster :5434, db 'viapal', user 'sandro' via socket)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'viapal',
        'USER': 'sandro',
        'HOST': '/var/run/postgresql',
        'PORT': '5434',
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'it-it'
TIME_ZONE = 'Europe/Rome'
USE_I18N = True
USE_TZ = True


STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATICFILES_DIRS = [
    # core non e' un'app Django: lo aggiungiamo qui per servire CSS custom (es. theming admin-tools)
    os.path.join(PROJECT_DIR, "static"),
]
MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# REST framework: solo session auth (PWA stessa origine in prod, dev via CORS)
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# Email: default console backend (in sviluppo le email finiscono a schermo,
# così si vede il testo senza inviare nulla). In produzione impostare via env:
#   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
#   EMAIL_HOST / EMAIL_PORT / EMAIL_HOST_USER / EMAIL_HOST_PASSWORD
#   EMAIL_USE_TLS=1 / DEFAULT_FROM_EMAIL="Viapal <...>"
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend'
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', '1') not in ('0', 'false', 'False', '')
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL', 'Viapal <noreply@viapal.e-den.it>'
)

# URL base della PWA, usato per i link cliccabili nelle email agli inquilini.
# In dev viene sovrascritto in local.py/dev.py con http://localhost:9000.
APP_BASE_URL = os.environ.get('APP_BASE_URL', 'https://viapal.e-den.it')

# allauth: login con username OPPURE email (l'inquilino invitato vede entrambi
# nell'email di invito). Richiede email univoche — verificato che non ce ne
# siano di duplicate fra gli utenti esistenti. No verifica email in dev.
ACCOUNT_EMAIL_VERIFICATION = 'none'
# Oggetto delle email allauth: sostituisce il prefisso di default "[<site>] "
# (che mostrava "[example.com]"). L'oggetto base è in core/templates/account/.
ACCOUNT_EMAIL_SUBJECT_PREFIX = 'Viapal — '
ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_SIGNUP_FIELDS = ['username*', 'email*', 'password1*', 'password2*']
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# dj-rest-auth: session-based, no JWT.
# - PASSWORD_RESET_SERIALIZER: brandizza il link di reset/invito facendolo
#   puntare alla SPA (vedi accounts.serializers.SpaPasswordResetSerializer).
# - OLD_PASSWORD_FIELD_ENABLED: il cambio password da loggato richiede la
#   vecchia password (default dj-rest-auth è False).
REST_AUTH = {
    'USE_JWT': False,
    'SESSION_LOGIN': True,
    'TOKEN_MODEL': None,
    'USER_DETAILS_SERIALIZER': 'accounts.serializers.UserSerializer',
    'PASSWORD_RESET_SERIALIZER': 'accounts.serializers.SpaPasswordResetSerializer',
    'OLD_PASSWORD_FIELD_ENABLED': True,
}

# Ruoli applicativi (gruppi Django)
ROLE_PROPRIETARI = 'proprietari'
ROLE_INQUILINI = 'inquilini'


# django-admin-tools: classi dashboard dichiarate esplicitamente per evitare
# l'autodiscover() che usa il modulo `imp` (rimosso in Python 3.12+).
ADMIN_TOOLS_INDEX_DASHBOARD = 'core.dashboard.ViapalIndexDashboard'
ADMIN_TOOLS_APP_INDEX_DASHBOARD = 'core.dashboard.ViapalAppIndexDashboard'

# Ambiente corrente (dev/staging/production), derivato da $ENV.
# Usato per differenziare visivamente admin e frontend ed evitare di
# operare su produzione pensando di essere in locale.
ENVIRONMENT = os.environ.get('ENV') or 'dev'

# CSS theming admin: di default quello "pulito" (produzione).
# dev.py / staging.py lo sovrascrivono con una variante colorata.
ADMIN_TOOLS_THEMING_CSS = 'viapal/admin/dashboard.css'
