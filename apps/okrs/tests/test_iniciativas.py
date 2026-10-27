from datetime import date
from decimal import Decimal as D

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.acompanhamento import selectors as acompanhamento_selectors
from apps.acompanhamento import services as acompanhamento
from apps.acompanhamento.models import AtualizacaoIniciativa
from apps.auditoria.models import RegistroAlteracao
from apps.auditoria.selectors import historico_legivel
from apps.auditoria.services import historico_do_objeto
from apps.cadastros.tests import fabricas as cadastros
from apps.cadastros.tests.fabricas import ATOR, TODAS
from apps.core.acesso import EscopoAcesso
from apps.core.erros import AcessoNegado, ConflitoDeVersao, ErroDeNegocio
from apps.core.models import RegistroImutavel
from apps.okrs import selectors, services
from apps.okrs.models import Iniciativa
from apps.okrs.tests.fabricas import Cenario

pytestmark = pytest.mark.django_db
Acao = RegistroAlteracao.Acao
HOJE = date(2026, 6, 15)


@pytest.fixture
def alfa():
    return Cenario()


@pytest.fixture
def objetivo(alfa):
    return alfa.objetivo()


# --------------------------------------------------------------- estrutura


def test_iniciativa_tem_responsavel_e_nao_tem_owner_nem_sponsor():
    campos = {campo.name for campo in Iniciativa._meta.get_fields()}

    assert "responsavel" in campos
    assert not campos & {"owner", "sponsor"}


def test_criar_iniciativa_sem_kr_contribui_para_o_objetivo(alfa, objetivo):
    iniciativa = alfa.iniciativa(objetivo, prazo=date(2026, 9, 30))

    assert iniciativa.status == Iniciativa.Status.NAO_INICIADA
    assert not iniciativa.krs.exists()
    assert historico_do_objeto(iniciativa).get().empresa_id == alfa.empresa.pk


def test_iniciativa_pode_contribuir_para_varios_krs(alfa, objetivo):
    kr1, kr2 = alfa.kr(objetivo, titulo="KR 1"), alfa.kr(objetivo, titulo="KR 2")

    iniciativa = alfa.iniciativa(objetivo, krs=[kr1, kr2])

    assert set(iniciativa.krs.values_list("titulo", flat=True)) == {"KR 1", "KR 2"}
    assert historico_do_objeto(iniciativa).filter(acao=Acao.VINCULO).count() == 2


def test_kr_de_outro_objetivo_e_recusado(alfa, objetivo):
    kr_de_outro = alfa.kr(alfa.objetivo(titulo="Outro"), titulo="KR alheio")

    with pytest.raises(ValidationError) as erro:
        alfa.iniciativa(objetivo, krs=[kr_de_outro])

    assert "mesmo objetivo" in erro.value.message_dict["krs"][0]
    assert not Iniciativa.objects.exists()


def test_responsavel_precisa_ser_da_empresa(alfa, objetivo):
    externa = cadastros.pessoa(nome="Externa", empresas=[cadastros.empresa("Beta", "BET")])

    with pytest.raises(ValidationError) as erro:
        alfa.iniciativa(objetivo, responsavel=externa)

    assert "vinculada à empresa" in erro.value.message_dict["responsavel"][0]


def test_objetivo_encerrado_nao_recebe_iniciativa(alfa):
    objetivo = alfa.objetivo(status="concluido", comentario_status="Atingido")

    with pytest.raises(ErroDeNegocio, match="novas iniciativas"):
        alfa.iniciativa(objetivo)


# ---------------------------------------------------------------- alteração


def test_concluir_registra_data_e_reabrir_limpa(alfa, objetivo):
    iniciativa = alfa.iniciativa(objetivo)

    iniciativa = services.atualizar_iniciativa(
        iniciativa.pk, dados={"status": "concluida"}, versao=1, ator=ATOR, escopo=TODAS
    )
    assert iniciativa.data_conclusao == timezone.localdate()

    iniciativa = services.atualizar_iniciativa(
        iniciativa.pk, dados={"status": "em_andamento"}, versao=2, ator=ATOR, escopo=TODAS
    )
    assert iniciativa.data_conclusao is None


