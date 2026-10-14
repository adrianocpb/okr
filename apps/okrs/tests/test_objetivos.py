import pytest
from django.core.exceptions import ValidationError

from apps.auditoria.models import RegistroAlteracao
from apps.auditoria.selectors import historico_legivel
from apps.auditoria.services import historico_do_objeto
from apps.cadastros import services as cadastros_services
from apps.cadastros.tests import fabricas as cadastros
from apps.cadastros.tests.fabricas import ATOR, TODAS
from apps.core.acesso import EscopoAcesso
from apps.core.erros import AcessoNegado, ConflitoDeVersao, ErroDeNegocio
from apps.okrs import selectors, services
from apps.okrs.models import Objetivo, VinculoObjetivo
from apps.okrs.tests.fabricas import Cenario

pytestmark = pytest.mark.django_db
Acao = RegistroAlteracao.Acao


@pytest.fixture
def alfa():
    return Cenario()


# --------------------------------------------------------------- criação


def test_criar_objetivo_com_owner_e_sponsor(alfa):
    objetivo = alfa.objetivo(titulo="  Crescer   receita ", descricao="Meta do ano")

    assert objetivo.titulo == "Crescer receita"
    assert (objetivo.owner, objetivo.sponsor) == (alfa.ana, alfa.bruno)
    assert objetivo.empresa == alfa.empresa
    registro = historico_do_objeto(objetivo).get()
    assert registro.acao == Acao.CRIACAO
    assert registro.empresa_id == alfa.empresa.pk


def test_owner_e_sponsor_sao_obrigatorios(alfa):
    objetivo = Objetivo(empresa=alfa.empresa, ciclo=alfa.anual, titulo="X")

    with pytest.raises(ValidationError) as erro:
        objetivo.full_clean()

    assert {"owner", "sponsor"} <= set(erro.value.message_dict)


def test_owner_e_sponsor_podem_ser_a_mesma_pessoa(alfa):
    objetivo = alfa.objetivo(owner=alfa.ana, sponsor=alfa.ana)

    assert objetivo.mesma_pessoa_owner_sponsor


def test_responsavel_precisa_estar_vinculado_a_empresa(alfa):
    beta = cadastros.empresa(nome="Beta", sigla="BET")
    de_fora = cadastros.pessoa(nome="Carla", empresas=[beta])

    with pytest.raises(ValidationError) as erro:
        alfa.objetivo(owner=de_fora)

    assert erro.value.message_dict["owner"] == [
        "A pessoa precisa estar vinculada à empresa do objetivo."
    ]


def test_pessoa_arquivada_nao_recebe_nova_responsabilidade(alfa):
    cadastros_services.arquivar_pessoa(alfa.bruno.pk, versao=1, ator=ATOR, escopo=TODAS)
    alfa.bruno.refresh_from_db()

    with pytest.raises(ValidationError) as erro:
        alfa.objetivo(sponsor=alfa.bruno)

    assert "arquivada" in erro.value.message_dict["sponsor"][0]


def test_responsavel_arquivado_depois_nao_impede_editar_outros_campos(alfa):
    objetivo = alfa.objetivo()
    cadastros_services.arquivar_pessoa(alfa.bruno.pk, versao=1, ator=ATOR, escopo=TODAS)

    objetivo = services.atualizar_objetivo(
        objetivo.pk, dados={"titulo": "Novo título"}, versao=1, ator=ATOR, escopo=TODAS
    )

    assert objetivo.titulo == "Novo título"


def test_ciclo_deve_ser_da_mesma_empresa(alfa):
    beta = Cenario(nome="Beta", sigla="BET")

    with pytest.raises(ValidationError) as erro:
        alfa.objetivo(ciclo=beta.anual)

    assert erro.value.message_dict["ciclo"] == ["O ciclo deve ser da mesma empresa do objetivo."]


def test_ciclo_arquivado_nao_recebe_objetivo(alfa):
    cadastros_services.arquivar_ciclo(alfa.t2.pk, versao=1, ator=ATOR, escopo=TODAS)
    alfa.t2.refresh_from_db()

    with pytest.raises(ValidationError) as erro:
        alfa.objetivo(ciclo=alfa.t2)

    assert "arquivado" in erro.value.message_dict["ciclo"][0]


def test_empresa_arquivada_nao_recebe_objetivo(alfa):
    outra = cadastros.empresa(nome="Gama", sigla="GAM")
    cadastros_services.arquivar_empresa(outra.pk, versao=1, ator=ATOR, escopo=TODAS)

    with pytest.raises(ErroDeNegocio, match="arquivada"):
        services.criar_objetivo(empresa_id=outra.pk, dados={"titulo": "X"}, ator=ATOR, escopo=TODAS)


