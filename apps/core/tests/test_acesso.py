from decimal import Decimal

import pytest

from apps.core.acesso import Ator, EscopoAcesso
from apps.core.tests.app_teste.models import ItemTeste


def test_ator_local_nao_e_verificado():
    assert Ator.local().verificado is False


def test_ator_com_usuario_e_verificado():
    assert Ator(descricao="Fulano", usuario_id=1).verificado is True


def test_escopo_todas_permite_qualquer_empresa():
    escopo = EscopoAcesso.todas()

    assert escopo.permite(1)
    assert escopo.permite(999)


def test_escopo_restrito_permite_apenas_as_empresas_listadas():
    escopo = EscopoAcesso.restrito([1, 2])

    assert escopo.permite(1)
    assert not escopo.permite(3)
    assert not escopo.permite(None)


@pytest.mark.django_db
def test_escopo_restrito_filtra_registros_de_outras_empresas():
    ItemTeste.objects.create(nome="da empresa A", valor=Decimal(1), empresa_id=1)
    ItemTeste.objects.create(nome="da empresa B", valor=Decimal(1), empresa_id=2)

    visiveis = EscopoAcesso.restrito([1]).filtrar(ItemTeste.objects.all())

    assert list(visiveis.values_list("nome", flat=True)) == ["da empresa A"]


@pytest.mark.django_db
def test_escopo_todas_nao_filtra():
    ItemTeste.objects.create(nome="A", valor=Decimal(1), empresa_id=1)
    ItemTeste.objects.create(nome="B", valor=Decimal(1), empresa_id=2)

    assert EscopoAcesso.todas().filtrar(ItemTeste.objects.all()).count() == 2
