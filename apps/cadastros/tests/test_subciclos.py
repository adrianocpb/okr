"""Ciclos bimestrais, divisão do ano na criação e telas de ciclo anual e subciclo."""

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.cadastros import services
from apps.cadastros.models import Ciclo
from apps.cadastros.tests import fabricas
from apps.cadastros.tests.fabricas import ATOR, TODAS
from apps.okrs import services as okrs_services
from apps.okrs.tests.fabricas import Cenario

pytestmark = pytest.mark.django_db


def html(resposta):
    return resposta.content.decode()


@pytest.fixture
def empresa():
    return fabricas.empresa(nome="Alfa", sigla="ALF")


def criar_ano(empresa, **divisao):
    return services.criar_ciclo_anual(
        empresa_id=empresa.pk, ano=2026, ator=ATOR, escopo=TODAS, **divisao
    )


# ----------------------------------------------------------------- regras


def test_criar_ano_dividido_em_trimestres_e_bimestres(empresa):
    anual = criar_ano(empresa, dividir_trimestres=True, dividir_bimestres=True)

    trimestres = anual.subciclos.filter(tipo="trimestral").order_by("trimestre")
    bimestres = anual.subciclos.filter(tipo="bimestral").order_by("bimestre")
    assert [c.sigla_subciclo for c in trimestres] == ["T1", "T2", "T3", "T4"]
    assert [c.sigla_subciclo for c in bimestres] == ["B1", "B2", "B3", "B4", "B5", "B6"]
    assert (bimestres[0].data_inicio, bimestres[0].data_fim) == (
        date(2026, 1, 1),
        date(2026, 2, 28),
    )
    assert (bimestres[5].data_inicio, bimestres[5].data_fim) == (
        date(2026, 11, 1),
        date(2026, 12, 31),
    )
    assert str(bimestres[5]) == "ALF · 2026 · B6"


def test_criar_ano_sem_divisao_nao_cria_subciclos(empresa):
    anual = criar_ano(empresa)

    assert not anual.subciclos.exists()


def test_divisao_exige_ano_regular(empresa):
    with pytest.raises(ValidationError, match="dia 1 e durar 12 meses"):
        services.criar_ciclo_anual(
            empresa_id=empresa.pk,
            ano=2026,
            data_inicio=date(2026, 1, 15),
            data_fim=date(2026, 12, 31),
            dividir_bimestres=True,
            ator=ATOR,
            escopo=TODAS,
        )
    # Nada fica gravado pela metade.
    assert not Ciclo.objects.exists()


def test_bimestre_numero_valido_e_unico(empresa):
    anual = criar_ano(empresa, dividir_bimestres=True)

    with pytest.raises(ValidationError, match="já tem o 3º bimestre"):
        services.criar_subciclo(
            ciclo_anual_id=anual.pk, tipo="bimestral", numero=3, ator=ATOR, escopo=TODAS
        )


def test_gerar_bimestres_cria_os_que_faltam(empresa):
    anual = criar_ano(empresa)
    services.criar_subciclo(
        ciclo_anual_id=anual.pk, tipo="bimestral", numero=2, ator=ATOR, escopo=TODAS
    )

    criados = services.gerar_subciclos(anual.pk, tipo="bimestral", ator=ATOR, escopo=TODAS)

    assert [c.bimestre for c in criados] == [1, 3, 4, 5, 6]


def test_objetivo_bimestral_pode_contribuir_para_o_anual():
    alfa = Cenario()
    b1 = services.criar_subciclo(
        ciclo_anual_id=alfa.anual.pk, tipo="bimestral", numero=1, ator=ATOR, escopo=TODAS
    )
    anual = alfa.objetivo(titulo="Anual")
    bimestral = alfa.objetivo(titulo="Do B1", ciclo=b1)

    vinculo = okrs_services.vincular(
        objetivo_trimestral_id=bimestral.pk, objetivo_anual_id=anual.pk, ator=ATOR, escopo=TODAS
    )

    assert vinculo.objetivo_anual == anual


# ------------------------------------------------------------------ telas


def test_novo_ciclo_anual_com_caixas_de_divisao(client, empresa):
    url = reverse("cadastros:ciclo_anual_novo")

    formulario = html(client.get(url))
    assert "Dividir em ciclos trimestrais" in formulario
    assert "Dividir em ciclos bimestrais" in formulario

    resposta = client.post(
        url,
        {"empresa": empresa.pk, "ano": 2026, "dividir_trimestres": "on", "dividir_bimestres": "on"},
        follow=True,
    )

    assert "cadastrado, com trimestres e bimestres." in html(resposta)
    assert Ciclo.objects.filter(tipo="trimestral").count() == 4
    assert Ciclo.objects.filter(tipo="bimestral").count() == 6


def test_tela_do_ciclo_anual_mostra_subciclos_e_objetivos_anuais(client):
    alfa = Cenario()
    services.gerar_subciclos(alfa.anual.pk, tipo="bimestral", ator=ATOR, escopo=TODAS)
    anual = alfa.objetivo(titulo="Crescer receita")
    trimestral = alfa.objetivo(titulo="Fechar contratos", ciclo=alfa.t1)
    okrs_services.vincular(
        objetivo_trimestral_id=trimestral.pk, objetivo_anual_id=anual.pk, ator=ATOR, escopo=TODAS
    )
    url = reverse("cadastros:ciclo_detalhe", args=[alfa.anual.pk])

    trimestres = html(client.get(url))
    assert "Trimestres (2)" in trimestres
    assert "Bimestres (6)" in trimestres
    assert "Objetivos anuais (1)" in trimestres
    assert "Crescer receita" in trimestres
    assert "Desdobrado em" in trimestres
    assert "1 objetivo" in trimestres  # T1 tem um objetivo

    bimestres = html(client.get(url, {"sub": "bi"}))
    assert "B6" in bimestres


def test_tela_do_subciclo_mostra_contribuicao_e_sem_desdobramento(client):
    alfa = Cenario()
    anual = alfa.objetivo(titulo="Crescer receita")
    alfa.objetivo(titulo="Estruturar dados")
    trimestral = alfa.objetivo(titulo="Fechar contratos", ciclo=alfa.t2)
    okrs_services.vincular(
        objetivo_trimestral_id=trimestral.pk, objetivo_anual_id=anual.pk, ator=ATOR, escopo=TODAS
    )

    conteudo = html(client.get(reverse("cadastros:ciclo_detalhe", args=[alfa.t2.pk])))

    assert "T2 2026" in conteudo
    assert "Objetivos do T2 (1)" in conteudo
    assert "Contribui para" in conteudo
    assert "Objetivos anuais sem desdobramento no T2" in conteudo
    assert "Estruturar dados" in conteudo
    assert 'aria-label="Anterior: T1"' in conteudo


def test_gerar_bimestres_pela_tela(client, empresa):
    anual = criar_ano(empresa)

    resposta = client.post(reverse("cadastros:ciclo_gerar_bimestres", args=[anual.pk]), follow=True)

    assert "Bimestres criados: B1, B2, B3, B4, B5, B6." in html(resposta)


def test_comentarios_de_template_nao_vazam_nas_telas(client):
    alfa = Cenario()
    alfa.objetivo(titulo="Crescer receita")
    for url in (
        reverse("cadastros:ciclo_detalhe", args=[alfa.anual.pk]),
        reverse("cadastros:ciclo_detalhe", args=[alfa.t1.pk]),
        reverse("cadastros:ciclo_lista"),
        reverse("okrs:objetivo_lista"),
    ):
        assert "{#" not in html(client.get(url)), url
