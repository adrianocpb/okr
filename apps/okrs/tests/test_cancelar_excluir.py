from datetime import date
from decimal import Decimal as D

import pytest
from django.urls import reverse

from apps.acompanhamento import services as acompanhamento
from apps.auditoria.models import RegistroAlteracao
from apps.cadastros.tests.fabricas import ATOR, TODAS
from apps.contas import services as contas
from apps.okrs.models import Iniciativa, Marco, Objetivo, ResultadoChave, VinculoObjetivo
from apps.okrs.tests.fabricas import Cenario

pytestmark = pytest.mark.django_db
HOJE = date(2026, 6, 15)


@pytest.fixture
def alfa():
    return Cenario()


def html(resposta):
    return resposta.content.decode()


def checkin(kr):
    acompanhamento.registrar_checkin(
        kr_id=kr.pk,
        dados={
            "data_referencia": HOJE,
            "valor": D("105"),
            "status_informado": "no_ritmo",
            "autor_informado": kr.responsavel,
        },
        ator=ATOR,
        escopo=TODAS,
        hoje=HOJE,
    )


@pytest.fixture
def cliente_comum(cliente_anonimo):
    usuario, _ = contas.criar_usuario(nome="Carla Comum", email="carla@exemplo.com")
    usuario.deve_trocar_senha = False
    usuario.save()
    cliente_anonimo.force_login(usuario)
    return cliente_anonimo


# ------------------------------------------------------------------ cancelar


def test_tela_do_objetivo_mostra_cancelar_e_excluir_para_admin(client, alfa):
    objetivo = alfa.objetivo()

    conteudo = html(client.get(reverse("okrs:objetivo_detalhe", args=[objetivo.pk])))

    assert "Cancelar objetivo" in conteudo
    assert reverse("okrs:objetivo_excluir", args=[objetivo.pk]) in conteudo


def test_cancelar_pede_motivo_e_registra(client, alfa):
    objetivo = alfa.objetivo()
    url = reverse("okrs:objetivo_cancelar", args=[objetivo.pk])

    sem_motivo = client.post(url, {"motivo": "", "versao": objetivo.versao})
    assert "Este campo é obrigatório" in html(sem_motivo)

    resposta = client.post(url, {"motivo": "Prioridade mudou", "versao": objetivo.versao})

    assert resposta.status_code == 302
    objetivo.refresh_from_db()
    assert objetivo.status == Objetivo.Status.CANCELADO
    assert objetivo.comentario_status == "Prioridade mudou"
    detalhe = html(client.get(reverse("okrs:objetivo_detalhe", args=[objetivo.pk])))
    assert "Cancelar objetivo" not in detalhe


def test_usuario_comum_pode_cancelar_mas_nao_ve_excluir(cliente_comum, alfa):
    objetivo = alfa.objetivo()

    conteudo = html(cliente_comum.get(reverse("okrs:objetivo_detalhe", args=[objetivo.pk])))

    assert "Cancelar objetivo" in conteudo
    assert reverse("okrs:objetivo_excluir", args=[objetivo.pk]) not in conteudo
    url = reverse("okrs:objetivo_excluir", args=[objetivo.pk])
    assert cliente_comum.get(url).status_code == 403
    assert cliente_comum.post(url).status_code == 403
    assert Objetivo.objects.filter(pk=objetivo.pk).exists()


# ------------------------------------------------------------------- excluir


def test_excluir_objetivo_sem_acompanhamento(client, alfa):
    objetivo = alfa.objetivo(titulo="Criado por engano")
    kr = alfa.kr(objetivo)
    alfa.iniciativa(objetivo, krs=[kr])
    url = reverse("okrs:objetivo_excluir", args=[objetivo.pk])

    confirmacao = html(client.get(url))
    assert "não pode ser desfeito" in confirmacao
    assert "KR: Novos clientes" in confirmacao

    resposta = client.post(url, follow=True)

    assert "Objetivo “Criado por engano” excluído." in html(resposta)
    assert not Objetivo.objects.filter(pk=objetivo.pk).exists()
    assert not ResultadoChave.objects.filter(pk=kr.pk).exists()
    assert not Iniciativa.objects.filter(objetivo_id=objetivo.pk).exists()
    registro = RegistroAlteracao.objects.get(objeto_id=objetivo.pk, acao="exclusao")
    assert registro.ator_descricao == "Admin Teste"
    assert registro.alteracoes["krs"]["antes"] == ["Novos clientes"]

    auditoria = html(client.get(reverse("auditoria:auditoria_lista"), {"acao": "exclusao"}))
    assert "Exclusão" in auditoria
    assert "Novos clientes" in auditoria


def test_excluir_remove_marcos_e_desfaz_vinculos(client, alfa):
    anual = alfa.objetivo(titulo="Anual")
    trimestral = alfa.objetivo(titulo="Trimestral", ciclo=alfa.t1)
    VinculoObjetivo.objects.create(objetivo_anual=anual, objetivo_trimestral=trimestral)
    kr = alfa.kr(trimestral, tipo_medicao="marcos")
    Marco.objects.create(kr=kr, ordem=1, descricao="Primeira etapa")

    client.post(reverse("okrs:objetivo_excluir", args=[trimestral.pk]))

    assert not Objetivo.objects.filter(pk=trimestral.pk).exists()
    assert not VinculoObjetivo.objects.exists()
    assert RegistroAlteracao.objects.filter(objeto_id=anual.pk, acao="desvinculo").exists()


def test_objetivo_com_checkin_nao_pode_ser_excluido(client, alfa):
    objetivo = alfa.objetivo()
    checkin(alfa.kr(objetivo))
    url = reverse("okrs:objetivo_excluir", args=[objetivo.pk])

    conteudo = html(client.get(url))
    assert "já tem check-ins registrados" in conteudo
    assert "Excluir definitivamente" not in conteudo

    client.post(url)

    assert Objetivo.objects.filter(pk=objetivo.pk).exists()
