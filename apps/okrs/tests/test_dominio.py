"""Testes do cálculo de progresso e da cor (Python puro, sem banco)."""

from decimal import Decimal as D

import pytest

from apps.okrs.dominio.cor import CINZA, cor_do_percentual, cor_do_progresso
from apps.okrs.dominio.progresso import (
    ErroDeMedicao,
    Medicao,
    Progresso,
    Regra,
    TipoMedicao,
    calcular,
    progresso_marcos,
    progresso_numerico,
    validar,
)

NUMERICO, MANUTENCAO = TipoMedicao.NUMERICO, TipoMedicao.MANUTENCAO
BINARIO, MARCOS = TipoMedicao.BINARIO, TipoMedicao.MARCOS


def crescente(inicial, meta):
    return Medicao(NUMERICO, Regra.CRESCENTE, D(inicial), D(meta))


def decrescente(inicial, meta):
    return Medicao(NUMERICO, Regra.DECRESCENTE, D(inicial), D(meta))


# ---------------------------------------------------------------- numérico


@pytest.mark.parametrize(
    ("inicial", "meta", "atual", "esperado"),
    [
        ("100", "150", "125", "50.00"),  # exemplo da especificação
        ("100", "150", "100", "0.00"),
        ("100", "150", "150", "100.00"),
        ("0", "3", "1", "33.33"),  # arredondamento
        ("0", "3", "2", "66.67"),
    ],
)
def test_numerico_crescente(inicial, meta, atual, esperado):
    assert calcular(crescente(inicial, meta), valor=D(atual)).percentual == D(esperado)


def test_numerico_decrescente():
    # Prazo de 10 para 6 dias; atual 8 ⇒ 50% (exemplo da especificação).
    assert calcular(decrescente("10", "6"), valor=D("8")).percentual == D("50.00")


def test_percentual_como_metrica_nao_e_confundido_com_progresso():
    # Margem de 12% para 15%; atual 13,5% ⇒ 50% de progresso, e não 13,5%.
    assert calcular(crescente("12", "15"), valor=D("13.5")).percentual == D("50.00")


def test_regressao_gera_percentual_negativo_preservado():
    progresso = calcular(crescente("100", "150"), valor=D("90"))

    assert progresso.percentual == D("-20.00")
    assert progresso.percentual_barra == D("0")


def test_superacao_passa_de_100_e_barra_fica_no_limite():
    progresso = calcular(crescente("100", "150"), valor=D("175"))

    assert progresso.percentual == D("150.00")
    assert progresso.percentual_barra == D("100")


def test_decrescente_pior_que_o_inicial_e_negativo():
    assert calcular(decrescente("10", "6"), valor=D("12")).percentual == D("-50.00")


def test_precisao_decimal_sem_erro_de_ponto_flutuante():
    # 0,1 + 0,2 em float daria 0,30000000000000004.
    medicao = crescente("0.1", "0.3")
    assert calcular(medicao, valor=D("0.2")).percentual == D("50.00")
    grandes = crescente("1000000000.0001", "1000000000.0003")
    assert calcular(grandes, valor=D("1000000000.0002")).percentual == D("50.00")


@pytest.mark.parametrize(
    ("medicao", "mensagem"),
    [
        (crescente("100", "100"), "diferente do valor inicial"),
        (crescente("150", "100"), "maior que o valor inicial"),
        (decrescente("6", "10"), "menor que o valor inicial"),
        (Medicao(NUMERICO, Regra.CRESCENTE, D(1), None), "Informe o valor inicial e a meta"),
        (Medicao(NUMERICO, Regra.MANTER_ACIMA, D(1), D(2)), "regra compatível"),
        (Medicao(NUMERICO, None, D(1), D(2)), "regra compatível"),
    ],
)
def test_configuracoes_numericas_invalidas(medicao, mensagem):
    with pytest.raises(ErroDeMedicao, match=mensagem):
        validar(medicao)


def test_meta_igual_ao_inicial_e_recusada_tambem_no_calculo_direto():
    with pytest.raises(ErroDeMedicao):
        progresso_numerico(D(5), D(5), D(5))


def test_numerico_exige_valor_medido():
    with pytest.raises(ErroDeMedicao, match="valor medido"):
        calcular(crescente("0", "10"))


# -------------------------------------------------------------- manutenção


