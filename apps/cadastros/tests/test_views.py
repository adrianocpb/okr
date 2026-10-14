import pytest
from django.test import Client
from django.urls import reverse

from apps.cadastros.models import Empresa, Pessoa
from apps.cadastros.tests import fabricas

pytestmark = pytest.mark.django_db


def html(resposta):
    return resposta.content.decode()


# ---------------------------------------------------------------- empresas


def test_lista_de_empresas_vazia_orienta_o_primeiro_cadastro(client):
    resposta = client.get(reverse("cadastros:empresa_lista"))

    assert resposta.status_code == 200
    assert "Cadastre a primeira empresa" in html(resposta)


def test_cadastrar_empresa_pela_tela(client):
    resposta = client.post(
        reverse("cadastros:empresa_nova"), {"nome": "Empresa Alfa", "sigla": "alf"}, follow=True
    )

    empresa = Empresa.objects.get()
    assert empresa.sigla == "ALF"
    assert resposta.redirect_chain[-1][0] == reverse("cadastros:empresa_detalhe", args=[empresa.pk])
    assert "Empresa ALF cadastrada." in html(resposta)
    assert "Criação" in html(resposta)  # histórico exibido no detalhe


def test_cadastro_de_empresa_duplicada_mostra_erro_no_campo(client):
    fabricas.empresa(nome="Empresa Alfa", sigla="ALF")

    resposta = client.post(
        reverse("cadastros:empresa_nova"), {"nome": "empresa alfa", "sigla": "OUT"}
    )

    assert resposta.status_code == 200
    assert "Já existe uma empresa com este nome." in html(resposta)
    assert Empresa.objects.count() == 1


def test_campos_obrigatorios_em_portugues(client):
    resposta = client.post(reverse("cadastros:empresa_nova"), {"nome": "", "sigla": ""})

    assert "Este campo é obrigatório." in html(resposta)


def test_editar_empresa_pela_tela(client):
    empresa = fabricas.empresa()

    client.post(
        reverse("cadastros:empresa_editar", args=[empresa.pk]),
        {"nome": "Alfa S.A.", "sigla": "ALF", "versao": 1},
    )

    assert Empresa.objects.get(pk=empresa.pk).nome == "Alfa S.A."


def test_edicao_concorrente_mostra_aviso_sem_sobrescrever(client):
    empresa = fabricas.empresa()
    url = reverse("cadastros:empresa_editar", args=[empresa.pk])
    client.post(url, {"nome": "Primeira edição", "sigla": "ALF", "versao": 1})

    resposta = client.post(url, {"nome": "Segunda edição", "sigla": "ALF", "versao": 1})

    assert "alterado por outra pessoa" in html(resposta)
    assert Empresa.objects.get(pk=empresa.pk).nome == "Primeira edição"


def test_arquivar_e_reativar_empresa_pela_tela(client):
    empresa = fabricas.empresa()

    resposta = client.post(
        reverse("cadastros:empresa_arquivar", args=[empresa.pk]), {"versao": 1}, follow=True
    )
    assert "Empresa arquivada" in html(resposta)
    assert Empresa.objects.get(pk=empresa.pk).arquivado

    client.post(reverse("cadastros:empresa_reativar", args=[empresa.pk]), {"versao": 2})
    assert not Empresa.objects.get(pk=empresa.pk).arquivado


def test_arquivar_exige_post(client):
    empresa = fabricas.empresa()

    resposta = client.get(reverse("cadastros:empresa_arquivar", args=[empresa.pk]))

    assert resposta.status_code == 405
    assert not Empresa.objects.get(pk=empresa.pk).arquivado


def test_formularios_exigem_token_csrf():
    cliente = Client(enforce_csrf_checks=True)

    resposta = cliente.post(reverse("cadastros:empresa_nova"), {"nome": "X", "sigla": "X"})

    assert resposta.status_code == 403
    assert not Empresa.objects.exists()


def test_empresa_inexistente_retorna_404(client):
    resposta = client.get(reverse("cadastros:empresa_detalhe", args=[999]))

    assert resposta.status_code == 404


