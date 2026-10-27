from datetime import date

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.acompanhamento.models import CheckIn
from apps.okrs.tests.fabricas import Cenario

pytestmark = pytest.mark.django_db

HOJE = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def hoje_fixo(monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: HOJE)


@pytest.fixture
def alfa():
    return Cenario()


@pytest.fixture
def kr(alfa):
    return alfa.kr(alfa.objetivo())


def html(resposta):
    return resposta.content.decode()


def dados(kr, **extra):
    return {
        "data_referencia": "2026-06-15",
        "valor": "125",
        "status_informado": "no_ritmo",
        "comentario": "Tudo certo",
        "dificuldades": "",
        "proximos_passos": "",
        "autor_informado": kr.responsavel_id,
        **extra,
    }


def test_formulario_mostra_campos_do_tipo_numerico(client, kr):
    conteudo = html(client.get(reverse("acompanhamento:checkin_novo", args=[kr.pk])))

    assert "Valor medido (clientes)" in conteudo
    assert 'name="concluido"' not in conteudo
    assert 'name="marcos"' not in conteudo
    assert 'name="confirmar_ciclo_encerrado"' not in conteudo  # ciclo em andamento
    assert 'value="2026-06-15"' in conteudo  # data de referência sugerida: hoje


def test_formulario_binario_pergunta_se_concluiu(client, alfa):
    kr = alfa.kr(alfa.objetivo(), tipo_medicao="binario", regra="")

    conteudo = html(client.get(reverse("acompanhamento:checkin_novo", args=[kr.pk])))

    assert "Foi concluído?" in conteudo
    assert 'name="valor"' not in conteudo


def test_registrar_checkin_pela_tela(client, kr):
    resposta = client.post(
        reverse("acompanhamento:checkin_novo", args=[kr.pk]), dados(kr), follow=True
    )

    assert CheckIn.objects.count() == 1
    conteudo = html(resposta)
    assert "Check-in registrado." in conteudo
    assert "50% · 125 clientes" in conteudo
    assert "registrado por Admin Teste" in conteudo
    assert "Tudo certo" in conteudo


def test_valor_em_formato_brasileiro(client, alfa):
    kr = alfa.kr(alfa.objetivo(), unidade="R$", casas_decimais=2)

    client.post(reverse("acompanhamento:checkin_novo", args=[kr.pk]), dados(kr, valor="125,50"))

    assert str(CheckIn.objects.get().valor) == "125.5000"


def test_data_futura_mostra_erro(client, kr):
    resposta = client.post(
        reverse("acompanhamento:checkin_novo", args=[kr.pk]),
        dados(kr, data_referencia="2026-06-16"),
    )

    assert "A data de referência não pode ser futura." in html(resposta)
    assert not CheckIn.objects.exists()


def test_retificar_pela_tela(client, kr):
    client.post(reverse("acompanhamento:checkin_novo", args=[kr.pk]), dados(kr))
    original = CheckIn.objects.get()

    formulario = html(client.get(reverse("acompanhamento:checkin_retificar", args=[original.pk])))
    assert "Motivo da retificação" in formulario
    assert 'name="data_referencia"' not in formulario  # data mantida do original

    resposta = client.post(
        reverse("acompanhamento:checkin_retificar", args=[original.pk]),
        dados(kr, valor="130", justificativa_retificacao="Valor corrigido"),
        follow=True,
    )

    conteudo = html(resposta)
    assert "Retificação registrada" in conteudo
    assert "Retificado" in conteudo
    assert "Valor corrigido" in conteudo
    assert CheckIn.objects.count() == 2


def test_objetivo_mostra_status_e_progresso_do_checkin(client, kr):
    client.post(
        reverse("acompanhamento:checkin_novo", args=[kr.pk]),
        dados(kr, status_informado="em_risco"),
    )

    conteudo = html(client.get(reverse("okrs:objetivo_detalhe", args=[kr.objetivo_id])))

    assert "50% · 125 clientes" in conteudo
    assert "Em risco" in conteudo
    assert "background: #f0a202" in conteudo  # cor de 50%


def test_atraso_aparece_no_objetivo_e_no_kr(client, kr, monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: date(2026, 2, 1))

    objetivo_html = html(client.get(reverse("okrs:objetivo_detalhe", args=[kr.objetivo_id])))
    kr_html = html(client.get(reverse("okrs:kr_detalhe", args=[kr.pk])))

    assert "Check-in atrasado" in objetivo_html
    assert "Atrasado há 17 dias" in kr_html


def test_ciclo_encerrado_pede_confirmacao(client, kr, monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: date(2027, 1, 10))

    formulario = html(client.get(reverse("acompanhamento:checkin_novo", args=[kr.pk])))
    assert 'name="confirmar_ciclo_encerrado"' in formulario
    assert 'value="2026-12-31"' in formulario  # sugere o último dia do ciclo

    resposta = client.post(
        reverse("acompanhamento:checkin_novo", args=[kr.pk]),
        dados(kr, data_referencia="2026-12-31"),
    )
    assert "Confirme para registrar" in html(resposta)


def test_checkin_de_kr_inexistente_retorna_404(client):
    assert client.get(reverse("acompanhamento:checkin_novo", args=[999])).status_code == 404
    assert client.get(reverse("acompanhamento:checkin_retificar", args=[999])).status_code == 404
