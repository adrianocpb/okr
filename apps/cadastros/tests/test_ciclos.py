from datetime import date

import pytest
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError

from apps.auditoria.models import RegistroAlteracao
from apps.auditoria.selectors import historico_legivel
from apps.auditoria.services import historico_do_objeto
from apps.cadastros import selectors, services
from apps.cadastros.models import Ciclo
from apps.cadastros.tests import fabricas
from apps.cadastros.tests.fabricas import ATOR, TODAS
from apps.core.acesso import EscopoAcesso
from apps.core.erros import AcessoNegado, ConflitoDeVersao, ErroDeNegocio

pytestmark = pytest.mark.django_db


@pytest.fixture
def empresa():
    return fabricas.empresa(nome="Alfa", sigla="ALF")


# ------------------------------------------------------------ ciclo anual


def test_ciclo_anual_sem_datas_usa_o_ano_civil(empresa):
    ciclo = fabricas.ciclo_anual(empresa, 2026)

    assert (ciclo.data_inicio, ciclo.data_fim) == (date(2026, 1, 1), date(2026, 12, 31))
    assert ciclo.tipo == Ciclo.Tipo.ANUAL
    assert str(ciclo) == "ALF · 2026"
    registro = historico_do_objeto(ciclo).get()
    assert registro.acao == RegistroAlteracao.Acao.CRIACAO
    assert registro.empresa_id == empresa.pk


def test_ciclo_anual_fiscal_com_datas_proprias(empresa):
    ciclo = fabricas.ciclo_anual(empresa, 2026, date(2026, 7, 1), date(2027, 6, 30))

    assert ciclo.periodo == "01/07/2026 a 30/06/2027"


def test_ciclo_exige_as_duas_datas_ou_nenhuma(empresa):
    with pytest.raises(ValidationError) as erro:
        fabricas.ciclo_anual(empresa, 2026, data_inicio=date(2026, 1, 1))

    assert "data_fim" in erro.value.message_dict


def test_data_de_termino_deve_ser_posterior(empresa):
    with pytest.raises(ValidationError) as erro:
        fabricas.ciclo_anual(empresa, 2026, date(2026, 12, 31), date(2026, 1, 1))

    assert erro.value.message_dict["data_fim"] == [
        "A data de término deve ser posterior à data de início."
    ]


def test_ano_repetido_na_mesma_empresa_e_recusado(empresa):
    fabricas.ciclo_anual(empresa, 2026)

    with pytest.raises(ValidationError) as erro:
        fabricas.ciclo_anual(empresa, 2026, date(2028, 1, 1), date(2028, 12, 31))

    assert erro.value.message_dict["ano"] == ["Esta empresa já tem um ciclo anual de 2026."]


def test_periodos_sobrepostos_na_mesma_empresa_sao_recusados(empresa):
    fabricas.ciclo_anual(empresa, 2026)

    with pytest.raises(ValidationError) as erro:
        fabricas.ciclo_anual(empresa, 2027, date(2026, 7, 1), date(2027, 6, 30))

    assert "se sobrepõe ao ciclo 2026" in erro.value.message_dict[NON_FIELD_ERRORS][0]


def test_empresas_diferentes_podem_ter_ciclos_com_mesmas_datas(empresa):
    outra = fabricas.empresa(nome="Beta", sigla="BET")

    fabricas.ciclo_anual(empresa, 2026)
    fabricas.ciclo_anual(outra, 2026)

    assert Ciclo.objects.filter(ano=2026).count() == 2


def test_empresa_arquivada_nao_recebe_ciclo(empresa):
    services.arquivar_empresa(empresa.pk, versao=1, ator=ATOR, escopo=TODAS)

    with pytest.raises(ErroDeNegocio, match="arquivada"):
        fabricas.ciclo_anual(empresa, 2026)


# -------------------------------------------------------------- trimestres


def test_trimestre_sem_datas_usa_periodo_padrao(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)

    t3 = fabricas.trimestre(anual, 3)

    assert (t3.data_inicio, t3.data_fim) == (date(2026, 7, 1), date(2026, 9, 30))
    assert (t3.empresa_id, t3.ano, t3.ciclo_anual_id) == (empresa.pk, 2026, anual.pk)
    assert t3.rotulo == "2026 · T3"


def test_trimestre_de_ano_fiscal_segue_o_inicio_do_ano(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026, date(2026, 7, 1), date(2027, 6, 30))

    t1, t4 = fabricas.trimestre(anual, 1), fabricas.trimestre(anual, 4)

    assert (t1.data_inicio, t1.data_fim) == (date(2026, 7, 1), date(2026, 9, 30))
    assert (t4.data_inicio, t4.data_fim) == (date(2027, 4, 1), date(2027, 6, 30))


