import re
from datetime import date
from decimal import Decimal as D

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.acompanhamento import services
from apps.acompanhamento.grafico import MARGEM_ESQ, desenhar, serie_do_kr
from apps.cadastros.tests.fabricas import ATOR, TODAS
from apps.okrs import selectors as okrs_selectors
from apps.okrs import services as okrs_services
from apps.okrs.tests.fabricas import Cenario

pytestmark = pytest.mark.django_db
HOJE = date(2026, 6, 15)


def checkin(kr, data, valor=None, status="no_ritmo", **extra):
    return services.registrar_checkin(
        kr_id=kr.pk,
        dados={
            "data_referencia": data,
            "valor": D(valor) if valor is not None else None,
            "status_informado": status,
            "autor_informado": kr.responsavel,
            **extra,
        },
        ator=ATOR,
        escopo=TODAS,
        hoje=HOJE,
    )


@pytest.fixture
def alfa():
    return Cenario()


# ------------------------------------------------------------------- série


def test_serie_usa_checkins_vigentes_em_ordem_de_data(alfa):
    kr = alfa.kr(alfa.objetivo())
    checkin(kr, date(2026, 3, 1), "120")
    errado = checkin(kr, date(2026, 2, 1), "999")
    services.retificar_checkin(
        errado.pk,
        dados={
            "valor": D("110"),
            "status_informado": "atencao",
            "autor_informado": kr.responsavel,
            "justificativa_retificacao": "Digitação",
        },
        ator=ATOR,
        escopo=TODAS,
        hoje=HOJE,
    )

    serie = serie_do_kr(kr)

    assert [(p.data, p.valor) for p in serie.pontos] == [
        (date(2026, 2, 1), D("110")),  # a retificação substitui o valor errado
        (date(2026, 3, 1), D("120")),
    ]
    assert [p.rotulo for p in serie.pontos] == ["110 clientes", "120 clientes"]
    assert [r.rotulo for r in serie.referencias] == [
        "Linha de base: 100 clientes",
        "Meta: 150 clientes",
    ]
    assert (serie.inicio, serie.fim) == (date(2026, 1, 1), date(2026, 12, 31))


def test_serie_de_manutencao_mostra_limites(alfa):
    kr = alfa.kr(
        alfa.objetivo(),
        tipo_medicao="manutencao",
        regra="manter_entre",
        unidade="dias",
        limite_inferior=D(10),
        limite_superior=D(20),
    )
    checkin(kr, date(2026, 5, 1), "15")

    serie = serie_do_kr(kr)

    assert [r.rotulo for r in serie.referencias] == ["Mínimo: 10 dias", "Máximo: 20 dias"]
    assert not serie.eixo_percentual


def test_serie_de_marcos_usa_percentual(alfa):
    kr = alfa.kr(alfa.objetivo(), tipo_medicao="marcos", regra="")
    m1 = okrs_services.adicionar_marco(kr.pk, descricao="Etapa 1", ator=ATOR, escopo=TODAS)
    okrs_services.adicionar_marco(kr.pk, descricao="Etapa 2", ator=ATOR, escopo=TODAS)
    checkin(kr, date(2026, 4, 1), marcos_ids=[m1.pk])

    serie = serie_do_kr(kr)

    assert serie.eixo_percentual
    assert [(p.valor, p.rotulo) for p in serie.pontos] == [(D("50.00"), "50%")]


# ----------------------------------------------------------------- desenho


def test_desenho_posiciona_pontos_no_periodo_do_ciclo(alfa):
    kr = alfa.kr(alfa.objetivo())
    checkin(kr, date(2026, 1, 1), "100")
    checkin(kr, date(2026, 6, 15), "150")

    desenho = desenhar(serie_do_kr(kr), hoje=HOJE)

    (x1, y1, _), (x2, y2, _) = desenho.pontos
    assert x1 == MARGEM_ESQ  # início do ciclo
    assert x2 == desenho.hoje_x  # mesmo dia de "hoje"
    assert y2 < y1  # valor maior fica mais alto no gráfico
    y_meta = dict((r.rotulo, posicao) for posicao, r in desenho.referencias)["Meta: 150 clientes"]
    assert y_meta == y2  # o ponto de 150 está na linha da meta
    assert desenho.linha == f"{x1},{y1} {x2},{y2}"


