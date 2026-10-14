import pytest
from django.core.exceptions import ValidationError

from apps.auditoria.models import RegistroAlteracao
from apps.auditoria.services import historico_do_objeto
from apps.cadastros import selectors, services
from apps.cadastros.models import Empresa, Pessoa
from apps.cadastros.tests import fabricas
from apps.cadastros.tests.fabricas import ATOR, TODAS
from apps.core.acesso import EscopoAcesso
from apps.core.erros import AcessoNegado, ConflitoDeVersao, PermissaoNegada

pytestmark = pytest.mark.django_db
Acao = RegistroAlteracao.Acao


# ---------------------------------------------------------------- empresas


def test_criar_empresa_normaliza_e_audita():
    empresa = fabricas.empresa(nome="  Empresa   Alfa ", sigla=" alf ")

    assert empresa.nome == "Empresa Alfa"
    assert empresa.sigla == "ALF"
    registro = historico_do_objeto(empresa).get()
    assert registro.acao == Acao.CRIACAO
    assert registro.empresa_id == empresa.pk
    assert "chave_nome" not in registro.alteracoes  # campo derivado não é auditado


@pytest.mark.parametrize(
    "nome_repetido", ["empresa alfa", "EMPRESA ALFA", "Émpresa Alfá", " Empresa  Alfa "]
)
def test_nome_de_empresa_e_unico_sem_distinguir_maiusculas_e_acentos(nome_repetido):
    fabricas.empresa(nome="Empresa Alfa", sigla="ALF")

    with pytest.raises(ValidationError) as erro:
        fabricas.empresa(nome=nome_repetido, sigla="OUT")

    assert erro.value.message_dict == {"nome": ["Já existe uma empresa com este nome."]}


def test_sigla_e_unica_sem_distinguir_maiusculas():
    fabricas.empresa(nome="Alfa", sigla="ALF")

    with pytest.raises(ValidationError) as erro:
        fabricas.empresa(nome="Outra", sigla="alf")

    assert erro.value.message_dict == {"sigla": ["Já existe uma empresa com esta sigla."]}


def test_atualizar_empresa_registra_antes_e_depois():
    empresa = fabricas.empresa()

    empresa = services.atualizar_empresa(
        empresa.pk, nome="Alfa Participações", sigla="ALF", versao=1, ator=ATOR, escopo=TODAS
    )

    registro = historico_do_objeto(empresa).filter(acao=Acao.ALTERACAO).get()
    assert registro.alteracoes == {
        "nome": {"antes": "Empresa Alfa", "depois": "Alfa Participações"}
    }
    assert empresa.chave_nome == "alfa participacoes"


def test_atualizar_empresa_com_versao_antiga_e_recusado():
    empresa = fabricas.empresa()
    services.atualizar_empresa(empresa.pk, nome="A", sigla="ALF", versao=1, ator=ATOR, escopo=TODAS)

    with pytest.raises(ConflitoDeVersao):
        services.atualizar_empresa(
            empresa.pk, nome="B", sigla="ALF", versao=1, ator=ATOR, escopo=TODAS
        )

    assert Empresa.objects.get(pk=empresa.pk).nome == "A"


def test_arquivar_empresa_nao_exclui_e_some_das_ativas():
    empresa = fabricas.empresa()

    services.arquivar_empresa(empresa.pk, versao=1, ator=ATOR, escopo=TODAS)

    assert Empresa.objects.filter(pk=empresa.pk).exists()
    assert not selectors.listar_empresas(TODAS).exists()
    assert selectors.listar_empresas(TODAS, situacao="arquivadas").count() == 1
    assert not selectors.empresas_para_vinculo(TODAS).exists()


def test_busca_de_empresa_ignora_acentos_e_maiusculas():
    fabricas.empresa(nome="Água Viva Indústria", sigla="AVI")
    fabricas.empresa(nome="Outra", sigla="OUT")

    assert [e.sigla for e in selectors.listar_empresas(TODAS, busca="agua")] == ["AVI"]
    assert [e.sigla for e in selectors.listar_empresas(TODAS, busca="INDUSTRIA")] == ["AVI"]
    assert [e.sigla for e in selectors.listar_empresas(TODAS, busca="avi")] == ["AVI"]


