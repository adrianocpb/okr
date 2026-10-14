"""Registro de alterações estruturais.

Deve ser chamado dentro da mesma transação da alteração: se o registro falhar,
a alteração inteira é revertida (sem perda silenciosa de histórico).
"""

from datetime import date, datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.auditoria.models import RegistroAlteracao
from apps.core.acesso import Ator


def valor_auditavel(valor):
    """Converte um valor de campo em algo serializável e fiel ao original."""
    if isinstance(valor, models.Model):
        return valor.pk
    if isinstance(valor, Decimal):
        return str(valor)  # preserva a precisão exata
    if isinstance(valor, datetime | date):
        return valor.isoformat()
    return valor


def registrar_alteracao(
    *,
    objeto: models.Model,
    acao: str,
    ator: Ator,
    alteracoes: dict | None = None,
    empresa_id: int | None = None,
) -> RegistroAlteracao:
    return RegistroAlteracao.objects.create(
        tipo_conteudo=ContentType.objects.get_for_model(objeto, for_concrete_model=True),
        objeto_id=objeto.pk,
        objeto_descricao=str(objeto)[:255],
        empresa_id=empresa_id,
        acao=acao,
        alteracoes=alteracoes or {},
        ator_descricao=ator.descricao,
        usuario_id=ator.usuario_id,
        origem=ator.origem,
    )


def historico_do_objeto(objeto: models.Model):
    return RegistroAlteracao.objects.filter(
        tipo_conteudo=ContentType.objects.get_for_model(objeto, for_concrete_model=True),
        objeto_id=objeto.pk,
    )
