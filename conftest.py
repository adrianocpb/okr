"""Fixtures comuns a toda a suíte.

Todas as telas exigem login. O fixture `client` padrão do pytest-django é
substituído por um cliente já autenticado como Administrador, para que os testes
de tela continuem focados nas regras de cada módulo. Para testar o acesso sem
login, use `cliente_anonimo`.
"""

import pytest
from django.test import Client


@pytest.fixture
def usuario_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        username="admin@exemplo.com",
        email="admin@exemplo.com",
        password="senha-ficticia-123",
        first_name="Admin",
        last_name="Teste",
        is_staff=True,
    )


@pytest.fixture
def cliente_anonimo():
    return Client()


@pytest.fixture
def client(usuario_admin):
    cliente = Client()
    cliente.force_login(usuario_admin)
    return cliente
