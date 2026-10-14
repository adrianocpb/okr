from datetime import date
from decimal import Decimal

import pytest

from apps.auditoria.models import RegistroAlteracao, RegistroImutavel
from apps.auditoria.services import registrar_alteracao, valor_auditavel
from apps.contas.models import Usuario
from apps.core.acesso import Ator

pytestmark = pytest.mark.django_db


@pytest.fixture
def registro():
    objeto = Usuario.objects.create_user(username="objeto-auditado", password="x-ficticia-123")
    return registrar_alteracao(
        objeto=objeto,
        acao=RegistroAlteracao.Acao.ALTERACAO,
        ator=Ator.local(),
        alteracoes={"first_name": {"antes": "", "depois": "Fulano"}},
    )


def test_registro_nao_pode_ser_alterado(registro):
    registro.ator_descricao = "outra pessoa"

    with pytest.raises(RegistroImutavel):
        registro.save()


def test_registro_nao_pode_ser_excluido(registro):
    with pytest.raises(RegistroImutavel):
        registro.delete()


def test_registros_nao_podem_ser_alterados_ou_excluidos_em_massa(registro):
    with pytest.raises(RegistroImutavel):
        RegistroAlteracao.objects.all().update(ator_descricao="x")
    with pytest.raises(RegistroImutavel):
        RegistroAlteracao.objects.all().delete()

    assert RegistroAlteracao.objects.get(pk=registro.pk).ator_descricao == registro.ator_descricao


def test_registro_guarda_autor_nao_verificado_sem_login(registro):
    assert registro.usuario_id is None
    assert registro.origem == "interface"
    assert "não autenticado" in registro.ator_descricao


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (Decimal("1234.50"), "1234.50"),
        (date(2026, 10, 14), "2026-10-14"),
        (None, None),
        ("texto", "texto"),
    ],
)
def test_valor_auditavel_preserva_valores(valor, esperado):
    assert valor_auditavel(valor) == esperado
