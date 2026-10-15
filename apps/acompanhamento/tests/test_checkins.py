from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError

from apps.acompanhamento import selectors, services
from apps.acompanhamento.models import CheckIn
from apps.auditoria.models import RegistroAlteracao
from apps.cadastros import services as cadastros_services
from apps.cadastros.tests import fabricas as cadastros
from apps.cadastros.tests.fabricas import ATOR, TODAS
from apps.core.acesso import EscopoAcesso
from apps.core.erros import AcessoNegado, ErroDeNegocio
from apps.core.models import RegistroImutavel
from apps.okrs import services as okrs_services
from apps.okrs.dominio.cor import CINZA
from apps.okrs.tests.fabricas import Cenario

pytestmark = pytest.mark.django_db

HOJE = date(2026, 6, 15)  # dentro do ciclo anual 2026 dos cenários de teste


@pytest.fixture
def alfa():
    return Cenario()


@pytest.fixture
def kr(alfa):
    return alfa.kr(alfa.objetivo())  # numérico crescente: 100 → 150 clientes


def registrar(kr, hoje=HOJE, **dados):
    base = {
        "data_referencia": hoje,
        "valor": D("125"),
        "status_informado": "no_ritmo",
        "comentario": "Andamento normal",
        "autor_informado": kr.responsavel,
    }
    base.update(dados)
    return services.registrar_checkin(kr_id=kr.pk, dados=base, ator=ATOR, escopo=TODAS, hoje=hoje)


# ------------------------------------------------------------ registro


def test_checkin_guarda_dados_e_copia_da_medicao(kr):
    checkin = registrar(kr, dificuldades="Equipe reduzida", proximos_passos="Contratar")

    assert (checkin.valor, checkin.status_informado) == (D("125"), "no_ritmo")
    assert (checkin.valor_inicial_vigente, checkin.meta_vigente) == (D("100"), D("150"))
    assert (checkin.tipo_medicao_vigente, checkin.regra_vigente) == ("numerico", "crescente")
    assert checkin.registrado_por is None and not checkin.autor_verificado
    assert checkin.progresso().percentual == D("50.00")


def test_situacao_do_kr_usa_o_checkin(kr):
    registrar(kr, status_informado="atencao")

    situacao = selectors.situacao_do_kr(kr, hoje=HOJE)

    assert situacao.texto == "50% · 125 clientes"
    assert situacao.cor == "#f0a202"
    assert (situacao.status, situacao.status_rotulo) == ("atencao", "Atenção")
    assert situacao.data_ultimo_checkin == HOJE


def test_checkin_nao_vai_para_o_historico_de_alteracoes(kr):
    antes = RegistroAlteracao.objects.count()

    registrar(kr)

    assert RegistroAlteracao.objects.count() == antes


@pytest.mark.parametrize(
    ("data", "trecho"),
    [
        (HOJE + timedelta(days=1), "não pode ser futura"),
        (date(2025, 12, 31), "anterior ao início do ciclo"),
    ],
)
def test_datas_de_referencia_invalidas(kr, data, trecho):
    with pytest.raises(ValidationError) as erro:
        registrar(kr, data_referencia=data)

    assert trecho in erro.value.message_dict["data_referencia"][0]


def test_ciclo_encerrado_exige_confirmacao_e_data_dentro_do_ciclo(kr):
    depois_do_fim = date(2027, 1, 10)

    with pytest.raises(ValidationError) as erro:
        registrar(kr, hoje=depois_do_fim, data_referencia=date(2026, 12, 31))
    assert "Confirme" in erro.value.message_dict["confirmar_ciclo_encerrado"][0]

    with pytest.raises(ValidationError) as erro:
        registrar(
            kr, hoje=depois_do_fim, data_referencia=depois_do_fim, confirmar_ciclo_encerrado=True
        )
    assert "dentro do ciclo" in erro.value.message_dict["data_referencia"][0]

    checkin = registrar(
        kr, hoje=depois_do_fim, data_referencia=date(2026, 12, 31), confirmar_ciclo_encerrado=True
    )
    assert checkin.pk


def test_autor_deve_ser_pessoa_ativa_da_empresa(alfa, kr):
    externa = cadastros.pessoa(nome="Externa", empresas=[cadastros.empresa("Beta", "BET")])
    with pytest.raises(ValidationError) as erro:
        registrar(kr, autor_informado=externa)
    assert "vinculada à empresa" in erro.value.message_dict["autor_informado"][0]

    cadastros_services.arquivar_pessoa(alfa.bruno.pk, versao=1, ator=ATOR, escopo=TODAS)
    alfa.bruno.refresh_from_db()
    with pytest.raises(ValidationError) as erro:
        registrar(kr, autor_informado=alfa.bruno)
    assert "arquivada" in erro.value.message_dict["autor_informado"][0]


