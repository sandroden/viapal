"""Il link admin → app PWA è riservato ai superuser.

È l'unica scorciatoia che porta fuori dall'admin: se comparisse anche a
uno staff qualsiasi lo manderebbe su una SPA che non è autorizzato a
vedere. Il test blinda la condizione, non la grafica.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser("su_test", "su@v.it", "pwd123!")


@pytest.fixture
def staff(db):
    return User.objects.create_user(
        "staff_test", "staff@v.it", "pwd123!", is_staff=True
    )


def _index(user):
    client = Client()
    client.force_login(user)
    return client.get("/admin/")


def test_superuser_vede_il_link(superuser, settings):
    html = _index(superuser).content.decode()
    assert f"{settings.APP_BASE_URL.rstrip('/')}/p/" in html
    assert "App Viapal" in html


def test_staff_non_superuser_non_lo_vede(staff):
    html = _index(staff).content.decode()
    assert "App Viapal" not in html


def test_le_voci_standard_restano(superuser):
    """`block.super`: il link si aggiunge, non sostituisce la barra utente."""
    html = _index(superuser).content.decode()
    assert "/admin/password_change/" in html
    assert "logout-form" in html
