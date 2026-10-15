from datetime import date
from decimal import Decimal as D

import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse
from django.utils import timezone

from apps.acompanhamento import services as acompanhamento
from apps.cadastros import services as cadastros_services
from apps.cadastros.tests.fabricas import ATOR, TODAS
from apps.core.acesso import EscopoAcesso
from apps.okrs import services as okrs_services
from apps.okrs.models import Objetivo
from apps.okrs.tests.fabricas import Cenario
from apps.painel.selectors import Filtros, montar_painel

pytestmark = pytest.mark.django_db
HOJE = date(2026, 6, 15)


def checkin(kr, valor, status, hoje=HOJE, **extra):
    return acompanhamento.registrar_checkin(
        kr_id=kr.pk,
        dados={
            "data_referencia": hoje,
            "valor": D(valor) if valor is not None else None,
            "status_informado": status,
            "autor_informado": kr.responsavel,
            **extra,
        },
        ator=ATOR,
        escopo=TODAS,
        hoje=hoje,
    )


def painel(filtros=None, escopo=TODAS, hoje=HOJE):
    return montar_painel(escopo, filtros or Filtros(data_de=hoje, data_ate=hoje), hoje)


@pytest.fixture
def alfa():
    return Cenario()


# ------------------------------------------------- agregação por contagem


def test_distribuicao_por_situacao_e_situacao_mais_critica(alfa):
    objetivo = alfa.objetivo()
    kr_ok = alfa.kr(objetivo, titulo="No ritmo")
    kr_risco = alfa.kr(objetivo, titulo="Em risco")
    alfa.kr(objetivo, titulo="Sem check-in")
    checkin(kr_ok, "190", "no_ritmo")
    checkin(kr_risco, "105", "em_risco")

    [cartao] = painel().cartoes

    assert cartao.distribuicao.itens == [
        ("em_risco", "Em risco", 1),
        ("sem_checkin", "Sem check-in", 1),
        ("no_ritmo", "No ritmo", 1),
    ]
    assert cartao.distribuicao.mais_critica == ("em_risco", "Em risco")


def test_painel_nao_soma_nem_tira_media_de_percentuais(client, alfa, monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: HOJE)
    objetivo = alfa.objetivo()
    checkin(alfa.kr(objetivo, titulo="KR zero"), "100", "atencao")  # 0%
    checkin(alfa.kr(objetivo, titulo="KR cem"), "150", "no_ritmo")  # 100%

    conteudo = client.get(reverse("painel:painel")).content.decode()

    assert "0% · 100 clientes" in conteudo and "100% · 150 clientes" in conteudo
    assert "50%" not in conteudo  # nenhuma média entre KRs diferentes
    assert not any(hasattr(cartao, "percentual") for cartao in painel().cartoes)


def test_kr_concluido_conta_como_concluido_e_cancelado_nao_conta(alfa):
    objetivo = alfa.objetivo()
    concluido = alfa.kr(objetivo, titulo="Concluído")
    cancelado = alfa.kr(objetivo, titulo="Cancelado")
    okrs_services.atualizar_kr(
        concluido.pk, dados={"status": "concluido"}, versao=1, ator=ATOR, escopo=TODAS
    )
    okrs_services.atualizar_kr(
        cancelado.pk, dados={"status": "cancelado"}, versao=1, ator=ATOR, escopo=TODAS
    )

    resultado = painel()

    assert resultado.distribuicao.itens == [("concluido", "Concluído", 1)]


def test_objetivos_mais_criticos_aparecem_primeiro(alfa):
    tranquilo = alfa.objetivo(titulo="A tranquilo")
    critico = alfa.objetivo(titulo="B crítico")
    checkin(alfa.kr(tranquilo), "190", "no_ritmo")
    checkin(alfa.kr(critico), "105", "em_risco")

    assert [c.objetivo.titulo for c in painel().cartoes] == ["B crítico", "A tranquilo"]


# ----------------------------------------------------------------- filtros


def test_periodo_padrao_mostra_ciclos_em_andamento(alfa):
    alfa.objetivo(titulo="Anual 2026")
    alfa.objetivo(titulo="Do T1", ciclo=alfa.t1)  # T1 encerrou em 31/03
    alfa.objetivo(titulo="Do T2", ciclo=alfa.t2)  # T2 em andamento em 15/06

    titulos = {c.objetivo.titulo for c in painel().cartoes}

    assert titulos == {"Anual 2026", "Do T2"}


def test_filtros_por_empresa_ciclo_periodo_status_e_situacao(alfa):
    beta = Cenario(nome="Beta", sigla="BET")
    alfa.objetivo(titulo="Alfa anual")
    rascunho = alfa.objetivo(titulo="Alfa rascunho", status="rascunho")
    alfa.objetivo(titulo="Alfa T1", ciclo=alfa.t1)
    beta.objetivo(titulo="Beta anual")
    checkin(alfa.kr(rascunho), "105", "em_risco")

    def titulos(**filtros):
        base = {"data_de": HOJE, "data_ate": HOJE}
        base.update(filtros)
        return {c.objetivo.titulo for c in painel(Filtros(**base)).cartoes}

    assert titulos(empresa_id=beta.empresa.pk) == {"Beta anual"}
    assert titulos(ciclo_id=alfa.t1.pk, data_de=None, data_ate=None) == {"Alfa T1"}
    assert titulos(
        data_de=date(2026, 1, 1), data_ate=date(2026, 2, 1), empresa_id=alfa.empresa.pk
    ) == {
        "Alfa anual",
        "Alfa T1",
    }
    assert titulos(status_objetivo="rascunho") == {"Alfa rascunho"}
    assert titulos(status_objetivo="", situacao_kr="em_risco") == {"Alfa rascunho"}


