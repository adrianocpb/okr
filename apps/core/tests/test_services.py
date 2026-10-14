from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.auditoria.models import RegistroAlteracao
from apps.auditoria.services import historico_do_objeto
from apps.core import services
from apps.core.acesso import Ator
from apps.core.erros import ConflitoDeVersao, ErroDeNegocio
from apps.core.tests.app_teste.models import ItemTeste

pytestmark = pytest.mark.django_db

ATOR = Ator.local()


def criar_item(**campos):
    dados = {"nome": "Item A", "valor": Decimal("10.00"), "empresa_id": 7, **campos}
    return services.criar(ItemTeste(**dados), ator=ATOR)


def test_criar_registra_auditoria_com_valores_iniciais():
    item = criar_item()

    registro = historico_do_objeto(item).get()
    assert registro.acao == RegistroAlteracao.Acao.CRIACAO
    assert registro.empresa_id == 7
    assert registro.alteracoes["nome"] == {"antes": None, "depois": "Item A"}
    assert registro.alteracoes["valor"] == {"antes": None, "depois": "10.00"}
    assert registro.ator_descricao == "Usuário local (não autenticado)"
    assert registro.usuario is None


def test_criar_valida_o_modelo_antes_de_gravar():
    with pytest.raises(ValidationError):
        criar_item(valor=Decimal("-1"))

    assert not ItemTeste.objects.exists()
    assert not RegistroAlteracao.objects.exists()


def test_atualizar_registra_antes_e_depois_e_incrementa_versao():
    item = criar_item()

    item = services.atualizar(
        item, {"nome": "Item B", "valor": Decimal("12.50")}, versao_esperada=1, ator=ATOR
    )

    assert item.versao == 2
    registro = historico_do_objeto(item).filter(acao=RegistroAlteracao.Acao.ALTERACAO).get()
    assert registro.alteracoes == {
        "nome": {"antes": "Item A", "depois": "Item B"},
        "valor": {"antes": "10.00", "depois": "12.50"},
    }


def test_atualizar_sem_mudancas_nao_grava_nem_audita():
    item = criar_item()

    item = services.atualizar(item, {"valor": Decimal("10.0")}, versao_esperada=1, ator=ATOR)

    assert item.versao == 1
    assert historico_do_objeto(item).count() == 1  # só a criação


def test_atualizar_com_versao_desatualizada_e_recusado_sem_sobrescrever():
    item = criar_item()
    copia_da_pessoa_a = ItemTeste.objects.get(pk=item.pk)
    copia_da_pessoa_b = ItemTeste.objects.get(pk=item.pk)

    services.atualizar(copia_da_pessoa_a, {"nome": "Versão A"}, versao_esperada=1, ator=ATOR)
    with pytest.raises(ConflitoDeVersao):
        services.atualizar(copia_da_pessoa_b, {"nome": "Versão B"}, versao_esperada=1, ator=ATOR)

    salvo = ItemTeste.objects.get(pk=item.pk)
    assert salvo.nome == "Versão A"
    assert salvo.versao == 2
    assert historico_do_objeto(item).filter(acao=RegistroAlteracao.Acao.ALTERACAO).count() == 1


def test_falha_na_auditoria_reverte_a_alteracao(monkeypatch):
    item = criar_item()

    def auditoria_com_falha(**kwargs):
        raise RuntimeError("falha simulada ao gravar auditoria")

    monkeypatch.setattr(services, "registrar_alteracao", auditoria_com_falha)
    with pytest.raises(RuntimeError):
        services.atualizar(item, {"nome": "Não deve ficar"}, versao_esperada=1, ator=ATOR)

    salvo = ItemTeste.objects.get(pk=item.pk)
    assert salvo.nome == "Item A"
    assert salvo.versao == 1


def test_falha_na_auditoria_reverte_a_criacao(monkeypatch):
    def auditoria_com_falha(**kwargs):
        raise RuntimeError("falha simulada ao gravar auditoria")

    monkeypatch.setattr(services, "registrar_alteracao", auditoria_com_falha)
    with pytest.raises(RuntimeError):
        criar_item()

    assert not ItemTeste.objects.exists()


def test_atualizar_invalido_nao_grava():
    item = criar_item()

    with pytest.raises(ValidationError):
        services.atualizar(item, {"valor": Decimal("-5")}, versao_esperada=1, ator=ATOR)

    salvo = ItemTeste.objects.get(pk=item.pk)
    assert salvo.valor == Decimal("10.00")
    assert salvo.versao == 1


def test_arquivar_e_reativar_preservam_registro_e_auditam():
    item = criar_item()

    item = services.arquivar(item, versao_esperada=1, ator=ATOR)
    assert item.arquivado
    assert item.versao == 2

    item = services.reativar(item, versao_esperada=2, ator=ATOR)
    assert not item.arquivado
    assert item.versao == 3

    acoes = list(historico_do_objeto(item).order_by("id").values_list("acao", flat=True))
    assert acoes == ["criacao", "arquivamento", "reativacao"]


def test_arquivar_registro_ja_arquivado_e_recusado():
    item = services.arquivar(criar_item(), versao_esperada=1, ator=ATOR)

    with pytest.raises(ErroDeNegocio):
        services.arquivar(item, versao_esperada=2, ator=ATOR)


def test_arquivar_com_versao_desatualizada_e_recusado():
    item = criar_item()
    services.atualizar(
        ItemTeste.objects.get(pk=item.pk), {"nome": "X"}, versao_esperada=1, ator=ATOR
    )

    with pytest.raises(ConflitoDeVersao):
        services.arquivar(item, versao_esperada=1, ator=ATOR)

    assert not ItemTeste.objects.get(pk=item.pk).arquivado
