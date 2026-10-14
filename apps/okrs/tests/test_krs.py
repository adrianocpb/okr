from datetime import date
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError

from apps.auditoria.models import RegistroAlteracao
from apps.auditoria.selectors import historico_legivel
from apps.auditoria.services import historico_do_objeto
from apps.cadastros import services as cadastros_services
from apps.cadastros.tests import fabricas as cadastros
from apps.cadastros.tests.fabricas import ATOR, TODAS
from apps.core.acesso import EscopoAcesso
from apps.core.erros import AcessoNegado, ConflitoDeVersao, ErroDeNegocio
from apps.okrs import formatacao, selectors, services
from apps.okrs.dominio.cor import CINZA
from apps.okrs.models import Marco, ResultadoChave
from apps.okrs.tests.fabricas import Cenario

pytestmark = pytest.mark.django_db
Acao = RegistroAlteracao.Acao


@pytest.fixture
def alfa():
    return Cenario()


@pytest.fixture
def objetivo(alfa):
    return alfa.objetivo()


# ------------------------------------------------------------ estrutura


def test_kr_nao_tem_owner_nem_sponsor():
    campos = {campo.name for campo in ResultadoChave._meta.get_fields()}

    assert "responsavel" in campos
    assert not campos & {"owner", "sponsor"}


def test_kr_exige_responsavel(alfa, objetivo):
    kr = ResultadoChave(objetivo=objetivo, titulo="X", tipo_medicao="binario")

    with pytest.raises(ValidationError) as erro:
        kr.full_clean()

    assert "responsavel" in erro.value.message_dict


def test_criar_kr_numerico_com_frequencia_quinzenal_padrao(alfa, objetivo):
    kr = alfa.kr(objetivo)

    assert kr.frequencia_checkin_dias == 14
    assert (kr.valor_inicial, kr.meta) == (D("100"), D("150"))
    registro = historico_do_objeto(kr).get()
    assert registro.acao == Acao.CRIACAO
    assert registro.empresa_id == alfa.empresa.pk


def test_responsavel_do_kr_precisa_ser_da_empresa_e_ativo(alfa, objetivo):
    de_fora = cadastros.pessoa(nome="Externa", empresas=[cadastros.empresa("Beta", "BET")])

    with pytest.raises(ValidationError) as erro:
        alfa.kr(objetivo, responsavel=de_fora)

    assert "vinculada à empresa" in erro.value.message_dict["responsavel"][0]


# ------------------------------------------------- validação da medição


@pytest.mark.parametrize(
    ("medicao", "campo", "trecho"),
    [
        ({"meta": D("100")}, "meta", "diferente do valor inicial"),
        ({"meta": D("80")}, "meta", "maior que o valor inicial"),
        ({"regra": "decrescente"}, "meta", "menor que o valor inicial"),
        ({"meta": None}, "meta", "Informe o valor inicial e a meta"),
        ({"regra": ""}, "regra", "regra compatível"),
        (
            {"tipo_medicao": "manutencao", "regra": "manter_acima"},
            "limite_inferior",
            "limite mínimo",
        ),
        (
            {"tipo_medicao": "manutencao", "regra": "manter_abaixo"},
            "limite_superior",
            "limite máximo",
        ),
        (
            {
                "tipo_medicao": "manutencao",
                "regra": "manter_entre",
                "limite_inferior": D("20"),
                "limite_superior": D("10"),
            },
            "limite_inferior",
            "menor que o limite máximo",
        ),
    ],
)
def test_medicoes_invalidas_sao_recusadas_no_campo_certo(alfa, objetivo, medicao, campo, trecho):
    with pytest.raises(ValidationError) as erro:
        alfa.kr(objetivo, **medicao)

    assert trecho in erro.value.message_dict[campo][0]


def test_campos_que_o_tipo_nao_usa_sao_descartados(alfa, objetivo):
    kr = alfa.kr(
        objetivo,
        tipo_medicao="binario",
        regra="crescente",
        unidade="clientes",
        limite_inferior=D("5"),
    )

    assert (kr.regra, kr.unidade, kr.valor_inicial, kr.meta, kr.limite_inferior) == (
        "",
        "",
        None,
        None,
        None,
    )