def test_desenho_sem_hoje_fora_do_ciclo(alfa):
    kr = alfa.kr(alfa.objetivo())
    checkin(kr, date(2026, 2, 1), "120")

    assert desenhar(serie_do_kr(kr), hoje=date(2027, 2, 1)).hoje_x is None


# ------------------------------------------------------------------- telas


def test_tela_do_kr_mostra_grafico_e_tabela_equivalente(client, alfa, monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: HOJE)
    kr = alfa.kr(
        alfa.objetivo(), unidade="R$", casas_decimais=2, valor_inicial=D("1000"), meta=D("1500.5")
    )
    url = reverse("okrs:kr_detalhe", args=[kr.pk])
    assert "O gráfico aparece a partir do primeiro check-in." in client.get(url).content.decode()

    checkin(kr, date(2026, 3, 1), "1200.25")
    checkin(kr, date(2026, 5, 1), "1300")
    conteudo = client.get(url).content.decode()

    assert "<svg" in conteudo and 'role="img"' in conteudo
    assert "Evolução do KR" in conteudo
    pontos = re.search(r'<polyline points="([^"]+)"', conteudo).group(1)
    assert "," in pontos and not re.search(r"\d,\d+,", pontos)  # coordenadas com ponto decimal
    assert "<td>R$ 1.200,25</td>" in conteudo  # tabela com os mesmos valores
    assert "<td>R$ 1.300,00</td>" in conteudo
    assert "Meta: R$ 1.500,50" in conteudo


# ------------------------------------------------- comparação entre períodos


def test_desdobramento_trimestral_lado_a_lado_sem_valor_combinado(alfa):
    anual = alfa.objetivo(titulo="Anual")
    t1 = alfa.objetivo(titulo="Do T1", ciclo=alfa.t1)
    t2 = alfa.objetivo(titulo="Do T2", ciclo=alfa.t2)
    alfa.objetivo(titulo="T2 sem vínculo", ciclo=alfa.t2)
    for trimestral in (t1, t2):
        okrs_services.vincular(
            objetivo_trimestral_id=trimestral.pk,
            objetivo_anual_id=anual.pk,
            ator=ATOR,
            escopo=TODAS,
        )
    kr_t1 = alfa.kr(t1, titulo="KR em reais", unidade="R$")
    alfa.kr(
        t2, titulo="KR em dias", regra="decrescente", unidade="dias", valor_inicial=D(10), meta=D(5)
    )
    checkin(kr_t1, date(2026, 3, 1), "125", confirmar_ciclo_encerrado=True)  # T1 já encerrou

    colunas = okrs_selectors.desdobramento_trimestral(anual)

    assert [c["rotulo"] for c in colunas] == [
        "1º trimestre",
        "2º trimestre",
        "3º trimestre",
        "4º trimestre",
    ]
    assert [[o.titulo for o in c["objetivos"]] for c in colunas] == [["Do T1"], ["Do T2"], [], []]
    [kr] = colunas[0]["objetivos"][0].krs_lista
    assert kr.situacao.texto == "50% · R$ 125"
    assert all(set(c) == {"rotulo", "ciclo", "objetivos"} for c in colunas)  # nada agregado
    assert okrs_selectors.desdobramento_trimestral(t1) == []  # só para objetivos anuais


def test_tela_do_objetivo_anual_mostra_desdobramento(client, alfa):
    anual = alfa.objetivo(titulo="Anual")
    t1 = alfa.objetivo(titulo="Objetivo do primeiro trimestre", ciclo=alfa.t1)
    okrs_services.vincular(
        objetivo_trimestral_id=t1.pk, objetivo_anual_id=anual.pk, ator=ATOR, escopo=TODAS
    )
    alfa.kr(t1, titulo="KR trimestral")

    conteudo = client.get(reverse("okrs:objetivo_detalhe", args=[anual.pk])).content.decode()

    assert "Desdobramento por trimestre" in conteudo
    assert "Objetivo do primeiro trimestre" in conteudo
    assert "KR trimestral" in conteudo
    assert "não há valor combinado" in conteudo