def test_campos_obrigatorios_por_tipo(alfa):
    objetivo = alfa.objetivo()
    numerico = alfa.kr(objetivo, titulo="Numérico")
    binario = alfa.kr(objetivo, titulo="Binário", tipo_medicao="binario", regra="")

    with pytest.raises(ValidationError) as erro:
        registrar(numerico, valor=None, status_informado="")
    assert {"valor", "status_informado"} <= set(erro.value.message_dict)

    with pytest.raises(ValidationError) as erro:
        registrar(binario, valor=None)
    assert "concluido" in erro.value.message_dict


def test_kr_ou_objetivo_cancelado_nao_recebe_checkin(alfa, kr):
    okrs_services.atualizar_kr(
        kr.pk, dados={"status": "cancelado"}, versao=1, ator=ATOR, escopo=TODAS
    )
    with pytest.raises(ErroDeNegocio, match="KR cancelado"):
        registrar(kr)

    objetivo = alfa.objetivo(
        titulo="Cancelado", status="cancelado", comentario_status="Saiu do plano"
    )
    outro = okrs_services.ResultadoChave.objects.create(
        objetivo=objetivo,
        titulo="KR legado",
        responsavel=alfa.ana,
        tipo_medicao="binario",
    )
    with pytest.raises(ErroDeNegocio, match="Objetivo cancelado"):
        registrar(outro, concluido=True)


def test_escopo_restrito_nao_registra_em_outra_empresa(kr):
    escopo = EscopoAcesso.restrito([cadastros.empresa("Beta", "BET").pk])

    with pytest.raises(AcessoNegado):
        services.registrar_checkin(kr_id=kr.pk, dados={}, ator=ATOR, escopo=escopo, hoje=HOJE)


# --------------------------------------------------------- imutabilidade


def test_checkin_nao_pode_ser_alterado_nem_excluido(kr):
    checkin = registrar(kr)

    checkin.valor = D("999")
    with pytest.raises(RegistroImutavel):
        checkin.save()
    with pytest.raises(RegistroImutavel):
        checkin.delete()
    with pytest.raises(RegistroImutavel):
        CheckIn.objects.filter(pk=checkin.pk).update(valor=D("999"))
    with pytest.raises(RegistroImutavel):
        CheckIn.objects.all().delete()

    assert CheckIn.objects.get(pk=checkin.pk).valor == D("125")


# ----------------------------------------------------------- retificação


def retificar(checkin, **dados):
    base = {
        "valor": D("130"),
        "status_informado": "no_ritmo",
        "autor_informado": checkin.autor_informado,
        "justificativa_retificacao": "Valor digitado errado",
    }
    base.update(dados)
    return services.retificar_checkin(checkin.pk, dados=base, ator=ATOR, escopo=TODAS, hoje=HOJE)


def test_retificacao_cria_novo_registro_e_preserva_o_original(kr):
    original = registrar(kr, data_referencia=date(2026, 6, 1))

    correcao = retificar(original)

    original.refresh_from_db()
    assert original.retificado and original.valor == D("125")
    assert correcao.retifica == original
    assert correcao.data_referencia == date(2026, 6, 1)  # mantém a data do original
    assert selectors.checkin_vigente(kr) == correcao
    assert [c.pk for c in selectors.checkins_do_kr(kr)] == [correcao.pk, original.pk]


def test_retificacao_exige_justificativa(kr):
    original = registrar(kr)

    with pytest.raises(ValidationError) as erro:
        retificar(original, justificativa_retificacao="  ")

    assert "justificativa_retificacao" in erro.value.message_dict


def test_nao_se_retifica_duas_vezes_o_mesmo_checkin(kr):
    original = registrar(kr)
    retificar(original)

    with pytest.raises(ErroDeNegocio, match="já foi retificado"):
        retificar(original)


# ------------------------------------------------- vigente e histórico


def test_checkin_vigente_e_o_de_data_mais_recente_e_depois_o_ultimo_registrado(kr):
    registrar(kr, data_referencia=date(2026, 6, 10), valor=D("140"))
    antigo_registrado_depois = registrar(kr, data_referencia=date(2026, 5, 1), valor=D("110"))
    assert selectors.checkin_vigente(kr).valor == D("140")
    assert antigo_registrado_depois.pk  # data antiga não substitui o mais recente

    empate = registrar(kr, data_referencia=date(2026, 6, 10), valor=D("145"))
    assert selectors.checkin_vigente(kr) == empate