@pytest.mark.parametrize("status", ["concluido", "cancelado"])
def test_concluir_ou_cancelar_exige_comentario(alfa, status):
    objetivo = alfa.objetivo()

    with pytest.raises(ValidationError) as erro:
        services.atualizar_objetivo(
            objetivo.pk, dados={"status": status}, versao=1, ator=ATOR, escopo=TODAS
        )
    assert "comentario_status" in erro.value.message_dict

    objetivo = services.atualizar_objetivo(
        objetivo.pk,
        dados={"status": status, "comentario_status": "Motivo informado"},
        versao=1,
        ator=ATOR,
        escopo=TODAS,
    )
    assert objetivo.status == status


# ------------------------------------------------------------ alteração


def test_troca_de_owner_fica_no_historico_com_nomes(alfa):
    objetivo = alfa.objetivo()

    services.atualizar_objetivo(
        objetivo.pk, dados={"owner": alfa.bruno}, versao=1, ator=ATOR, escopo=TODAS
    )

    registro = historico_do_objeto(objetivo).filter(acao=Acao.ALTERACAO).get()
    assert registro.alteracoes == {"owner": {"antes": alfa.ana.pk, "depois": alfa.bruno.pk}}
    mudanca = historico_legivel(objetivo)[0].mudancas[0]
    assert (mudanca.campo, mudanca.antes, mudanca.depois) == ("Owner", "Ana ALF", "Bruno ALF")


def test_edicao_concorrente_e_recusada(alfa):
    objetivo = alfa.objetivo()
    services.atualizar_objetivo(
        objetivo.pk, dados={"titulo": "A"}, versao=1, ator=ATOR, escopo=TODAS
    )

    with pytest.raises(ConflitoDeVersao):
        services.atualizar_objetivo(
            objetivo.pk, dados={"titulo": "B"}, versao=1, ator=ATOR, escopo=TODAS
        )


def test_empresa_do_objetivo_nao_muda(alfa):
    objetivo = alfa.objetivo()
    beta = cadastros.empresa(nome="Beta", sigla="BET")

    objetivo = services.atualizar_objetivo(
        objetivo.pk, dados={"empresa": beta, "titulo": "Y"}, versao=1, ator=ATOR, escopo=TODAS
    )

    assert objetivo.empresa == alfa.empresa


# --------------------------------------------------------------- vínculos


def test_objetivo_trimestral_pode_existir_sem_vinculo(alfa):
    trimestral = alfa.objetivo(titulo="Lançar produto", ciclo=alfa.t1)

    assert not VinculoObjetivo.objects.filter(objetivo_trimestral=trimestral).exists()


def test_vincular_trimestral_a_varios_anuais_e_auditar_nos_dois(alfa):
    anual_a = alfa.objetivo(titulo="Anual A")
    anual_b = alfa.objetivo(titulo="Anual B")
    trimestral = alfa.objetivo(titulo="Trimestral", ciclo=alfa.t1)

    for anual in (anual_a, anual_b):
        services.vincular(
            objetivo_trimestral_id=trimestral.pk,
            objetivo_anual_id=anual.pk,
            ator=ATOR,
            escopo=TODAS,
        )

    vinculos = selectors.vinculos_do_objetivo(trimestral)
    assert {v.objetivo_anual.titulo for v in vinculos["anuais"]} == {"Anual A", "Anual B"}
    assert historico_do_objeto(anual_a).filter(acao=Acao.VINCULO).exists()
    assert historico_do_objeto(trimestral).filter(acao=Acao.VINCULO).count() == 2


def test_vinculo_entre_empresas_diferentes_e_recusado(alfa):
    beta = Cenario(nome="Beta", sigla="BET")
    anual_beta = beta.objetivo(titulo="Anual Beta")
    trimestral = alfa.objetivo(titulo="Trimestral", ciclo=alfa.t1)

    with pytest.raises(ValidationError, match="mesma empresa"):
        services.vincular(
            objetivo_trimestral_id=trimestral.pk,
            objetivo_anual_id=anual_beta.pk,
            ator=ATOR,
            escopo=TODAS,
        )


def test_vinculo_exige_trimestre_do_mesmo_ano(alfa):
    anual_2027 = cadastros.ciclo_anual(alfa.empresa, 2027)
    objetivo_2027 = alfa.objetivo(titulo="Anual 2027", ciclo=anual_2027)
    trimestral = alfa.objetivo(titulo="Trimestral 2026", ciclo=alfa.t1)

    with pytest.raises(ValidationError, match="ciclo anual"):
        services.vincular(
            objetivo_trimestral_id=trimestral.pk,
            objetivo_anual_id=objetivo_2027.pk,
            ator=ATOR,
            escopo=TODAS,
        )


def test_vinculo_exige_anual_e_trimestral_na_ordem_certa(alfa):
    anual = alfa.objetivo(titulo="Anual")
    outro_anual = alfa.objetivo(titulo="Outro anual")

    with pytest.raises(ValidationError, match="trimestral"):
        services.vincular(
            objetivo_trimestral_id=outro_anual.pk,
            objetivo_anual_id=anual.pk,
            ator=ATOR,
            escopo=TODAS,
        )


