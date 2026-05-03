"""Shim per django-admin-tools su Django >= 5.0.

DAT 0.9.x importa `django.utils.itercompat.is_iterable`, modulo rimosso in
Django 5.0. Reintroduciamo lo stub minimo in sys.modules in modo che l'import
non fallisca all'avvio di INSTALLED_APPS.

Tutti gli altri import di simboli vecchi (ugettext_lazy, force_text, importlib)
sono gia' protetti da try/except dentro DAT, quindi non serve toccarli.
"""
import sys
import types


def _install_itercompat_shim() -> None:
    if "django.utils.itercompat" in sys.modules:
        return

    mod = types.ModuleType("django.utils.itercompat")

    def is_iterable(x):
        try:
            iter(x)
        except TypeError:
            return False
        return True

    mod.is_iterable = is_iterable
    sys.modules["django.utils.itercompat"] = mod


_install_itercompat_shim()