def test_trimestre_fora_do_ano_e_recusado(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)

    with pytest.raises(ValidationError) as erro:
        fabricas.trimestre(anual, 4, date(2026, 10, 1), date(2027, 1, 31))

    assert "dentro do período do ciclo anual" in erro.value.message_dict["data_inicio"][0]


def test_trimestre_repetido_e_recusado(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    fabricas.trimestre(anual, 1)

    with pytest.raises(ValidationError) as erro:
        fabricas.trimestre(anual, 1, date(2026, 1, 1), date(2026, 1, 31))

    assert erro.value.message_dict["trimestre"] == ["O ciclo anual 2026 já tem o 1º trimestre."]


def test_trimestres_sobrepostos_sao_recusados(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    fabricas.trimestre(anual, 1)

    with pytest.raises(ValidationError) as erro:
        fabricas.trimestre(anual, 2, date(2026, 3, 1), date(2026, 5, 31))

    assert "se sobrepõe" in erro.value.message_dict[NON_FIELD_ERRORS][0]


def test_trimestre_so_pode_ser_criado_em_ciclo_anual(empresa):
    t1 = fabricas.trimestre(fabricas.ciclo_anual(empresa, 2026), 1)

    with pytest.raises(ErroDeNegocio):
        fabricas.trimestre(t1, 2)


def test_trimestre_padrao_exige_datas_quando_ano_e_irregular(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026, date(2026, 1, 15), date(2026, 12, 20))

    with pytest.raises(ValidationError) as erro:
        fabricas.trimestre(anual, 1)

    assert "informe as datas" in erro.value.message_dict["data_inicio"][0]
    t1 = fabricas.trimestre(anual, 1, date(2026, 1, 15), date(2026, 4, 14))
    assert t1.pk


# ------------------------------------------------------ geração automática


def test_gerar_trimestres_cria_os_que_faltam(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    fabricas.trimestre(anual, 2)

    criados = services.gerar_trimestres(anual.pk, ator=ATOR, escopo=TODAS)

    assert [c.trimestre for c in criados] == [1, 3, 4]
    assert anual.trimestres.count() == 4


def test_gerar_trimestres_com_todos_existentes_informa(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    services.gerar_trimestres(anual.pk, ator=ATOR, escopo=TODAS)

    with pytest.raises(ErroDeNegocio, match="quatro trimestres"):
        services.gerar_trimestres(anual.pk, ator=ATOR, escopo=TODAS)


def test_gerar_trimestres_recusa_ano_irregular(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026, date(2026, 1, 15), date(2026, 12, 20))

    with pytest.raises(ErroDeNegocio, match="individualmente"):
        services.gerar_trimestres(anual.pk, ator=ATOR, escopo=TODAS)


# ----------------------------------------------------- edição e situação


def test_editar_datas_do_ano_que_deixariam_trimestre_de_fora_e_recusado(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    fabricas.trimestre(anual, 4)

    with pytest.raises(ValidationError) as erro:
        services.atualizar_ciclo(
            anual.pk,
            dados={"data_inicio": date(2026, 1, 1), "data_fim": date(2026, 11, 30)},
            versao=1,
            ator=ATOR,
            escopo=TODAS,
        )

    assert "abrangendo todos os trimestres" in erro.value.message_dict["data_inicio"][0]


def test_mudar_ano_de_ciclo_com_trimestres_e_recusado(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    fabricas.trimestre(anual, 1)

    with pytest.raises(ValidationError) as erro:
        services.atualizar_ciclo(anual.pk, dados={"ano": 2027}, versao=1, ator=ATOR, escopo=TODAS)

    assert "já possui trimestres" in erro.value.message_dict["ano"][0]


def test_edicao_ignora_campos_que_nao_mudam_e_audita(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    outra = fabricas.empresa(nome="Beta", sigla="BET")

    ciclo = services.atualizar_ciclo(
        anual.pk,
        dados={"data_fim": date(2026, 12, 30), "empresa_id": outra.pk, "tipo": "trimestral"},
        versao=1,
        ator=ATOR,
        escopo=TODAS,
    )

    assert (ciclo.empresa_id, ciclo.tipo) == (empresa.pk, Ciclo.Tipo.ANUAL)
    registro = historico_do_objeto(ciclo).filter(acao=RegistroAlteracao.Acao.ALTERACAO).get()
    assert registro.alteracoes == {"data_fim": {"antes": "2026-12-31", "depois": "2026-12-30"}}


def test_edicao_concorrente_de_ciclo_e_recusada(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    services.atualizar_ciclo(
        anual.pk, dados={"data_fim": date(2026, 12, 30)}, versao=1, ator=ATOR, escopo=TODAS
    )

    with pytest.raises(ConflitoDeVersao):
        services.atualizar_ciclo(
            anual.pk, dados={"data_fim": date(2026, 12, 29)}, versao=1, ator=ATOR, escopo=TODAS
        )


@pytest.mark.parametrize(
    ("hoje", "situacao"),
    [
        (date(2025, 12, 31), Ciclo.Situacao.PLANEJADO),
        (date(2026, 1, 1), Ciclo.Situacao.EM_ANDAMENTO),
        (date(2026, 12, 31), Ciclo.Situacao.EM_ANDAMENTO),
        (date(2027, 1, 1), Ciclo.Situacao.ENCERRADO),
    ],
)
def test_situacao_e_calculada_pelas_datas(empresa, hoje, situacao):
    ciclo = fabricas.ciclo_anual(empresa, 2026)

    assert ciclo.situacao_em(hoje) == situacao


def test_filtro_por_situacao(empresa):
    fabricas.ciclo_anual(empresa, 2025)
    fabricas.ciclo_anual(empresa, 2026)
    fabricas.ciclo_anual(empresa, 2027)
    hoje = date(2026, 6, 15)

    def anos(situacao):
        return [c.ano for c in selectors.listar_ciclos(TODAS, situacao=situacao, hoje=hoje)]

    assert anos(Ciclo.Situacao.ENCERRADO) == [2025]
    assert anos(Ciclo.Situacao.EM_ANDAMENTO) == [2026]
    assert anos(Ciclo.Situacao.PLANEJADO) == [2027]


# ------------------------------------------------- arquivamento e escopo


def test_arquivar_anual_exige_trimestres_arquivados(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    t1 = fabricas.trimestre(anual, 1)

    with pytest.raises(ErroDeNegocio, match="Arquive primeiro os trimestres"):
        services.arquivar_ciclo(anual.pk, versao=1, ator=ATOR, escopo=TODAS)

    services.arquivar_ciclo(t1.pk, versao=1, ator=ATOR, escopo=TODAS)
    services.arquivar_ciclo(anual.pk, versao=1, ator=ATOR, escopo=TODAS)
    assert Ciclo.objects.get(pk=anual.pk).arquivado


def test_ciclo_arquivado_libera_o_periodo_e_nao_pode_ser_reativado_em_conflito(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    services.arquivar_ciclo(anual.pk, versao=1, ator=ATOR, escopo=TODAS)

    novo = fabricas.ciclo_anual(empresa, 2026)  # período e ano liberados

    with pytest.raises(ErroDeNegocio, match="já tem outro ciclo anual de 2026"):
        services.reativar_ciclo(anual.pk, versao=2, ator=ATOR, escopo=TODAS)
    assert novo.pk


def test_reativar_trimestre_exige_anual_ativo(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    t1 = fabricas.trimestre(anual, 1)
    services.arquivar_ciclo(t1.pk, versao=1, ator=ATOR, escopo=TODAS)
    services.arquivar_ciclo(anual.pk, versao=1, ator=ATOR, escopo=TODAS)

    with pytest.raises(ErroDeNegocio, match="Reative o ciclo anual"):
        services.reativar_ciclo(t1.pk, versao=2, ator=ATOR, escopo=TODAS)


def test_ciclo_arquivado_nao_pode_ser_editado(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    services.arquivar_ciclo(anual.pk, versao=1, ator=ATOR, escopo=TODAS)

    with pytest.raises(ErroDeNegocio, match="Reative"):
        services.atualizar_ciclo(
            anual.pk, dados={"data_fim": date(2026, 12, 30)}, versao=2, ator=ATOR, escopo=TODAS
        )


def test_escopo_restrito_nao_ve_nem_cria_ciclos_de_outra_empresa(empresa):
    outra = fabricas.empresa(nome="Beta", sigla="BET")
    ciclo_outra = fabricas.ciclo_anual(outra, 2026)
    escopo = EscopoAcesso.restrito([empresa.pk])

    assert not selectors.listar_ciclos(escopo).exists()
    with pytest.raises(AcessoNegado):
        selectors.obter_ciclo(escopo, ciclo_outra.pk)
    with pytest.raises(AcessoNegado):
        services.criar_ciclo_anual(empresa_id=outra.pk, ano=2027, ator=ATOR, escopo=escopo)
    with pytest.raises(AcessoNegado):
        services.criar_trimestre(
            ciclo_anual_id=ciclo_outra.pk, trimestre=1, ator=ATOR, escopo=escopo
        )


def test_historico_mostra_referencias_pelo_nome(empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    t1 = fabricas.trimestre(anual, 1)

    criacao = historico_legivel(t1)[0]
    valores = {m.campo: m.depois for m in criacao.mudancas}

    assert valores["Ciclo anual"] == "ALF · 2026"
    assert valores["Empresa"] == "ALF — Alfa"
    assert valores["Tipo"] == "Trimestral"
    assert valores["Trimestre"] == "1º trimestre"
