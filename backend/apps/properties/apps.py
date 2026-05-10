from django.apps import AppConfig


class PropertiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "properties"
    verbose_name = "Immobile e occupazione"

    def ready(self):
        from . import signals  # noqa: F401
