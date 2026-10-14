from datetime import date

import pytest
from django.urls import reverse

from apps.cadastros.models import Ciclo
from apps.cadastros.tests import fabricas

pytestmark = pytest.mark.django_db


def html(resposta):
    return resposta.content.decode()


@pytest.fixture
def empresa():
    return fabricas.empresa(nome="Alfa", sigla="ALF")


def test_lista_vazia_orienta_o_primeiro_cadastro(client):
    resposta = client.get(reverse("cadastros:ciclo_lista"))

    assert resposta.status_code == 200
    assert "Cadastre o primeiro ciclo anual" in html(resposta)


def test_criar_ciclo_anual_pela_tela_com_ano_civil(client, empresa):
    resposta = client.post(
        reverse("cadastros:ciclo_anual_novo"),
        {"empresa": empresa.pk, "ano": 2026, "data_inicio": "", "data_fim": ""},
        follow=True,
    )

    ciclo = Ciclo.objects.get()
    assert (ciclo.data_inicio, ciclo.data_fim) == (date(2026, 1, 1), date(2026, 12, 31))
    assert "Ciclo anual ALF · 2026 cadastrado." in html(resposta)
    assert "Gerar trimestres que faltam" in html(resposta)


def test_criar_ciclo_anual_com_datas_do_seletor_do_navegador(client, empresa):
    client.post(
        reverse("cadastros:ciclo_anual_novo"),
        {"empresa": empresa.pk, "ano": 2026, "data_inicio": "2026-07-01", "data_fim": "2027-06-30"},
    )

    assert Ciclo.objects.get().periodo == "01/07/2026 a 30/06/2027"


def test_ciclo_anual_duplicado_mostra_erro_no_formulario(client, empresa):
    fabricas.ciclo_anual(empresa, 2026)

    resposta = client.post(
        reverse("cadastros:ciclo_anual_novo"), {"empresa": empresa.pk, "ano": 2026}
    )

    assert "Esta empresa já tem um ciclo anual de 2026." in html(resposta)
    assert Ciclo.objects.count() == 1


def test_novo_ciclo_pre_seleciona_empresa(client, empresa):
    conteudo = html(client.get(reverse("cadastros:ciclo_anual_novo"), {"empresa": empresa.pk}))

    assert f'<option value="{empresa.pk}" selected>' in conteudo


def test_gerar_trimestres_pela_tela(client, empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)

    resposta = client.post(
        reverse("cadastros:ciclo_gerar_trimestres", args=[anual.pk]), follow=True
    )

    assert "Trimestres criados: T1, T2, T3, T4." in html(resposta)
    assert anual.trimestres.count() == 4


def test_gerar_trimestres_exige_post(client, empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)

    resposta = client.get(reverse("cadastros:ciclo_gerar_trimestres", args=[anual.pk]))

    assert resposta.status_code == 405


def test_novo_trimestre_mostra_periodos_padrao_e_cria(client, empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    url = reverse("cadastros:ciclo_trimestre_novo", args=[anual.pk])

    assert "01/04/2026 a 30/06/2026" in html(client.get(url))

    resposta = client.post(url, {"trimestre": 2, "data_inicio": "", "data_fim": ""}, follow=True)
    assert "Ciclo ALF · 2026 · T2 cadastrado." in html(resposta)


def test_trimestre_fora_do_ano_mostra_erro(client, empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)

    resposta = client.post(
        reverse("cadastros:ciclo_trimestre_novo", args=[anual.pk]),
        {"trimestre": 4, "data_inicio": "2026-10-01", "data_fim": "2027-01-31"},
    )

    assert "dentro do período do ciclo anual" in html(resposta)


def test_novo_trimestre_em_ciclo_trimestral_e_recusado(client, empresa):
    t1 = fabricas.trimestre(fabricas.ciclo_anual(empresa, 2026), 1)

    resposta = client.get(reverse("cadastros:ciclo_trimestre_novo", args=[t1.pk]))

    assert resposta.status_code == 400


def test_editar_ciclo_pela_tela(client, empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    url = reverse("cadastros:ciclo_editar", args=[anual.pk])
    assert 'name="trimestre"' not in html(client.get(url))  # anual não edita trimestre

    client.post(
        url, {"ano": 2026, "data_inicio": "2026-01-01", "data_fim": "2026-12-30", "versao": 1}
    )

    assert Ciclo.objects.get(pk=anual.pk).data_fim == date(2026, 12, 30)


def test_arquivar_ciclo_com_trimestres_mostra_mensagem(client, empresa):
    anual = fabricas.ciclo_anual(empresa, 2026)
    fabricas.trimestre(anual, 1)

    resposta = client.post(
        reverse("cadastros:ciclo_arquivar", args=[anual.pk]), {"versao": 1}, follow=True
    )

    assert "Arquive primeiro os trimestres" in html(resposta)
    assert not Ciclo.objects.get(pk=anual.pk).arquivado


def test_lista_filtra_por_empresa_e_tipo(client, empresa):
    outra = fabricas.empresa(nome="Beta", sigla="BET")
    anual = fabricas.ciclo_anual(empresa, 2026)
    fabricas.trimestre(anual, 1)
    fabricas.ciclo_anual(outra, 2026)

    conteudo = html(
        client.get(reverse("cadastros:ciclo_lista"), {"empresa": empresa.pk, "tipo": "trimestral"})
    )

    assert "2026 · T1" in conteudo
    assert "BET" not in conteudo.split("<tbody>")[1]


def test_detalhe_da_empresa_lista_ciclos(client, empresa):
    fabricas.ciclo_anual(empresa, 2026)

    conteudo = html(client.get(reverse("cadastros:empresa_detalhe", args=[empresa.pk])))

    assert "01/01/2026 a 31/12/2026" in conteudo
    assert reverse("cadastros:ciclo_anual_novo") in conteudo


def test_menu_tem_ciclos(client):
    assert reverse("cadastros:ciclo_lista") in html(client.get(reverse("core:inicio")))
