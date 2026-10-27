import pytest
from django.test import Client, override_settings

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.urls("apps.core.tests.app_teste.urls"),
]


def test_pagina_404_em_portugues(client):
    resposta = client.get("/endereco-inexistente/")

    assert resposta.status_code == 404
    assert "Página não encontrada" in resposta.content.decode()


def test_erro_de_negocio_vira_pagina_amigavel_com_status_400(client):
    resposta = client.get("/teste/erro-negocio/")

    assert resposta.status_code == 400
    html = resposta.content.decode()
    assert "Operação não realizada" in html
    assert "Regra de negócio fictícia violada." in html


def test_conflito_de_versao_retorna_409_com_orientacao(client):
    resposta = client.get("/teste/conflito/")

    assert resposta.status_code == 409
    assert "alterado por outra pessoa" in resposta.content.decode()


@override_settings(DEBUG=False)
def test_erro_inesperado_mostra_pagina_500_em_portugues(usuario_admin):
    cliente = Client(raise_request_exception=False)
    cliente.force_login(usuario_admin)

    resposta = cliente.get("/teste/erro-inesperado/")

    assert resposta.status_code == 500
    html = resposta.content.decode()
    assert "Erro interno" in html
    assert "falha inesperada fictícia" not in html  # detalhe técnico não é exposto
