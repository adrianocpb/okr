"""Operações genéricas de gravação com auditoria e bloqueio otimista.

Os services de cada módulo usam estas funções para que toda gravação:
- valide o modelo (`full_clean`);
- seja recusada se a versão editada estiver desatualizada (ConflitoDeVersao);
- registre a auditoria na mesma transação (falha na auditoria desfaz tudo).
"""

from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from apps.auditoria.models import RegistroAlteracao
from apps.auditoria.services import registrar_alteracao, valor_auditavel
from apps.core.acesso import Ator
from apps.core.erros import ConflitoDeVersao, ErroDeNegocio
from apps.core.models import ModeloArquivavel, ModeloBase

CAMPOS_DE_CONTROLE = {"id", "criado_em", "atualizado_em", "versao", "arquivado_em"}

Acao = RegistroAlteracao.Acao


def _empresa_id(objeto: models.Model, empresa_id: int | None) -> int | None:
    if empresa_id is not None:
        return empresa_id
    return getattr(objeto, "empresa_id", None)


def _iguais(antes, depois) -> bool:
    if isinstance(antes, models.Model) or isinstance(depois, models.Model):
        return valor_auditavel(antes) == valor_auditavel(depois)
    return antes == depois


def _campos_auditaveis(objeto: models.Model):
    for campo in objeto._meta.concrete_fields:
        if campo.name not in CAMPOS_DE_CONTROLE:
            yield campo


@transaction.atomic
def criar(objeto: ModeloBase, *, ator: Ator, empresa_id: int | None = None) -> ModeloBase:
    objeto.full_clean()
    objeto.save()
    alteracoes = {
        campo.name: {"antes": None, "depois": valor_auditavel(getattr(objeto, campo.attname))}
        for campo in _campos_auditaveis(objeto)
    }
    registrar_alteracao(
        objeto=objeto,
        acao=Acao.CRIACAO,
        ator=ator,
        alteracoes=alteracoes,
        empresa_id=_empresa_id(objeto, empresa_id),
    )
    return objeto


def _gravar_condicionalmente(objeto: ModeloBase, versao_esperada: int, valores: dict) -> None:
    """Grava somente se a versão no banco ainda for a esperada; incrementa a versão."""
    gravados = (
        type(objeto)
        ._default_manager.filter(pk=objeto.pk, versao=versao_esperada)
        .update(**valores, versao=F("versao") + 1, atualizado_em=timezone.now())
    )
    if gravados == 0:
        raise ConflitoDeVersao()


@transaction.atomic
def atualizar(
    objeto: ModeloBase,
    dados: dict,
    *,
    versao_esperada: int,
    ator: Ator,
    empresa_id: int | None = None,
) -> ModeloBase:
    """Aplica `dados` (campo → novo valor) ao objeto, com validação e auditoria.

    Retorna o objeto recarregado do banco. Se nada mudou, não grava nem audita.
    """
    alteracoes = {}
    for nome, novo in dados.items():
        antigo = getattr(objeto, nome)
        if not _iguais(antigo, novo):
            alteracoes[nome] = {"antes": valor_auditavel(antigo), "depois": valor_auditavel(novo)}
    if not alteracoes:
        if objeto.versao != versao_esperada:
            raise ConflitoDeVersao()
        return objeto

    for nome in alteracoes:
        setattr(objeto, nome, dados[nome])
    objeto.full_clean()

    _gravar_condicionalmente(objeto, versao_esperada, {nome: dados[nome] for nome in alteracoes})
    registrar_alteracao(
        objeto=objeto,
        acao=Acao.ALTERACAO,
        ator=ator,
        alteracoes=alteracoes,
        empresa_id=_empresa_id(objeto, empresa_id),
    )
    objeto.refresh_from_db()
    return objeto


@transaction.atomic
def arquivar(
    objeto: ModeloArquivavel,
    *,
    versao_esperada: int,
    ator: Ator,
    empresa_id: int | None = None,
) -> ModeloArquivavel:
    if objeto.arquivado:
        raise ErroDeNegocio("Este registro já está arquivado.")
    agora = timezone.now()
    _gravar_condicionalmente(objeto, versao_esperada, {"arquivado_em": agora})
    registrar_alteracao(
        objeto=objeto,
        acao=Acao.ARQUIVAMENTO,
        ator=ator,
        alteracoes={"arquivado_em": {"antes": None, "depois": valor_auditavel(agora)}},
        empresa_id=_empresa_id(objeto, empresa_id),
    )
    objeto.refresh_from_db()
    return objeto


@transaction.atomic
def reativar(
    objeto: ModeloArquivavel,
    *,
    versao_esperada: int,
    ator: Ator,
    empresa_id: int | None = None,
) -> ModeloArquivavel:
    if not objeto.arquivado:
        raise ErroDeNegocio("Este registro não está arquivado.")
    anterior = objeto.arquivado_em
    _gravar_condicionalmente(objeto, versao_esperada, {"arquivado_em": None})
    registrar_alteracao(
        objeto=objeto,
        acao=Acao.REATIVACAO,
        ator=ator,
        alteracoes={"arquivado_em": {"antes": valor_auditavel(anterior), "depois": None}},
        empresa_id=_empresa_id(objeto, empresa_id),
    )
    objeto.refresh_from_db()
    return objeto