def test_escopo_restrito_nao_cria_empresa():
    with pytest.raises(PermissaoNegada):
        services.criar_empresa(nome="X", sigla="X", ator=ATOR, escopo=EscopoAcesso.restrito([1]))


def test_escopo_restrito_nao_ve_nem_altera_empresa_de_fora():
    a = fabricas.empresa(nome="A", sigla="A")
    b = fabricas.empresa(nome="B", sigla="B")
    escopo_a = EscopoAcesso.restrito([a.pk])

    assert [e.pk for e in selectors.listar_empresas(escopo_a)] == [a.pk]
    with pytest.raises(AcessoNegado):
        selectors.obter_empresa(escopo_a, b.pk)
    with pytest.raises(AcessoNegado):
        services.atualizar_empresa(b.pk, nome="Z", sigla="B", versao=1, ator=ATOR, escopo=escopo_a)
    with pytest.raises(AcessoNegado):
        services.arquivar_empresa(b.pk, versao=1, ator=ATOR, escopo=escopo_a)


# ----------------------------------------------------------------- pessoas


def test_pessoa_pode_pertencer_a_varias_empresas_e_vinculos_sao_auditados():
    a = fabricas.empresa(nome="A", sigla="A")
    b = fabricas.empresa(nome="B", sigla="B")

    pessoa = fabricas.pessoa(email="Fulana@Exemplo.com", empresas=[a, b])

    assert pessoa.email == "fulana@exemplo.com"
    assert set(pessoa.empresas.values_list("sigla", flat=True)) == {"A", "B"}
    vinculos = historico_do_objeto(pessoa).filter(acao=Acao.VINCULO)
    assert sorted(vinculos.values_list("empresa_id", flat=True)) == sorted([a.pk, b.pk])


def test_pessoa_exige_ao_menos_uma_empresa():
    with pytest.raises(ValidationError) as erro:
        fabricas.pessoa(empresas=[])

    assert "empresas" in erro.value.message_dict
    assert not Pessoa.objects.exists()


def test_email_de_pessoa_e_unico_e_opcional():
    a = fabricas.empresa()
    fabricas.pessoa(nome="Sem e-mail 1", empresas=[a])
    fabricas.pessoa(nome="Sem e-mail 2", empresas=[a])  # vários sem e-mail são permitidos
    fabricas.pessoa(nome="Com e-mail", email="x@exemplo.com", empresas=[a])

    with pytest.raises(ValidationError) as erro:
        fabricas.pessoa(nome="Outra", email="X@EXEMPLO.COM", empresas=[a])

    assert erro.value.message_dict == {"email": ["Já existe uma pessoa com este e-mail."]}


def test_empresa_arquivada_nao_recebe_novos_vinculos():
    a = fabricas.empresa()
    services.arquivar_empresa(a.pk, versao=1, ator=ATOR, escopo=TODAS)

    with pytest.raises(ValidationError, match="arquivada"):
        fabricas.pessoa(empresas=[Empresa.objects.get(pk=a.pk)])


def test_vinculo_existente_com_empresa_arquivada_e_mantido_ao_editar():
    a = fabricas.empresa(nome="A", sigla="A")
    pessoa = fabricas.pessoa(empresas=[a])
    services.arquivar_empresa(a.pk, versao=1, ator=ATOR, escopo=TODAS)

    pessoa = services.atualizar_pessoa(
        pessoa.pk,
        nome="Novo Nome",
        email=None,
        empresas_ids=[a.pk],
        versao=1,
        ator=ATOR,
        escopo=TODAS,
    )

    assert pessoa.nome == "Novo Nome"
    assert list(pessoa.empresas.values_list("sigla", flat=True)) == ["A"]