def test_manutencao_acima_descarta_limite_maximo(alfa, objetivo):
    kr = alfa.kr(
        objetivo,
        tipo_medicao="manutencao",
        regra="manter_acima",
        unidade="pontos",
        limite_inferior=D("70"),
        limite_superior=D("90"),
    )

    assert (kr.limite_inferior, kr.limite_superior) == (D("70"), None)


def test_percentual_como_unidade_com_decimais(alfa, objetivo):
    kr = alfa.kr(
        objetivo,
        titulo="Margem",
        unidade="%",
        casas_decimais=1,
        valor_inicial=D("12"),
        meta=D("15"),
    )

    assert formatacao.resumo_medicao(kr) == "De 12,0% para 15,0% (crescente)"


# ------------------------------------------------- criação e alteração


def test_objetivo_encerrado_nao_recebe_kr(alfa):
    objetivo = alfa.objetivo(status="cancelado", comentario_status="Fora de prioridade")

    with pytest.raises(ErroDeNegocio, match="não recebe novos KRs"):
        alfa.kr(objetivo)


def test_alterar_meta_fica_no_historico(alfa, objetivo):
    kr = alfa.kr(objetivo)

    services.atualizar_kr(kr.pk, dados={"meta": D("160")}, versao=1, ator=ATOR, escopo=TODAS)

    registro = historico_do_objeto(kr).filter(acao=Acao.ALTERACAO).get()
    assert registro.alteracoes == {"meta": {"antes": "150.0000", "depois": "160"}}
    mudanca = historico_legivel(kr)[0].mudancas[0]
    assert (mudanca.campo, mudanca.antes, mudanca.depois) == ("Meta", "150", "160")


def test_edicao_concorrente_de_kr_e_recusada(alfa, objetivo):
    kr = alfa.kr(objetivo)
    services.atualizar_kr(kr.pk, dados={"titulo": "A"}, versao=1, ator=ATOR, escopo=TODAS)

    with pytest.raises(ConflitoDeVersao):
        services.atualizar_kr(kr.pk, dados={"titulo": "B"}, versao=1, ator=ATOR, escopo=TODAS)


def test_objetivo_do_kr_nao_muda(alfa, objetivo):
    outro = alfa.objetivo(titulo="Outro")
    kr = alfa.kr(objetivo)

    kr = services.atualizar_kr(
        kr.pk, dados={"objetivo": outro, "titulo": "Y"}, versao=1, ator=ATOR, escopo=TODAS
    )

    assert kr.objetivo == objetivo


def test_responsavel_arquivado_nao_trava_edicao_de_outros_campos(alfa, objetivo):
    kr = alfa.kr(objetivo, responsavel=alfa.bruno)
    cadastros_services.arquivar_pessoa(alfa.bruno.pk, versao=1, ator=ATOR, escopo=TODAS)

    kr = services.atualizar_kr(kr.pk, dados={"titulo": "Novo"}, versao=1, ator=ATOR, escopo=TODAS)

    assert kr.titulo == "Novo"


# --------------------------------------------------------------- marcos


def test_marcos_sao_numerados_e_auditados(alfa, objetivo):
    kr = alfa.kr(objetivo, tipo_medicao="marcos", regra="")

    services.adicionar_marco(kr.pk, descricao="Contratar fornecedor", ator=ATOR, escopo=TODAS)
    services.adicionar_marco(
        kr.pk, descricao="Piloto", prazo=date(2026, 6, 30), ator=ATOR, escopo=TODAS
    )

    assert [str(m) for m in kr.marcos.all()] == ["1. Contratar fornecedor", "2. Piloto"]
    assert historico_do_objeto(kr).filter(acao=Acao.ALTERACAO).count() == 2
    assert formatacao.resumo_medicao(kr) == "2 marcos de conclusão"