def test_trocar_krs_audita_e_incrementa_versao(alfa, objetivo):
    kr1, kr2 = alfa.kr(objetivo, titulo="KR 1"), alfa.kr(objetivo, titulo="KR 2")
    iniciativa = alfa.iniciativa(objetivo, krs=[kr1])

    iniciativa = services.atualizar_iniciativa(
        iniciativa.pk, dados={}, kr_ids=[kr2.pk], versao=1, ator=ATOR, escopo=TODAS
    )

    assert iniciativa.versao == 2
    assert list(iniciativa.krs.values_list("titulo", flat=True)) == ["KR 2"]
    mudancas = [
        (e.acao, e.mudancas[0].campo, e.mudancas[0].antes, e.mudancas[0].depois)
        for e in historico_legivel(iniciativa)[:2]
    ]
    assert ("Desvínculo", "KR", "KR 1", "—") in mudancas
    assert ("Vínculo", "KR", "—", "KR 2") in mudancas
    with pytest.raises(ConflitoDeVersao):
        services.atualizar_iniciativa(
            iniciativa.pk, dados={"titulo": "X"}, versao=1, ator=ATOR, escopo=TODAS
        )


def test_iniciativa_nao_altera_progresso_do_kr(alfa, objetivo):
    kr = alfa.kr(objetivo)
    antes = selectors.situacao_do_kr(kr)

    iniciativa = alfa.iniciativa(objetivo, krs=[kr])
    services.atualizar_iniciativa(
        iniciativa.pk, dados={"status": "concluida"}, versao=1, ator=ATOR, escopo=TODAS
    )

    depois = selectors.situacao_do_kr(kr)
    assert (
        (antes.progresso, antes.texto) == (depois.progresso, depois.texto) == (None, "Sem check-in")
    )


def test_atraso_considera_prazo_e_status(alfa, objetivo):
    vencida = alfa.iniciativa(objetivo, titulo="Vencida", prazo=date(2026, 6, 1))
    alfa.iniciativa(objetivo, titulo="No prazo", prazo=date(2026, 7, 1))
    alfa.iniciativa(objetivo, titulo="Sem prazo")
    concluida = alfa.iniciativa(objetivo, titulo="Concluída", prazo=date(2026, 5, 1))
    services.atualizar_iniciativa(
        concluida.pk, dados={"status": "concluida"}, versao=1, ator=ATOR, escopo=TODAS
    )

    atrasadas = [
        i.titulo for i in selectors.iniciativas_do_objetivo(objetivo, hoje=HOJE) if i.atrasada
    ]

    assert atrasadas == ["Vencida"]
    assert vencida.atrasada_em(HOJE)


def test_escopo_restrito_nao_ve_iniciativa_de_outra_empresa(alfa, objetivo):
    iniciativa = alfa.iniciativa(objetivo)
    escopo = EscopoAcesso.restrito([cadastros.empresa("Beta", "BET").pk])

    with pytest.raises(AcessoNegado):
        selectors.obter_iniciativa(escopo, iniciativa.pk)
    with pytest.raises(AcessoNegado):
        services.criar_iniciativa(objetivo_id=objetivo.pk, dados={}, ator=ATOR, escopo=escopo)


def test_responsabilidades_incluem_iniciativas(alfa, objetivo):
    alfa.iniciativa(objetivo, responsavel=alfa.ana)

    assert [
        i.titulo for i in selectors.responsabilidades_da_pessoa(TODAS, alfa.ana)["iniciativas"]
    ] == ["Campanha de vendas"]


# ------------------------------------------------- atualizações de execução


def atualizar(iniciativa, **dados):
    base = {
        "data_referencia": HOJE,
        "status": "em_andamento",
        "comentario": "Iniciada",
        "autor_informado": iniciativa.responsavel,
    }
    base.update(dados)
    return acompanhamento.registrar_atualizacao(
        iniciativa_id=iniciativa.pk, dados=base, ator=ATOR, escopo=TODAS, hoje=HOJE
    )