def test_filtro_de_busca_na_lista(client):
    fabricas.empresa(nome="Água Viva", sigla="AVI")
    fabricas.empresa(nome="Beta", sigla="BET")

    resposta = client.get(reverse("cadastros:empresa_lista"), {"busca": "agua"})

    assert "Água Viva" in html(resposta)
    assert "Beta" not in html(resposta)


# ----------------------------------------------------------------- pessoas


def test_cadastrar_pessoa_com_varias_empresas_pela_tela(client):
    a = fabricas.empresa(nome="Alfa", sigla="ALF")
    b = fabricas.empresa(nome="Beta", sigla="BET")

    resposta = client.post(
        reverse("cadastros:pessoa_nova"),
        {"nome": "Fulana", "email": "", "empresas": [a.pk, b.pk]},
        follow=True,
    )

    pessoa = Pessoa.objects.get()
    assert pessoa.email is None
    assert set(pessoa.empresas.values_list("sigla", flat=True)) == {"ALF", "BET"}
    assert "Pessoa Fulana cadastrada." in html(resposta)
    assert "Vínculo" in html(resposta)


def test_cadastro_de_pessoa_sem_empresa_mostra_erro(client):
    fabricas.empresa()

    resposta = client.post(reverse("cadastros:pessoa_nova"), {"nome": "Fulana", "empresas": []})

    assert "Selecione ao menos uma empresa." in html(resposta)
    assert not Pessoa.objects.exists()


def test_nova_pessoa_pre_seleciona_empresa_da_origem(client):
    a = fabricas.empresa()

    resposta = client.get(reverse("cadastros:pessoa_nova"), {"empresa": a.pk})

    assert f'value="{a.pk}"' in html(resposta)
    assert "checked" in html(resposta)


def test_nova_pessoa_sem_empresas_orienta_cadastrar_empresa(client):
    resposta = client.get(reverse("cadastros:pessoa_nova"))

    assert "Cadastre uma empresa" in html(resposta)


def test_empresa_arquivada_nao_aparece_como_opcao_para_nova_pessoa(client):
    ativa = fabricas.empresa(nome="Ativa", sigla="ATV")
    arquivada = fabricas.empresa(nome="Arquivada", sigla="ARQ")
    client.post(reverse("cadastros:empresa_arquivar", args=[arquivada.pk]), {"versao": 1})

    conteudo = html(client.get(reverse("cadastros:pessoa_nova")))

    assert "ATV — Ativa" in conteudo
    assert "ARQ — Arquivada" not in conteudo
    assert ativa.pk


def test_editar_pessoa_e_ver_historico(client):
    a = fabricas.empresa(nome="Alfa", sigla="ALF")
    pessoa = fabricas.pessoa(nome="Fulana", empresas=[a])

    resposta = client.post(
        reverse("cadastros:pessoa_editar", args=[pessoa.pk]),
        {"nome": "Fulana Silva", "email": "fulana@exemplo.com", "empresas": [a.pk], "versao": 1},
        follow=True,
    )

    conteudo = html(resposta)
    assert "Pessoa Fulana Silva atualizada." in conteudo
    assert "Alteração" in conteudo
    assert "Fulana Silva" in conteudo
    assert "autor não verificado" in conteudo


def test_lista_de_pessoas_filtra_por_empresa(client):
    a = fabricas.empresa(nome="Alfa", sigla="ALF")
    b = fabricas.empresa(nome="Beta", sigla="BET")
    fabricas.pessoa(nome="Pessoa da Alfa", empresas=[a])
    fabricas.pessoa(nome="Pessoa da Beta", empresas=[b])

    conteudo = html(client.get(reverse("cadastros:pessoa_lista"), {"empresa": b.pk}))

    assert "Pessoa da Beta" in conteudo
    assert "Pessoa da Alfa" not in conteudo


def test_detalhe_da_empresa_lista_pessoas_vinculadas(client):
    a = fabricas.empresa(nome="Alfa", sigla="ALF")
    fabricas.pessoa(nome="Fulana", empresas=[a])

    conteudo = html(client.get(reverse("cadastros:empresa_detalhe", args=[a.pk])))

    assert "Fulana" in conteudo


def test_menu_tem_empresas_e_pessoas(client):
    conteudo = html(client.get(reverse("core:inicio")))

    assert reverse("cadastros:empresa_lista") in conteudo
    assert reverse("cadastros:pessoa_lista") in conteudo