def test_escopo_restrito_so_mostra_suas_empresas(alfa):
    beta = Cenario(nome="Beta", sigla="BET")
    alfa.objetivo(titulo="Alfa")
    beta.objetivo(titulo="Beta")

    resultado = painel(escopo=EscopoAcesso.restrito([beta.empresa.pk]))

    assert [c.objetivo.titulo for c in resultado.cartoes] == ["Beta"]


# ----------------------------------------------------------------- alertas


def tipos_de_alerta(**kwargs):
    return {(a.tipo, a.texto.split(" — ")[0]) for a in painel(**kwargs).alertas}


def test_alertas_de_kr(alfa):
    objetivo = alfa.objetivo()
    risco = alfa.kr(objetivo, titulo="KR risco")
    atencao = alfa.kr(objetivo, titulo="KR atenção")
    nps = alfa.kr(
        objetivo,
        titulo="NPS",
        tipo_medicao="manutencao",
        regra="manter_acima",
        unidade="pontos",
        limite_inferior=D(70),
    )
    alfa.kr(objetivo, titulo="KR atrasado")  # sem check-in desde 01/01
    checkin(risco, "105", "em_risco")
    checkin(atencao, "120", "atencao")
    checkin(nps, "60", "no_ritmo")

    alertas = tipos_de_alerta()

    assert ("KR em risco", "KR risco") in alertas
    assert ("KR em atenção", "KR atenção") in alertas
    assert ("Fora do limite", "NPS") in alertas
    assert ("Check-in atrasado", "KR atrasado") in alertas
    assert ("Check-in atrasado", "KR risco") not in alertas


def test_alertas_de_objetivo_iniciativa_e_responsavel(alfa):
    alfa.objetivo(titulo="Sem KR")
    com_kr = alfa.objetivo(titulo="Com KR")
    checkin(alfa.kr(com_kr), "190", "no_ritmo")
    alfa.iniciativa(com_kr, titulo="Iniciativa vencida", prazo=date(2026, 6, 1))
    alfa.iniciativa(com_kr, titulo="Iniciativa no prazo", prazo=date(2026, 7, 1))
    cadastros_services.arquivar_pessoa(alfa.bruno.pk, versao=1, ator=ATOR, escopo=TODAS)

    alertas = tipos_de_alerta()

    assert ("Objetivo sem KR", "Sem KR") in alertas
    assert ("Iniciativa atrasada", "Iniciativa vencida") in alertas
    assert ("Iniciativa atrasada", "Iniciativa no prazo") not in alertas
    assert ("Responsável inativo", "Objetivo: Sem KR") in alertas  # Bruno é sponsor
    assert ("Responsável inativo", "Iniciativa: Iniciativa no prazo") in alertas


def test_alertas_mais_graves_primeiro(alfa):
    objetivo = alfa.objetivo()
    alfa.objetivo(titulo="Sem KR")
    checkin(alfa.kr(objetivo, titulo="KR risco"), "105", "em_risco")

    assert painel().alertas[0].tipo == "KR em risco"


# ------------------------------------------------------------------- telas


def test_painel_e_a_pagina_inicial(client, alfa, monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: HOJE)
    objetivo = alfa.objetivo(titulo="Crescer receita")
    checkin(alfa.kr(objetivo), "105", "em_risco")

    conteudo = client.get("/").content.decode()

    assert "Painel de OKRs" in conteudo
    assert "Crescer receita" in conteudo
    assert "Precisa de atenção" in conteudo
    assert "KR em risco" in conteudo  # alerta com texto, não só cor
    assert "Situação mais crítica" in conteudo
    assert "Mostrando ciclos em andamento hoje (15/06/2026)" in conteudo


def test_filtros_pela_tela(client, alfa, monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: HOJE)
    alfa.objetivo(titulo="Objetivo do T1", ciclo=alfa.t1)

    padrao = client.get("/").content.decode()
    por_ciclo = client.get("/", {"ciclo": alfa.t1.pk}).content.decode()

    assert "Objetivo do T1" not in padrao
    assert "Objetivo do T1" in por_ciclo


def test_situacao_do_sistema_continua_acessivel(client):
    conteudo = client.get(reverse("core:inicio")).content.decode()

    assert reverse("core:inicio") == "/sistema/"
    assert "Situação do sistema" in conteudo
    assert 'href="/"' in conteudo  # marca e menu levam ao painel


# ---------------------------------------------------------- dados fictícios


def test_gerar_dados_ficticios_exige_confirmacao_e_banco_vazio(alfa):
    with pytest.raises(CommandError, match="--confirmar"):
        call_command("gerar_dados_ficticios")
    with pytest.raises(CommandError, match="já tem empresas"):
        call_command("gerar_dados_ficticios", "--confirmar")


def test_gerar_dados_ficticios_em_banco_vazio(capsys):
    call_command(
        "gerar_dados_ficticios",
        "--confirmar",
        "--empresas=2",
        "--objetivos=6",
        "--checkins=30",
    )

    assert Objetivo.objects.count() == 6
    assert "Dados fictícios gerados" in capsys.readouterr().out
