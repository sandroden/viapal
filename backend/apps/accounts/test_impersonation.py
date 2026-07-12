"""Test per l'impersonation inquilini ("vedi come lui")."""
import pytest
from django.contrib.auth.models import Group, User

from accounts.impersonation import puo_impersonare


@pytest.fixture
def client():
    from rest_framework.test import APIClient
    return APIClient(enforce_csrf_checks=False)


@pytest.fixture
def gruppo_proprietari(db):
    grp, _ = Group.objects.get_or_create(name='proprietari')
    return grp


@pytest.fixture
def gruppo_inquilini(db):
    grp, _ = Group.objects.get_or_create(name='inquilini')
    return grp


@pytest.fixture
def proprietario(db, gruppo_proprietari):
    u = User.objects.create_user('test_prop', email='p@v.it', password='pwd123!')
    u.groups.add(gruppo_proprietari)
    return u


@pytest.fixture
def proprietario2(db, gruppo_proprietari):
    u = User.objects.create_user('test_prop2', email='p2@v.it', password='pwd123!')
    u.groups.add(gruppo_proprietari)
    return u


@pytest.fixture
def inquilino(db, gruppo_inquilini):
    u = User.objects.create_user('test_inq', email='i@v.it', password='pwd123!')
    u.groups.add(gruppo_inquilini)
    return u


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser('test_su', email='su@v.it', password='pwd123!')


@pytest.fixture
def tenant_profile(db, inquilino, immobile):
    from properties.models import TenantProfile
    return TenantProfile.objects.create(
        user=inquilino, property=immobile,
        nominativo='Inquilino Test', giorno_pagamento_affitto=1)


@pytest.fixture
def membership_proprietario(db, proprietario, immobile):
    """Membership del proprietario sull'immobile in cui affitta l'inquilino.

    Multiproprietà: senza questa membership il proprietario non può
    impersonare gli inquilini di quell'immobile.
    """
    from properties.models import PropertyMembership
    return PropertyMembership.objects.create(
        property=immobile, user=proprietario,
        ruolo=PropertyMembership.Ruolo.PROPRIETARIO)


# --- unit: gate puo_impersonare ------------------------------------------

def test_gate_proprietario_impersona_inquilino(
        proprietario, inquilino, tenant_profile, membership_proprietario):
    # il proprietario ha una membership sull'immobile dove l'inquilino affitta
    assert puo_impersonare(proprietario, inquilino) is True


def test_gate_proprietario_senza_membership_non_impersona(
        proprietario, inquilino, tenant_profile):
    # niente PropertyMembership sull'immobile dell'inquilino: negato
    assert puo_impersonare(proprietario, inquilino) is False


def test_gate_proprietario_membership_su_altro_immobile(
        proprietario, inquilino, tenant_profile, immobile2):
    # membership su un immobile DIVERSO da quello dell'inquilino: negato
    from properties.models import PropertyMembership
    PropertyMembership.objects.create(
        property=immobile2, user=proprietario,
        ruolo=PropertyMembership.Ruolo.PROPRIETARIO)
    assert puo_impersonare(proprietario, inquilino) is False


def test_gate_proprietario_non_impersona_altro_proprietario(proprietario, proprietario2):
    assert puo_impersonare(proprietario, proprietario2) is False


def test_gate_proprietario_non_impersona_superuser(proprietario, superuser):
    assert puo_impersonare(proprietario, superuser) is False


def test_gate_superuser_attore_impersona_inquilino(superuser, inquilino):
    # admin in locale e' superuser senza gruppo: deve poter impersonare.
    assert puo_impersonare(superuser, inquilino) is True


def test_gate_inquilino_non_impersona(inquilino, proprietario):
    # un inquilino non puo' impersonare nessuno, nemmeno un altro inquilino
    assert puo_impersonare(inquilino, proprietario) is False


def test_gate_self(proprietario):
    assert puo_impersonare(proprietario, proprietario) is False


# --- API: impersonate / stop ---------------------------------------------

def test_proprietario_impersona_inquilino(
        client, proprietario, tenant_profile, membership_proprietario):
    client.post('/api/auth/login/',
                {'username': 'test_prop', 'password': 'pwd123!'}, format='json')

    resp = client.post(f'/api/auth/impersonate/{tenant_profile.pk}/')
    assert resp.status_code == 200
    assert resp.json()['redirect'] == '/i/'

    me = client.get('/api/auth/user/').json()
    assert me['username'] == 'test_inq'
    assert me['role'] == 'inquilino'
    assert me['is_impersonated'] is True
    assert me['impersonator_username'] == 'test_prop'


def test_stop_ripristina_proprietario(
        client, proprietario, tenant_profile, membership_proprietario):
    client.post('/api/auth/login/',
                {'username': 'test_prop', 'password': 'pwd123!'}, format='json')
    client.post(f'/api/auth/impersonate/{tenant_profile.pk}/')

    resp = client.post('/api/auth/impersonate/stop/')
    assert resp.status_code == 200

    me = client.get('/api/auth/user/').json()
    assert me['username'] == 'test_prop'
    assert me['role'] == 'proprietario'
    assert me['is_impersonated'] is False
    assert me['impersonator_username'] is None


def test_proprietario_senza_membership_403(client, proprietario, tenant_profile):
    # multiproprietà: senza membership sull'immobile dell'inquilino → 403
    client.post('/api/auth/login/',
                {'username': 'test_prop', 'password': 'pwd123!'}, format='json')
    resp = client.post(f'/api/auth/impersonate/{tenant_profile.pk}/')
    assert resp.status_code == 403


def test_inquilino_non_puo_impersonare(client, inquilino, tenant_profile):
    client.post('/api/auth/login/',
                {'username': 'test_inq', 'password': 'pwd123!'}, format='json')
    resp = client.post(f'/api/auth/impersonate/{tenant_profile.pk}/')
    assert resp.status_code == 403


def test_stop_senza_impersonation_400(client, proprietario):
    client.post('/api/auth/login/',
                {'username': 'test_prop', 'password': 'pwd123!'}, format='json')
    resp = client.post('/api/auth/impersonate/stop/')
    assert resp.status_code == 400


def test_impersonate_richiede_auth(client, tenant_profile):
    resp = client.post(f'/api/auth/impersonate/{tenant_profile.pk}/')
    assert resp.status_code == 403