def test_alterar_somente_vinculos_incrementa_versao_e_audita():
    a = fabricas.empresa(nome="A", sigla="A")
    b = fabricas.empresa(nome="B", sigla="B")
    pessoa = fabricas.pessoa(empresas=[a])

    pessoa = services.atualizar_pessoa(
        pessoa.pk,
        nome=pessoa.nome,
        email=None,
        empresas_ids=[b.pk],
        versao=1,
        ator=ATOR,
        escopo=TODAS,
    )

    assert pessoa.versao == 2
    assert list(pessoa.empresas.values_list("sigla", flat=True)) == ["B"]
    acoes = list(historico_do_objeto(pessoa).order_by("id").values_list("acao", "empresa_id"))
    assert acoes[-2:] == [(Acao.DESVINCULO, a.pk), (Acao.VINCULO, b.pk)]
    with pytest.raises(ConflitoDeVersao):
        services.atualizar_pessoa(
            pessoa.pk, nome="X", email=None, empresas_ids=[b.pk], versao=1, ator=ATOR, escopo=TODAS
        )


def test_edicao_com_escopo_restrito_preserva_vinculos_fora_do_escopo():
    a = fabricas.empresa(nome="A", sigla="A")
    b = fabricas.empresa(nome="B", sigla="B")
    c = fabricas.empresa(nome="C", sigla="C")
    pessoa = fabricas.pessoa(empresas=[a, b])
    escopo_a_c = EscopoAcesso.restrito([a.pk, c.pk])

    services.atualizar_pessoa(
        pessoa.pk,
        nome=pessoa.nome,
        email=None,
        empresas_ids=[c.pk],
        versao=1,
        ator=ATOR,
        escopo=escopo_a_c,
    )

    assert set(Pessoa.objects.get(pk=pessoa.pk).empresas.values_list("sigla", flat=True)) == {
        "B",
        "C",
    }


def test_escopo_restrito_nao_vincula_empresa_de_fora():
    a = fabricas.empresa(nome="A", sigla="A")
    b = fabricas.empresa(nome="B", sigla="B")

    with pytest.raises(ValidationError):
        services.criar_pessoa(
            nome="X",
            email=None,
            empresas_ids=[b.pk],
            ator=ATOR,
            escopo=EscopoAcesso.restrito([a.pk]),
        )


def test_escopo_restrito_ve_somente_pessoas_de_suas_empresas():
    a = fabricas.empresa(nome="A", sigla="A")
    b = fabricas.empresa(nome="B", sigla="B")
    da_a = fabricas.pessoa(nome="Pessoa da A", empresas=[a])
    da_b = fabricas.pessoa(nome="Pessoa da B", empresas=[b])
    das_duas = fabricas.pessoa(nome="Pessoa das duas", empresas=[a, b])
    escopo_a = EscopoAcesso.restrito([a.pk])

    visiveis = {p.pk for p in selectors.listar_pessoas(escopo_a)}
    assert visiveis == {da_a.pk, das_duas.pk}
    with pytest.raises(AcessoNegado):
        selectors.obter_pessoa(escopo_a, da_b.pk)
    # Empresas exibidas para quem tem escopo restrito: só as do escopo.
    assert [e.sigla for e in selectors.obter_pessoa(escopo_a, das_duas.pk).empresas_visiveis] == [
        "A"
    ]


def test_busca_de_pessoa_ignora_acentos_e_filtra_por_empresa():
    a = fabricas.empresa(nome="A", sigla="A")
    b = fabricas.empresa(nome="B", sigla="B")
    fabricas.pessoa(nome="José Antônio", empresas=[a])
    fabricas.pessoa(nome="Maria", email="maria@exemplo.com", empresas=[b])

    assert [p.nome for p in selectors.listar_pessoas(TODAS, busca="jose antonio")] == [
        "José Antônio"
    ]
    assert [p.nome for p in selectors.listar_pessoas(TODAS, busca="MARIA@")] == ["Maria"]
    assert [p.nome for p in selectors.listar_pessoas(TODAS, empresa_id=b.pk)] == ["Maria"]


def test_arquivar_e_reativar_pessoa():
    pessoa = fabricas.pessoa(empresas=[fabricas.empresa()])

    services.arquivar_pessoa(pessoa.pk, versao=1, ator=ATOR, escopo=TODAS)
    assert not selectors.listar_pessoas(TODAS).exists()

    services.reativar_pessoa(pessoa.pk, versao=2, ator=ATOR, escopo=TODAS)
    assert selectors.listar_pessoas(TODAS).count() == 1