def test_remover_marco_registra_no_historico(alfa, objetivo):
    kr = alfa.kr(objetivo, tipo_medicao="marcos", regra="")
    marco = services.adicionar_marco(kr.pk, descricao="Etapa 1", ator=ATOR, escopo=TODAS)

    services.remover_marco(marco.pk, ator=ATOR, escopo=TODAS)

    assert not Marco.objects.exists()
    ultima = historico_do_objeto(kr).order_by("-id").first()
    assert ultima.alteracoes == {"marco": {"antes": "1. Etapa 1", "depois": None}}


def test_marco_so_em_kr_do_tipo_marcos(alfa, objetivo):
    kr = alfa.kr(objetivo)

    with pytest.raises(ErroDeNegocio, match="tipo Marcos"):
        services.adicionar_marco(kr.pk, descricao="X", ator=ATOR, escopo=TODAS)


# ------------------------------------------------------ consulta e escopo


def test_kr_sem_checkin_aparece_em_cinza(alfa, objetivo):
    alfa.kr(objetivo)

    [kr] = selectors.krs_do_objetivo(objetivo)

    assert kr.situacao.progresso is None
    assert kr.situacao.cor == CINZA
    assert kr.situacao.texto == "Sem check-in"


def test_escopo_restrito_nao_ve_kr_de_outra_empresa(alfa, objetivo):
    kr = alfa.kr(objetivo)
    escopo_outra = EscopoAcesso.restrito([cadastros.empresa("Beta", "BET").pk])

    with pytest.raises(AcessoNegado):
        selectors.obter_kr(escopo_outra, kr.pk)
    with pytest.raises(AcessoNegado):
        services.atualizar_kr(
            kr.pk, dados={"titulo": "X"}, versao=1, ator=ATOR, escopo=escopo_outra
        )
    with pytest.raises(AcessoNegado):
        services.criar_kr(objetivo_id=objetivo.pk, dados={}, ator=ATOR, escopo=escopo_outra)


def test_responsabilidades_incluem_krs(alfa, objetivo):
    alfa.kr(objetivo, responsavel=alfa.bruno)

    papeis = selectors.responsabilidades_da_pessoa(TODAS, alfa.bruno)

    assert [kr.titulo for kr in papeis["krs"]] == ["Novos clientes"]


# ------------------------------------------------------------- formatação


@pytest.mark.parametrize(
    ("numero", "casas", "unidade", "esperado"),
    [
        (D("1234.5"), 2, "R$", "R$ 1.234,50"),
        (D("12.5"), 1, "%", "12,5%"),
        (D("30"), 0, "dias", "30 dias"),
        (D("1500"), 0, "", "1.500"),
        (None, 0, "dias", "—"),
    ],
)
def test_formatacao_de_valores(numero, casas, unidade, esperado):
    assert formatacao.valor(numero, casas, unidade) == esperado


@pytest.mark.parametrize(
    ("medicao", "esperado"),
    [
        (
            {"regra": "decrescente", "valor_inicial": D(10), "meta": D(6), "unidade": "dias"},
            "De 10 dias para 6 dias (decrescente)",
        ),
        (
            {
                "tipo_medicao": "manutencao",
                "regra": "manter_acima",
                "limite_inferior": D(70),
                "unidade": "pontos",
            },
            "Manter ≥ 70 pontos",
        ),
        (
            {
                "tipo_medicao": "manutencao",
                "regra": "manter_abaixo",
                "limite_superior": D(5),
                "unidade": "dias",
            },
            "Manter ≤ 5 dias",
        ),
        (
            {
                "tipo_medicao": "manutencao",
                "regra": "manter_entre",
                "limite_inferior": D(10),
                "limite_superior": D(20),
                "unidade": "",
            },
            "Manter entre 10 e 20",
        ),
        ({"tipo_medicao": "binario", "regra": ""}, "Concluído ou não concluído (sim/não)"),
    ],
)
def test_resumo_da_medicao(alfa, objetivo, medicao, esperado):
    assert formatacao.resumo_medicao(alfa.kr(objetivo, **medicao)) == esperado


def test_formatacao_de_percentual():
    assert formatacao.percentual(D("50.00")) == "50%"
    assert formatacao.percentual(D("33.33")) == "33,3%"
    assert formatacao.percentual(None) == "—"
