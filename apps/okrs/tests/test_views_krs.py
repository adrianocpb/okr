from decimal import Decimal as D

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

from apps.okrs.models import Marco, ResultadoChave
from apps.okrs.tests.fabricas import Cenario

pytestmark = pytest.mark.django_db


def html(resposta):
    return resposta.content.decode()


@pytest.fixture
def alfa():
    return Cenario()


@pytest.fixture
def objetivo(alfa):
    return alfa.objetivo()


def dados_kr(cenario, **extra):
    return {
        "titulo": "Receita recorrente",
        "descricao": "",
        "responsavel": cenario.ana.pk,
        "tipo_medicao": "numerico",
        "sentido": "crescente",
        "regra_manutencao": "",
        "unidade": "R$",
        "casas_decimais": 2,
        "valor_inicial": "1.000.000,00",
        "meta": "1.250.000,50",
        "limite_inferior": "",
        "limite_superior": "",
        "frequencia_checkin_dias": 14,
        "status": "ativo",
        **extra,
    }


def test_formulario_de_kr_tem_responsavel_e_nao_tem_owner_ou_sponsor(client, objetivo):
    conteudo = html(client.get(reverse("okrs:kr_novo", args=[objetivo.pk])))

    assert 'name="responsavel"' in conteudo
    assert 'name="owner"' not in conteudo
    assert 'name="sponsor"' not in conteudo
    assert 'data-tipos="numerico"' in conteudo  # campos marcados para o script da tela


def test_cadastrar_kr_com_valores_em_formato_brasileiro(client, alfa, objetivo):
    resposta = client.post(reverse("okrs:kr_novo", args=[objetivo.pk]), dados_kr(alfa), follow=True)

    kr = ResultadoChave.objects.get()
    assert (kr.valor_inicial, kr.meta) == (D("1000000"), D("1250000.50"))
    conteudo = html(resposta)
    assert "KR cadastrado." in conteudo
    assert "De R$ 1.000.000,00 para R$ 1.250.000,50 (crescente)" in conteudo
    assert "Sem check-in" in conteudo


def test_numerico_sem_sentido_mostra_erro(client, alfa, objetivo):
    resposta = client.post(reverse("okrs:kr_novo", args=[objetivo.pk]), dados_kr(alfa, sentido=""))

    assert "Escolha se a métrica é crescente ou decrescente." in html(resposta)
    assert not ResultadoChave.objects.exists()


def test_meta_incoerente_mostra_erro_no_formulario(client, alfa, objetivo):
    resposta = client.post(
        reverse("okrs:kr_novo", args=[objetivo.pk]),
        dados_kr(alfa, sentido="decrescente"),
    )

    assert "Em métricas decrescentes, a meta deve ser menor que o valor inicial." in html(resposta)


def test_cadastrar_kr_de_manutencao(client, alfa, objetivo):
    client.post(
        reverse("okrs:kr_novo", args=[objetivo.pk]),
        dados_kr(
            alfa,
            tipo_medicao="manutencao",
            sentido="",
            regra_manutencao="manter_entre",
            unidade="dias",
            casas_decimais=0,
            limite_inferior="10",
            limite_superior="20",
        ),
    )

    kr = ResultadoChave.objects.get()
    assert (kr.regra, kr.limite_inferior, kr.limite_superior) == ("manter_entre", D(10), D(20))
    assert (kr.valor_inicial, kr.meta) == (None, None)


def test_editar_kr_mostra_valores_sem_zeros_extras(client, alfa, objetivo):
    kr = alfa.kr(objetivo, valor_inicial=D("100"), meta=D("150.5"))

    conteudo = html(client.get(reverse("okrs:kr_editar", args=[kr.pk])))

    assert 'value="100"' in conteudo
    assert 'value="150,5"' in conteudo


def test_editar_kr_pela_tela(client, alfa, objetivo):
    kr = alfa.kr(objetivo)

    client.post(
        reverse("okrs:kr_editar", args=[kr.pk]),
        dados_kr(
            alfa,
            unidade="clientes",
            casas_decimais=0,
            valor_inicial="100",
            meta="180",
            versao=1,
        ),
    )

    assert ResultadoChave.objects.get().meta == D("180")


def test_marcos_pela_tela(client, alfa, objetivo):
    kr = alfa.kr(objetivo, tipo_medicao="marcos", regra="")
    url_detalhe = reverse("okrs:kr_detalhe", args=[kr.pk])
    assert "ainda não tem marcos" in html(client.get(url_detalhe))

    client.post(reverse("okrs:marco_adicionar", args=[kr.pk]), {"descricao": "Piloto", "prazo": ""})
    marco = Marco.objects.get()
    assert "1. Piloto" in html(client.get(url_detalhe)).replace("\n", " ")

    client.post(reverse("okrs:marco_remover", args=[kr.pk, marco.pk]))
    assert not Marco.objects.exists()


def test_objetivo_lista_krs_com_progresso_individual(client, alfa, objetivo):
    alfa.kr(objetivo, titulo="KR em reais", unidade="R$")
    alfa.kr(objetivo, titulo="KR binário", tipo_medicao="binario", regra="")

    conteudo = html(client.get(reverse("okrs:objetivo_detalhe", args=[objetivo.pk])))

    assert "KR em reais" in conteudo and "KR binário" in conteudo
    assert "os percentuais não são somados entre KRs" in conteudo
    assert conteudo.count("progresso__barra") == 2


def test_objetivo_encerrado_nao_oferece_novo_kr(client, alfa):
    objetivo = alfa.objetivo(status="concluido", comentario_status="Atingido")

    assert reverse("okrs:kr_novo", args=[objetivo.pk]) not in html(
        client.get(reverse("okrs:objetivo_detalhe", args=[objetivo.pk]))
    )
    assert client.get(reverse("okrs:kr_novo", args=[objetivo.pk])).status_code == 400


def test_kr_inexistente_retorna_404(client):
    assert client.get(reverse("okrs:kr_detalhe", args=[999])).status_code == 404


def test_script_do_formulario_existe():
    assert finders.find("js/kr_form.js")
