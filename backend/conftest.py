import os

os.environ.setdefault('ENV', 'dev')

import pytest  # noqa: E402


@pytest.fixture
def immobile(db):
    """L'immobile di riferimento dei test (multiproprietà, Fase A).

    Fixture centrale: i modelli di dominio sono property-scoped e ogni
    test che li crea deve attribuirli a un immobile.
    """
    from properties.models import Property

    return Property.objects.create(nome="Immobile Test", indirizzo="Via Test 1")


@pytest.fixture
def immobile2(db):
    """Un secondo immobile, per i test di isolamento cross-property."""
    from properties.models import Property

    return Property.objects.create(nome="Immobile Test 2", indirizzo="Via Test 2")
