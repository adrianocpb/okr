import pytest
from django.contrib.auth import get_user_model

from apps.contas.models import Usuario


def test_modelo_de_usuario_e_o_customizado():
    assert get_user_model() is Usuario


@pytest.mark.django_db
def test_usuario_e_persistido_com_senha_protegida():
    Usuario.objects.create_user(username="teste", password="senha-ficticia-123")

    salvo = Usuario.objects.get(username="teste")
    assert salvo.password != "senha-ficticia-123"
    assert salvo.check_password("senha-ficticia-123")