def test_mudanca_de_meta_preserva_o_calculo_historico(kr):
    checkin = registrar(kr)  # 125 de 100→150 = 50%

    okrs_services.atualizar_kr(kr.pk, dados={"meta": D("200")}, versao=1, ator=ATOR, escopo=TODAS)
    kr.refresh_from_db()

    [historico] = selectors.checkins_do_kr(kr)
    assert historico.situacao.progresso.percentual == D("50.00")  # meta da época
    assert selectors.situacao_do_kr(kr, hoje=HOJE).progresso.percentual == D("25.00")  # meta atual
    assert checkin.meta_vigente == D("150")


def test_tipo_de_medicao_nao_muda_depois_de_checkins(kr):
    registrar(kr)

    with pytest.raises(ValidationError) as erro:
        okrs_services.atualizar_kr(
            kr.pk, dados={"tipo_medicao": "binario"}, versao=1, ator=ATOR, escopo=TODAS
        )

    assert "não pode mudar" in erro.value.message_dict["tipo_medicao"][0]


# ------------------------------------------------------- tipos de medição


def test_manutencao_fora_do_limite(alfa):
    kr = alfa.kr(
        alfa.objetivo(),
        tipo_medicao="manutencao",
        regra="manter_acima",
        unidade="pontos",
        limite_inferior=D("70"),
    )
    registrar(kr, valor=D("68"), status_informado="em_risco")

    situacao = selectors.situacao_do_kr(kr, hoje=HOJE)

    assert situacao.texto == "Fora do limite · 68 pontos (2 pontos além do limite)"
    assert situacao.cor == "#d64545"


def test_binario(alfa):
    kr = alfa.kr(alfa.objetivo(), tipo_medicao="binario", regra="")
    registrar(kr, valor=None, concluido=True, status_informado="concluido")

    assert selectors.situacao_do_kr(kr, hoje=HOJE).texto == "Concluído"


def test_marcos(alfa):
    kr = alfa.kr(alfa.objetivo(), tipo_medicao="marcos", regra="")
    with pytest.raises(ErroDeNegocio, match="Cadastre os marcos"):
        registrar(kr, valor=None)

    m1 = okrs_services.adicionar_marco(kr.pk, descricao="Etapa 1", ator=ATOR, escopo=TODAS)
    okrs_services.adicionar_marco(kr.pk, descricao="Etapa 2", ator=ATOR, escopo=TODAS)
    registrar(kr, valor=None, marcos_ids=[m1.pk])

    assert selectors.situacao_do_kr(kr, hoje=HOJE).texto == "1 de 2 marcos · 50%"
    with pytest.raises(ErroDeNegocio, match="já foi registrado em check-ins"):
        okrs_services.remover_marco(m1.pk, ator=ATOR, escopo=TODAS)


def test_marcos_de_outro_kr_sao_recusados(alfa):
    objetivo = alfa.objetivo()
    kr_a = alfa.kr(objetivo, titulo="A", tipo_medicao="marcos", regra="")
    kr_b = alfa.kr(objetivo, titulo="B", tipo_medicao="marcos", regra="")
    okrs_services.adicionar_marco(kr_a.pk, descricao="Etapa A", ator=ATOR, escopo=TODAS)
    marco_b = okrs_services.adicionar_marco(kr_b.pk, descricao="Etapa B", ator=ATOR, escopo=TODAS)

    with pytest.raises(ValidationError) as erro:
        registrar(kr_a, valor=None, marcos_ids=[marco_b.pk])

    assert "marcos" in erro.value.message_dict


# ------------------------------------------------------------- atraso


def test_atraso_sem_nenhum_checkin_conta_desde_o_inicio_do_ciclo(kr):
    situacao = selectors.situacao_do_kr(kr, hoje=date(2026, 1, 21))  # início + 14 + 6

    assert situacao.texto == "Sem check-in" and situacao.cor == CINZA
    assert situacao.proximo_checkin == date(2026, 1, 15)
    assert situacao.dias_em_atraso == 6


def test_checkin_recente_zera_o_atraso(kr):
    registrar(kr, data_referencia=date(2026, 6, 10))

    assert selectors.situacao_do_kr(kr, hoje=HOJE).dias_em_atraso == 0
    assert selectors.situacao_do_kr(kr, hoje=date(2026, 6, 30)).dias_em_atraso == 6


def test_sem_atraso_fora_do_ciclo_ou_para_kr_concluido(kr):
    assert selectors.situacao_do_kr(kr, hoje=date(2027, 3, 1)).dias_em_atraso == 0

    okrs_services.atualizar_kr(
        kr.pk, dados={"status": "concluido"}, versao=1, ator=ATOR, escopo=TODAS
    )
    kr.refresh_from_db()
    assert selectors.situacao_do_kr(kr, hoje=date(2026, 6, 30)).dias_em_atraso == 0
