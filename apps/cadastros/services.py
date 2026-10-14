"""Regras de gravação de empresas e pessoas."""

from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.auditoria.models import RegistroAlteracao
from apps.auditoria.services import registrar_alteracao
from apps.cadastros import selectors
from apps.cadastros.models import Empresa, Pessoa, VinculoPessoaEmpresa
from apps.core import services
from apps.core.acesso import Ator, EscopoAcesso
from apps.core.erros import ErroDeNegocio, PermissaoNegada

Acao = RegistroAlteracao.Acao


def _gravar_protegido(funcao, mensagem_duplicidade: str):
    """Converte violação de unicidade do banco (corrida entre duas gravações) em erro amigável."""
    try:
        with transaction.atomic():
            return funcao()
    except IntegrityError as exc:
        raise ErroDeNegocio(mensagem_duplicidade) from exc


# ---------------------------------------------------------------- empresas


def criar_empresa(*, nome: str, sigla: str, ator: Ator, escopo: EscopoAcesso) -> Empresa:
    if not escopo.irrestrito:
        raise PermissaoNegada("Somente administradores podem cadastrar empresas.")
    return _gravar_protegido(
        lambda: services.criar(Empresa(nome=nome, sigla=sigla), ator=ator),
        "Já existe uma empresa com este nome ou sigla.",
    )


def atualizar_empresa(
    empresa_id: int, *, nome: str, sigla: str, versao: int, ator: Ator, escopo: EscopoAcesso
) -> Empresa:
    empresa = selectors.obter_empresa(escopo, empresa_id)
    return _gravar_protegido(
        lambda: services.atualizar(
            empresa, {"nome": nome, "sigla": sigla}, versao_esperada=versao, ator=ator
        ),
        "Já existe uma empresa com este nome ou sigla.",
    )


def arquivar_empresa(empresa_id: int, *, versao: int, ator: Ator, escopo: EscopoAcesso) -> Empresa:
    empresa = selectors.obter_empresa(escopo, empresa_id)
    return services.arquivar(empresa, versao_esperada=versao, ator=ator)


def reativar_empresa(empresa_id: int, *, versao: int, ator: Ator, escopo: EscopoAcesso) -> Empresa:
    empresa = selectors.obter_empresa(escopo, empresa_id)
    return services.reativar(empresa, versao_esperada=versao, ator=ator)


# ----------------------------------------------------------------- pessoas


def _validar_empresas_selecionadas(
    selecionadas: set[int], *, ja_vinculadas: set[int], escopo: EscopoAcesso
) -> dict[int, Empresa]:
    """Confere se as empresas existem, estão no escopo e, se novas, estão ativas."""
    empresas = {e.pk: e for e in escopo.filtrar(Empresa.objects.filter(pk__in=selecionadas), "id")}
    if set(empresas) != selecionadas:
        raise ValidationError({"empresas": "Selecione apenas empresas disponíveis."})
    arquivadas_novas = [
        e.sigla for pk, e in empresas.items() if e.arquivado and pk not in ja_vinculadas
    ]
    if arquivadas_novas:
        siglas = ", ".join(arquivadas_novas)
        raise ValidationError(
            {"empresas": f"Empresa arquivada não pode receber novos vínculos: {siglas}."}
        )
    return empresas


def _vincular(pessoa: Pessoa, empresa: Empresa, ator: Ator) -> None:
    VinculoPessoaEmpresa.objects.create(pessoa=pessoa, empresa=empresa)
    registrar_alteracao(
        objeto=pessoa,
        acao=Acao.VINCULO,
        ator=ator,
        alteracoes={"empresa": {"antes": None, "depois": str(empresa)}},
        empresa_id=empresa.pk,
    )


def _desvincular(pessoa: Pessoa, empresa: Empresa, ator: Ator) -> None:
    VinculoPessoaEmpresa.objects.filter(pessoa=pessoa, empresa=empresa).delete()
    registrar_alteracao(
        objeto=pessoa,
        acao=Acao.DESVINCULO,
        ator=ator,
        alteracoes={"empresa": {"antes": str(empresa), "depois": None}},
        empresa_id=empresa.pk,
    )


def criar_pessoa(
    *,
    nome: str,
    email: str | None,
    empresas_ids: Iterable[int],
    ator: Ator,
    escopo: EscopoAcesso,
) -> Pessoa:
    selecionadas = set(empresas_ids)
    if not selecionadas:
        raise ValidationError({"empresas": "Selecione ao menos uma empresa."})
    empresas = _validar_empresas_selecionadas(selecionadas, ja_vinculadas=set(), escopo=escopo)

    def gravar():
        pessoa = services.criar(Pessoa(nome=nome, email=email), ator=ator)
        for empresa in sorted(empresas.values(), key=lambda e: e.sigla):
            _vincular(pessoa, empresa, ator)
        return pessoa

    return _gravar_protegido(gravar, "Já existe uma pessoa com este e-mail.")


def atualizar_pessoa(
    pessoa_id: int,
    *,
    nome: str,
    email: str | None,
    empresas_ids: Iterable[int],
    versao: int,
    ator: Ator,
    escopo: EscopoAcesso,
) -> Pessoa:
    """Atualiza dados e vínculos. Vínculos com empresas fora do escopo de quem
    edita são preservados (não aparecem para essa pessoa, então não podem ser
    removidos por ela)."""
    pessoa = selectors.obter_pessoa(escopo, pessoa_id)
    atuais = set(pessoa.vinculos.values_list("empresa_id", flat=True))
    fora_do_escopo = {pk for pk in atuais if not escopo.permite(pk)}
    selecionadas = set(empresas_ids)
    empresas = _validar_empresas_selecionadas(selecionadas, ja_vinculadas=atuais, escopo=escopo)

    finais = fora_do_escopo | selecionadas
    if not finais:
        raise ValidationError({"empresas": "Selecione ao menos uma empresa."})
    adicionar = selecionadas - atuais
    remover = (atuais - fora_do_escopo) - selecionadas

    def gravar():
        versao_antes = pessoa.versao
        atualizada = services.atualizar(
            pessoa, {"nome": nome, "email": email}, versao_esperada=versao, ator=ator
        )
        if (adicionar or remover) and atualizada.versao == versao_antes:
            services.confirmar_versao(atualizada, versao)
        for empresa in Empresa.objects.filter(pk__in=remover).order_by("sigla"):
            _desvincular(atualizada, empresa, ator)
        for pk in sorted(adicionar, key=lambda pk: empresas[pk].sigla):
            _vincular(atualizada, empresas[pk], ator)
        return atualizada

    return _gravar_protegido(gravar, "Já existe uma pessoa com este e-mail.")


def arquivar_pessoa(pessoa_id: int, *, versao: int, ator: Ator, escopo: EscopoAcesso) -> Pessoa:
    pessoa = selectors.obter_pessoa(escopo, pessoa_id)
    return services.arquivar(pessoa, versao_esperada=versao, ator=ator)


def reativar_pessoa(pessoa_id: int, *, versao: int, ator: Ator, escopo: EscopoAcesso) -> Pessoa:
    pessoa = selectors.obter_pessoa(escopo, pessoa_id)
    return services.reativar(pessoa, versao_esperada=versao, ator=ator)
