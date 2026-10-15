from datetime import date
from decimal import Decimal as D

import pytest
from django.contrib.staticfiles import finders
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.acompanhamento import services as acompanhamento
from apps.cadastros.tests.fabricas import ATOR, TODAS
from apps.okrs.tests.fabricas import Cenario

pytestmark = pytest.mark.django_db
HOJE = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: HOJE)


@pytest.fixture
def alfa():
    return Cenario()


def checkin(kr, data, valor, status="no_ritmo"):
    acompanhamento.registrar_checkin(
        kr_id=kr.pk,
        dados={
            "data_referencia": data,
            "valor": D(valor),
            "status_informado": status,
            "autor_informado": kr.responsavel,
        },
        ator=ATOR,
        escopo=TODAS,
        hoje=HOJE,
    )


def lista(client, **filtros):
    return client.get(reverse("okrs:objetivo_lista"), filtros).content.decode()


def test_cada_objetivo_e_uma_linha_que_abre_e_fecha(client, alfa):
    alfa.objetivo(titulo="Crescer receita")
    alfa.objetivo(titulo="Reduzir custos")

    conteudo = lista(client)

    assert conteudo.count('<details class="objetivo-linha"') == 2
    assert "data-expandir-todos" in conteudo and "data-recolher-todos" in conteudo
    assert finders.find("js/objetivos_lista.js")


def test_linha_mostra_krs_com_ultimo_checkin_resultado_e_grafico(client, alfa):
    objetivo = alfa.objetivo(titulo="Crescer receita")
    kr = alfa.kr(objetivo, titulo="Novos clientes")
    alfa.kr(objetivo, titulo="KR ainda sem check-in")
    checkin(kr, date(2026, 5, 1), "110")
    checkin(kr, date(2026, 6, 10), "125", status="atencao")

    conteudo = lista(client)

    assert "Novos clientes" in conteudo
    assert "10/06/2026" in conteudo  # data do último check-in
    assert "Atenção" in conteudo
    assert "50% · 125 clientes" in conteudo  # resultado
    assert 'class="mini-grafico"' in conteudo  # gráfico de evolução
    assert "último 125 clientes em 10/06/2026" in conteudo  # descrição acessível
    assert "KR ainda sem check-in" in conteudo and "Sem check-ins" in conteudo


def test_iniciativas_aparecem_abaixo_dos_krs(client, alfa):
    objetivo = alfa.objetivo(titulo="Crescer receita")
    kr = alfa.kr(objetivo, titulo="Novos clientes")
    alfa.iniciativa(objetivo, titulo="Campanha de vendas", krs=[kr], prazo=date(2026, 6, 1))

    conteudo = lista(client)

    posicao_krs = conteudo.index("Resultados-chave")
    posicao_iniciativas = conteudo.index(">Iniciativas</h3>")
    assert posicao_krs < posicao_iniciativas < conteudo.index("Campanha de vendas")
    assert "Atrasada" in conteudo  # prazo vencido


def test_consultas_nao_crescem_com_a_quantidade_de_objetivos(client, alfa):
    def montar(quantidade, prefixo):
        for n in range(quantidade):
            objetivo = alfa.objetivo(titulo=f"{prefixo} {n}")
            kr = alfa.kr(objetivo, titulo=f"KR {prefixo} {n}")
            checkin(kr, date(2026, 6, 1), "120")
            alfa.iniciativa(objetivo, titulo=f"Iniciativa {prefixo} {n}", krs=[kr])

    def consultas():
        with CaptureQueriesContext(connection) as contexto:
            lista(client)
        return len(contexto)

    montar(2, "A")
    com_dois = consultas()
    montar(6, "B")
    com_oito = consultas()

    assert com_oito == com_dois