def test_vinculo_duplicado_e_recusado(alfa):
    anual = alfa.objetivo(titulo="Anual")
    trimestral = alfa.objetivo(titulo="Trimestral", ciclo=alfa.t1)
    argumentos = {
        "objetivo_trimestral_id": trimestral.pk,
        "objetivo_anual_id": anual.pk,
        "ator": ATOR,
        "escopo": TODAS,
    }
    services.vincular(**argumentos)

    with pytest.raises(ValidationError, match="já estão vinculados"):
        services.vincular(**argumentos)


def test_desvincular_remove_e_registra_no_historico(alfa):
    anual = alfa.objetivo(titulo="Anual")
    trimestral = alfa.objetivo(titulo="Trimestral", ciclo=alfa.t1)
    vinculo = services.vincular(
        objetivo_trimestral_id=trimestral.pk, objetivo_anual_id=anual.pk, ator=ATOR, escopo=TODAS
    )

    services.desvincular(vinculo.pk, ator=ATOR, escopo=TODAS)

    assert not VinculoObjetivo.objects.exists()
    assert historico_do_objeto(trimestral).filter(acao=Acao.DESVINCULO).exists()
    assert historico_do_objeto(anual).filter(acao=Acao.DESVINCULO).exists()


def test_trocar_ciclo_com_vinculos_e_recusado(alfa):
    anual = alfa.objetivo(titulo="Anual")
    trimestral = alfa.objetivo(titulo="Trimestral", ciclo=alfa.t1)
    services.vincular(
        objetivo_trimestral_id=trimestral.pk, objetivo_anual_id=anual.pk, ator=ATOR, escopo=TODAS
    )

    with pytest.raises(ValidationError) as erro:
        services.atualizar_objetivo(
            trimestral.pk, dados={"ciclo": alfa.t2}, versao=1, ator=ATOR, escopo=TODAS
        )

    assert "Remova os vínculos" in erro.value.message_dict["ciclo"][0]


def test_anuais_vinculaveis_exclui_ja_vinculados_e_cancelados(alfa):
    disponivel = alfa.objetivo(titulo="Disponível")
    ja_vinculado = alfa.objetivo(titulo="Já vinculado")
    alfa.objetivo(titulo="Cancelado", status="cancelado", comentario_status="Sem prioridade")
    trimestral = alfa.objetivo(titulo="Trimestral", ciclo=alfa.t1)
    services.vincular(
        objetivo_trimestral_id=trimestral.pk,
        objetivo_anual_id=ja_vinculado.pk,
        ator=ATOR,
        escopo=TODAS,
    )

    assert list(selectors.anuais_vinculaveis(trimestral)) == [disponivel]
    assert not selectors.anuais_vinculaveis(disponivel).exists()  # anual não vincula


# --------------------------------------------------------------- consulta


def test_escopo_restrito_nao_ve_objetivos_de_outra_empresa(alfa):
    beta = Cenario(nome="Beta", sigla="BET")
    objetivo_beta = beta.objetivo(titulo="Da Beta")
    alfa.objetivo(titulo="Da Alfa")
    escopo = EscopoAcesso.restrito([alfa.empresa.pk])

    assert [o.titulo for o in selectors.listar_objetivos(escopo)] == ["Da Alfa"]
    with pytest.raises(AcessoNegado):
        selectors.obter_objetivo(escopo, objetivo_beta.pk)
    with pytest.raises(AcessoNegado):
        services.atualizar_objetivo(
            objetivo_beta.pk, dados={"titulo": "X"}, versao=1, ator=ATOR, escopo=escopo
        )


def test_filtros_de_objetivos(alfa):
    alfa.objetivo(titulo="Expandir operação")
    alfa.objetivo(titulo="Reduzir custos", ciclo=alfa.t1, status="rascunho")

    def titulos(**filtros):
        return [o.titulo for o in selectors.listar_objetivos(TODAS, **filtros)]

    assert titulos(ciclo_id=alfa.t1.pk) == ["Reduzir custos"]
    assert titulos(status="rascunho") == ["Reduzir custos"]
    assert titulos(busca="operacao") == ["Expandir operação"]


def test_responsabilidades_da_pessoa(alfa):
    alfa.objetivo(titulo="Objetivo 1", owner=alfa.ana, sponsor=alfa.bruno)
    alfa.objetivo(titulo="Objetivo 2", owner=alfa.bruno, sponsor=alfa.ana)

    papeis = selectors.responsabilidades_da_pessoa(TODAS, alfa.ana)

    assert [o.titulo for o in papeis["owner"]] == ["Objetivo 1"]
    assert [o.titulo for o in papeis["sponsor"]] == ["Objetivo 2"]
