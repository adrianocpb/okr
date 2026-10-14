import pytest
from django.urls import reverse

from apps.okrs.models import Objetivo, VinculoObjetivo
from apps.okrs.tests.fabricas import Cenario

pytestmark = pytest.mark.django_db


def html(resposta):
    return resposta.content.decode()


@pytest.fixture
def alfa():
    return Cenario()


def dados_formulario(cenario, **extra):
    return {
        "titulo": "Crescer receita",
        "descricao": "Aumentar a receita recorrente",
        "ciclo": cenario.anual.pk,
        "owner": cenario.ana.pk,
        "sponsor": cenario.bruno.pk,
        "status": "ativo",
        "comentario_status": "",
        **extra,
    }


def test_lista_vazia_orienta_o_primeiro_cadastro(client):
    resposta = client.get(reverse("okrs:objetivo_lista"))

    assert resposta.status_code == 200
    assert "Cadastre o primeiro objetivo" in html(resposta)


def test_novo_objetivo_pede_primeiro_a_empresa(client, alfa):
    conteudo = html(client.get(reverse("okrs:objetivo_novo")))

    assert "Escolha a empresa" in conteudo
    assert f"?empresa={alfa.empresa.pk}" in conteudo


def test_formulario_mostra_apenas_pessoas_e_ciclos_da_empresa(client, alfa):
    beta = Cenario(nome="Beta", sigla="BET")

    conteudo = html(client.get(reverse("okrs:objetivo_novo"), {"empresa": alfa.empresa.pk}))

    assert "Ana ALF" in conteudo
    assert "Ana BET" not in conteudo
    assert f'value="{beta.anual.pk}"' not in conteudo


def test_cadastrar_objetivo_pela_tela(client, alfa):
    resposta = client.post(
        reverse("okrs:objetivo_novo") + f"?empresa={alfa.empresa.pk}",
        dados_formulario(alfa),
        follow=True,
    )

    objetivo = Objetivo.objects.get()
    assert objetivo.owner == alfa.ana
    assert "Objetivo cadastrado." in html(resposta)
    assert "Criação" in html(resposta)


def test_mesma_pessoa_como_owner_e_sponsor_gera_aviso(client, alfa):
    resposta = client.post(
        reverse("okrs:objetivo_novo") + f"?empresa={alfa.empresa.pk}",
        dados_formulario(alfa, sponsor=alfa.ana.pk),
        follow=True,
    )

    assert Objetivo.objects.count() == 1
    assert "Owner e Sponsor são a mesma pessoa" in html(resposta)


def test_concluir_sem_comentario_mostra_erro(client, alfa):
    objetivo = alfa.objetivo()

    resposta = client.post(
        reverse("okrs:objetivo_editar", args=[objetivo.pk]),
        dados_formulario(alfa, status="concluido", versao=1),
    )

    assert "Informe um comentário ao concluir ou cancelar o objetivo." in html(resposta)
    assert Objetivo.objects.get().status == "ativo"


def test_editar_objetivo_pela_tela(client, alfa):
    objetivo = alfa.objetivo()

    client.post(
        reverse("okrs:objetivo_editar", args=[objetivo.pk]),
        dados_formulario(alfa, titulo="Crescer receita em 20%", versao=1),
    )

    assert Objetivo.objects.get().titulo == "Crescer receita em 20%"


def test_vincular_e_desvincular_pela_tela(client, alfa):
    anual = alfa.objetivo(titulo="Anual")
    trimestral = alfa.objetivo(titulo="Trimestral", ciclo=alfa.t1)

    detalhe = html(client.get(reverse("okrs:objetivo_detalhe", args=[trimestral.pk])))
    assert "Objetivos anuais vinculados" in detalhe
    assert "Anual" in detalhe

    resposta = client.post(
        reverse("okrs:objetivo_vincular", args=[trimestral.pk]),
        {"objetivo_anual": anual.pk},
        follow=True,
    )
    assert "Objetivo vinculado ao objetivo anual." in html(resposta)
    vinculo = VinculoObjetivo.objects.get()

    anual_html = html(client.get(reverse("okrs:objetivo_detalhe", args=[anual.pk])))
    assert "Objetivos trimestrais vinculados" in anual_html
    assert "Trimestral" in anual_html

    client.post(reverse("okrs:objetivo_desvincular", args=[trimestral.pk, vinculo.pk]))
    assert not VinculoObjetivo.objects.exists()


def test_vincular_exige_post(client, alfa):
    trimestral = alfa.objetivo(titulo="Trimestral", ciclo=alfa.t1)

    resposta = client.get(reverse("okrs:objetivo_vincular", args=[trimestral.pk]))

    assert resposta.status_code == 405


def test_objetivo_inexistente_retorna_404(client):
    assert client.get(reverse("okrs:objetivo_detalhe", args=[999])).status_code == 404


def test_lista_filtra_por_empresa(client, alfa):
    beta = Cenario(nome="Beta", sigla="BET")
    alfa.objetivo(titulo="Objetivo da Alfa")
    beta.objetivo(titulo="Objetivo da Beta")

    conteudo = html(client.get(reverse("okrs:objetivo_lista"), {"empresa": beta.empresa.pk}))

    assert "Objetivo da Beta" in conteudo
    assert "Objetivo da Alfa" not in conteudo


def test_pessoa_mostra_responsabilidades(client, alfa):
    alfa.objetivo(titulo="Crescer receita")

    conteudo = html(client.get(reverse("cadastros:pessoa_detalhe", args=[alfa.ana.pk])))

    assert "Responsabilidades" in conteudo
    assert "Crescer receita" in conteudo


def test_ciclo_e_empresa_mostram_objetivos(client, alfa):
    alfa.objetivo(titulo="Crescer receita")

    ciclo_html = html(client.get(reverse("cadastros:ciclo_detalhe", args=[alfa.anual.pk])))
    empresa_html = html(client.get(reverse("cadastros:empresa_detalhe", args=[alfa.empresa.pk])))

    assert "Crescer receita" in ciclo_html
    assert "1 objetivo" in empresa_html


def test_menu_tem_objetivos(client):
    assert reverse("okrs:objetivo_lista") in html(client.get(reverse("core:inicio")))
