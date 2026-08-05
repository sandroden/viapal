"""Context processor di progetto."""
from django.conf import settings


def app_frontend(request):
    """Espone l'URL dell'app PWA ai template (admin compreso).

    In produzione admin e frontend stanno sullo stesso dominio, in sviluppo
    no (Django :8020, Quasar :9020): un link relativo `/p/` dall'admin
    finirebbe su Django, che la SPA non la serve. Passiamo quindi sempre
    da ``APP_BASE_URL``, che ogni ambiente valorizza per sé.
    """
    return {"app_frontend_url": f"{settings.APP_BASE_URL.rstrip('/')}/p/"}
