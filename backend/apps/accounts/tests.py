"""Test smoke per auth backend.

Coprono il flusso login -> /api/auth/user/ -> logout via session cookie
e verificano che il campo `role` venga calcolato dai gruppi Django.
"""
import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient


@pytest.fixture
def client():
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
def inquilino(db, gruppo_inquilini):
    u = User.objects.create_user('test_inq', email='i@v.it', password='pwd123!')
    u.groups.add(gruppo_inquilini)
    return u


def test_csrf_endpoint_set_cookie(client):
    resp = client.get('/api/auth/csrf/')
    assert resp.status_code == 200
    assert 'csrftoken' in resp.cookies


def test_login_proprietario_e_user_endpoint(client, proprietario):
    resp = client.post('/api/auth/login/',
                       {'username': 'test_prop', 'password': 'pwd123!'},
                       format='json')
    assert resp.status_code in (200, 204)

    me = client.get('/api/auth/user/')
    assert me.status_code == 200
    data = me.json()
    assert data['username'] == 'test_prop'
    assert data['role'] == 'proprietario'


def test_login_inquilino_role(client, inquilino):
    client.post('/api/auth/login/',
                {'username': 'test_inq', 'password': 'pwd123!'},
                format='json')
    me = client.get('/api/auth/user/')
    assert me.status_code == 200
    assert me.json()['role'] == 'inquilino'


def test_user_endpoint_richiede_auth(client):
    resp = client.get('/api/auth/user/')
    assert resp.status_code == 403


def test_logout_invalida_sessione(client, proprietario):
    client.post('/api/auth/login/',
                {'username': 'test_prop', 'password': 'pwd123!'},
                format='json')
    assert client.get('/api/auth/user/').status_code == 200
    client.post('/api/auth/logout/')
    assert client.get('/api/auth/user/').status_code == 403


def test_login_credenziali_invalide(client, proprietario):
    resp = client.post('/api/auth/login/',
                       {'username': 'test_prop', 'password': 'wrong'},
                       format='json')
    assert resp.status_code == 400


def test_gruppi_creati_al_post_migrate(db):
    assert Group.objects.filter(name='proprietari').exists()
    assert Group.objects.filter(name='inquilini').exists()