def test_atualizacao_registra_e_muda_status_da_iniciativa(alfa, objetivo):
    iniciativa = alfa.iniciativa(objetivo)

    atualizacao = atualizar(iniciativa, dificuldades="Fornecedor atrasou")

    iniciativa.refresh_from_db()
    assert iniciativa.status == "em_andamento"
    assert atualizacao.dificuldades == "Fornecedor atrasou"
    assert not atualizacao.autor_verificado
    alteracao = historico_do_objeto(iniciativa).filter(acao=Acao.ALTERACAO).get()
    assert alteracao.alteracoes["status"] == {"antes": "nao_iniciada", "depois": "em_andamento"}


def test_atualizacao_e_imutavel(alfa, objetivo):
    atualizacao = atualizar(alfa.iniciativa(objetivo))

    with pytest.raises(RegistroImutavel):
        atualizacao.save()
    with pytest.raises(RegistroImutavel):
        AtualizacaoIniciativa.objects.all().delete()


def test_atualizacao_valida_data_status_e_autor(alfa, objetivo):
    iniciativa = alfa.iniciativa(objetivo)
    externa = cadastros.pessoa(nome="Externa", empresas=[cadastros.empresa("Beta", "BET")])

    with pytest.raises(ValidationError) as erro:
        atualizar(iniciativa, data_referencia=date(2026, 6, 16), status="", autor_informado=externa)

    assert {"data_referencia", "status", "autor_informado"} <= set(erro.value.message_dict)


def test_iniciativa_cancelada_nao_recebe_atualizacao(alfa, objetivo):
    iniciativa = alfa.iniciativa(objetivo, status="cancelada")

    with pytest.raises(ErroDeNegocio, match="cancelada"):
        atualizar(iniciativa)


def test_historico_de_execucao_em_ordem(alfa, objetivo):
    iniciativa = alfa.iniciativa(objetivo)
    atualizar(iniciativa, data_referencia=date(2026, 6, 1), comentario="Primeira")
    atualizar(iniciativa, data_referencia=date(2026, 6, 10), comentario="Segunda")

    comentarios = [
        a.comentario for a in acompanhamento_selectors.atualizacoes_da_iniciativa(iniciativa)
    ]

    assert comentarios == ["Segunda", "Primeira"]


# ---------------------------------------------------------------- telas


def test_fluxo_de_iniciativa_pelas_telas(client, alfa, objetivo, monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: HOJE)
    kr = alfa.kr(objetivo, valor_inicial=D("1"), meta=D("2"))

    form = client.get(
        reverse("okrs:iniciativa_nova", args=[objetivo.pk]), {"kr": kr.pk}
    ).content.decode()
    assert 'name="owner"' not in form and "checked" in form  # KR de origem pré-selecionado

    resposta = client.post(
        reverse("okrs:iniciativa_nova", args=[objetivo.pk]),
        {
            "titulo": "Treinar equipe",
            "descricao": "",
            "responsavel": alfa.bruno.pk,
            "prazo": "2026-06-01",
            "status": "nao_iniciada",
            "krs": [kr.pk],
        },
        follow=True,
    )
    iniciativa = Iniciativa.objects.get()
    conteudo = resposta.content.decode()
    assert "Iniciativa cadastrada." in conteudo
    assert "Prazo vencido em 01/06/2026" in conteudo

    resposta = client.post(
        reverse("acompanhamento:atualizacao_nova", args=[iniciativa.pk]),
        {
            "data_referencia": "2026-06-15",
            "status": "concluida",
            "comentario": "Treinamento realizado",
            "dificuldades": "",
            "proximos_passos": "",
            "autor_informado": alfa.bruno.pk,
        },
        follow=True,
    )
    conteudo = resposta.content.decode()
    assert "Atualização registrada." in conteudo
    assert "Treinamento realizado" in conteudo
    assert "registrado por Admin Teste" in conteudo

    objetivo_html = client.get(
        reverse("okrs:objetivo_detalhe", args=[objetivo.pk])
    ).content.decode()
    kr_html = client.get(reverse("okrs:kr_detalhe", args=[kr.pk])).content.decode()
    assert "Treinar equipe" in objetivo_html and "Concluída" in objetivo_html
    assert "Treinar equipe" in kr_html


def test_iniciativa_inexistente_retorna_404(client):
    assert client.get(reverse("okrs:iniciativa_detalhe", args=[999])).status_code == 404
    assert client.get(reverse("acompanhamento:atualizacao_nova", args=[999])).status_code == 404