@pytest.mark.parametrize(
    ("regra", "inferior", "superior", "atual", "atendido", "distancia"),
    [
        (Regra.MANTER_ACIMA, "70", None, "75", True, "0"),
        (Regra.MANTER_ACIMA, "70", None, "70", True, "0"),  # limite incluído
        (Regra.MANTER_ACIMA, "70", None, "68", False, "2"),
        (Regra.MANTER_ABAIXO, None, "5", "4", True, "0"),
        (Regra.MANTER_ABAIXO, None, "5", "7.5", False, "2.5"),
        (Regra.MANTER_ENTRE, "10", "20", "15", True, "0"),
        (Regra.MANTER_ENTRE, "10", "20", "8", False, "2"),
        (Regra.MANTER_ENTRE, "10", "20", "23", False, "3"),
    ],
)
def test_manutencao(regra, inferior, superior, atual, atendido, distancia):
    medicao = Medicao(
        MANUTENCAO,
        regra,
        limite_inferior=D(inferior) if inferior else None,
        limite_superior=D(superior) if superior else None,
    )

    progresso = calcular(medicao, valor=D(atual))

    assert progresso.percentual is None  # manutenção não tem percentual
    assert progresso.percentual_barra is None
    assert (progresso.atendido, progresso.distancia) == (atendido, D(distancia))


@pytest.mark.parametrize(
    ("medicao", "mensagem"),
    [
        (Medicao(MANUTENCAO, Regra.MANTER_ACIMA), "limite mínimo"),
        (Medicao(MANUTENCAO, Regra.MANTER_ABAIXO), "limite máximo"),
        (
            Medicao(MANUTENCAO, Regra.MANTER_ENTRE, limite_inferior=D(20), limite_superior=D(10)),
            "menor que o limite máximo",
        ),
        (Medicao(MANUTENCAO, Regra.CRESCENTE, limite_inferior=D(1)), "regra compatível"),
    ],
)
def test_configuracoes_de_manutencao_invalidas(medicao, mensagem):
    with pytest.raises(ErroDeMedicao, match=mensagem):
        validar(medicao)


# --------------------------------------------------------- binário e marcos


def test_binario():
    medicao = Medicao(BINARIO)

    assert calcular(medicao, concluido=False).percentual == D(0)
    assert calcular(medicao, concluido=True).percentual == D(100)


def test_binario_exige_informacao_e_nao_aceita_regra():
    with pytest.raises(ErroDeMedicao, match="concluído"):
        calcular(Medicao(BINARIO))
    with pytest.raises(ErroDeMedicao, match="não usa regra"):
        validar(Medicao(BINARIO, Regra.CRESCENTE))


@pytest.mark.parametrize(
    ("concluidos", "total", "esperado"),
    [(0, 4, "0.00"), (1, 4, "25.00"), (1, 3, "33.33"), (4, 4, "100.00")],
)
def test_marcos_com_pesos_iguais(concluidos, total, esperado):
    medicao = Medicao(MARCOS)

    progresso = calcular(medicao, marcos_concluidos=concluidos, marcos_total=total)

    assert progresso.percentual == D(esperado)


def test_marcos_sem_cadastro_ou_quantidade_invalida():
    with pytest.raises(ErroDeMedicao, match="ao menos um marco"):
        progresso_marcos(0, 0)
    with pytest.raises(ErroDeMedicao, match="inválida"):
        progresso_marcos(5, 4)
    with pytest.raises(ErroDeMedicao, match="marcos concluídos"):
        calcular(Medicao(MARCOS), marcos_total=3)


# --------------------------------------------------------------------- cor


@pytest.mark.parametrize(
    ("percentual", "cor"),
    [
        ("-20", "#d64545"),  # negativo: vermelho
        ("0", "#d64545"),  # vermelho
        ("50", "#f0a202"),  # laranja/amarelo
        ("90", "#2f9e44"),  # verde
        ("100", "#2f9e44"),
        ("150", "#2f9e44"),  # superação continua verde
    ],
)
def test_pontos_da_escala_de_cor(percentual, cor):
    assert cor_do_percentual(D(percentual)) == cor


def test_cor_e_interpolada_continuamente():
    # 10% fica perto do vermelho; 70% fica entre o amarelo e o verde.
    assert cor_do_percentual(D(10)) == "#db5838"  # 20% do caminho até o laranja
    assert cor_do_percentual(D(70)) == "#90a023"
    # 25% é exatamente o meio entre vermelho (0) e laranja/amarelo (50).
    assert cor_do_percentual(D(25)) == "#e37424"


def test_cor_de_manutencao_e_sem_dado():
    assert cor_do_progresso(Progresso(percentual=None, atendido=True)) == "#2f9e44"
    assert cor_do_progresso(Progresso(percentual=None, atendido=False)) == "#d64545"
    assert cor_do_progresso(None) == CINZA
    assert cor_do_progresso(Progresso(percentual=D(50))) == "#f0a202"
