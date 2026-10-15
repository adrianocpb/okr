from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.acompanhamento import services
from apps.acompanhamento.linha_do_tempo import linha_do_tempo
from apps.auditoria.models import RegistroAlteracao
from apps.auditoria.selectors import entradas_legiveis, listar_auditoria
from apps.cadastros.tests import fabricas as cadastros
from apps.cadastros.tests.fabricas import ATOR, TODAS
from apps.core.acesso import EscopoAcesso
from apps.okrs import services as okrs_services
from apps.okrs.tests.fabricas import Cenario

pytestmark = pytest.mark.django_db
HOJE = date(2026, 6, 15)


@pytest.fixture
def cenario():
    alfa = Cenario()
    objetivo = alfa.objetivo()
    kr = alfa.kr(objetivo)
    iniciativa = alfa.iniciativa(objetivo, krs=[kr])
    checkin = services.registrar_checkin(
        kr_id=kr.pk,
        dados={
            "data_referencia": HOJE,
            "valor": D("125"),
            "status_informado": "atencao",
            "comentario": "Abaixo do esperado",
            "autor_informado": alfa.ana,
        },
        ator=ATOR,
        escopo=TODAS,
        hoje=HOJE,
    )
    services.registrar_atualizacao(
        iniciativa_id=iniciativa.pk,
        dados={
            "data_referencia": HOJE,
            "status": "em_andamento",
            "dificuldades": "Equipe reduzida",
            "autor_informado": alfa.bruno,
        },
        ator=ATOR,
        escopo=TODAS,
        hoje=HOJE,
    )
    return alfa, objetivo, kr, iniciativa, checkin


# ---------------------------------------------------------- linha do tempo


def test_linha_do_tempo_reune_as_tres_categorias_em_ordem(cenario):
    _, objetivo, *_ = cenario

    itens = linha_do_tempo(objetivo)

    categorias = {item.categoria for item in itens}
    assert categorias == {"checkin", "atualizacao", "alteracao"}
    momentos = [item.momento for item in itens]
    assert momentos == sorted(momentos, reverse=True)


def test_linha_do_tempo_filtra_por_categoria(cenario):
    _, objetivo, *_ = cenario

    checkins = linha_do_tempo(objetivo, "checkin")
    atualizacoes = linha_do_tempo(objetivo, "atualizacao")
    alteracoes = linha_do_tempo(objetivo, "alteracao")

    assert [i.resumo for i in checkins] == ["50% · 125 clientes"]
    assert [i.rotulo_status for i in checkins] == ["Atenção"]
    assert ("Dificuldades", "Equipe reduzida") in atualizacoes[0].detalhes
    titulos = " ".join(i.titulo for i in alteracoes)
    assert "Objetivo: Crescer receita" in titulos
    assert "Resultado-chave: Novos clientes" in titulos
    assert "Iniciativa: Campanha de vendas" in titulos


def test_linha_do_tempo_mostra_retificacao(cenario):
    alfa, objetivo, kr, _, checkin = cenario
    services.retificar_checkin(
        checkin.pk,
        dados={
            "valor": D("130"),
            "status_informado": "no_ritmo",
            "autor_informado": alfa.ana,
            "justificativa_retificacao": "Correção",
        },
        ator=ATOR,
        escopo=TODAS,
        hoje=HOJE,
    )

    itens = linha_do_tempo(objetivo, "checkin")

    assert [(i.retificacao, i.retificado) for i in itens] == [(True, False), (False, True)]
    assert ("Motivo da retificação", "Correção") in itens[0].detalhes


def test_linha_do_tempo_nao_mistura_objetivos(cenario):
    alfa, *_ = cenario
    outro = alfa.objetivo(titulo="Outro objetivo")

    titulos = [i.titulo for i in linha_do_tempo(outro)]

    assert titulos == ["Criação · Objetivo: Outro objetivo"]


# --------------------------------------------------------------- auditoria


def test_auditoria_filtra_por_tipo_acao_empresa_e_periodo(cenario):
    alfa, objetivo, *_ = cenario
    beta = cadastros.empresa("Beta", "BET")

    def descricoes(**filtros):
        return {r.objeto_descricao for r in listar_auditoria(TODAS, **filtros)}

    assert descricoes(tipo="objetivo") == {"Crescer receita"}
    assert descricoes(tipo="kr") == {"Novos clientes"}
    assert "Beta" not in str(descricoes(empresa_id=alfa.empresa.pk))
    assert descricoes(empresa_id=beta.pk) == {"BET — Beta"}
    hoje = timezone.localdate()
    assert descricoes(data_de=hoje + timedelta(days=1)) == set()
    assert "Crescer receita" in descricoes(data_de=hoje, data_ate=hoje)
    okrs_services.atualizar_objetivo(
        objetivo.pk, dados={"titulo": "Novo"}, versao=1, ator=ATOR, escopo=TODAS
    )
    assert descricoes(acao=RegistroAlteracao.Acao.ALTERACAO) >= {"Novo"}


def test_auditoria_com_escopo_restrito_so_mostra_suas_empresas(cenario):
    alfa, *_ = cenario
    beta = Cenario(nome="Beta", sigla="BET")

    registros = listar_auditoria(EscopoAcesso.restrito([beta.empresa.pk]))

    assert registros.exists()
    assert set(registros.values_list("empresa_id", flat=True)) == {beta.empresa.pk}


def test_entradas_legiveis_trazem_tipo_e_link(cenario):
    _, objetivo, *_ = cenario

    [entrada] = entradas_legiveis(listar_auditoria(TODAS, tipo="objetivo"))

    assert entrada.tipo_registro == "Objetivo"
    assert entrada.url_objeto == reverse("okrs:objetivo_detalhe", args=[objetivo.pk])


# ------------------------------------------------------------------- telas


def test_tela_da_linha_do_tempo(client, cenario):
    _, objetivo, *_ = cenario
    url = reverse("acompanhamento:linha_do_tempo", args=[objetivo.pk])

    tudo = client.get(url).content.decode()
    so_checkins = client.get(url, {"tipo": "checkin"}).content.decode()

    assert "linha-do-tempo__item--checkin" in tudo
    assert "linha-do-tempo__item--atualizacao" in tudo
    assert "linha-do-tempo__item--alteracao" in tudo
    assert "linha-do-tempo__item--alteracao" not in so_checkins
    assert "Abaixo do esperado" in so_checkins
    assert url in client.get(reverse("okrs:objetivo_detalhe", args=[objetivo.pk])).content.decode()


def test_tela_de_auditoria(client, cenario):
    conteudo = client.get(
        reverse("auditoria:auditoria_lista"), {"tipo": "iniciativa"}
    ).content.decode()

    assert "Campanha de vendas" in conteudo
    lista = conteudo.split("</form>")[1]
    assert 'selo--neutro">Iniciativa<' in lista
    assert 'selo--neutro">Objetivo<' not in lista  # só registros do tipo filtrado
    assert "autor não verificado" in conteudo


def test_auditoria_no_menu(client):
    conteudo = client.get(reverse("core:inicio")).content.decode()

    assert reverse("auditoria:auditoria_lista") in conteudo
