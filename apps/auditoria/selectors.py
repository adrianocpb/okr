"""Histórico de alterações em formato legível para as telas."""

import re
from dataclasses import dataclass
from datetime import date, datetime

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.utils import formats, timezone

from apps.auditoria.services import historico_do_objeto

ROTULOS_ESPECIAIS = {"empresa": "Empresa"}
DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class Mudanca:
    campo: str
    antes: str
    depois: str


@dataclass(frozen=True)
class EntradaHistorico:
    data_hora: datetime
    acao: str
    autor: str
    autor_verificado: bool
    mudancas: list[Mudanca]


def _rotulo(modelo: type[models.Model], campo: str) -> str:
    if campo in ROTULOS_ESPECIAIS:
        return ROTULOS_ESPECIAIS[campo]
    try:
        return str(modelo._meta.get_field(campo).verbose_name).capitalize()
    except FieldDoesNotExist:
        return campo


def _texto(valor) -> str:
    if valor is None or valor == "":
        return "—"
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, str):
        if not DATA_ISO.match(valor):
            return valor
        try:
            momento = datetime.fromisoformat(valor)
        except ValueError:
            return valor
        if momento.tzinfo is not None:
            return formats.date_format(timezone.localtime(momento), "SHORT_DATETIME_FORMAT")
        if len(valor) == 10:
            return formats.date_format(date.fromisoformat(valor), "SHORT_DATE_FORMAT")
        return valor
    return str(valor)


def historico_legivel(objeto: models.Model) -> list[EntradaHistorico]:
    modelo = type(objeto)
    entradas = []
    for registro in historico_do_objeto(objeto).select_related("usuario"):
        mudancas = [
            Mudanca(
                campo=_rotulo(modelo, campo),
                antes=_texto(valores.get("antes")),
                depois=_texto(valores.get("depois")),
            )
            for campo, valores in registro.alteracoes.items()
        ]
        entradas.append(
            EntradaHistorico(
                data_hora=registro.data_hora,
                acao=registro.get_acao_display(),
                autor=registro.ator_descricao,
                autor_verificado=registro.usuario_id is not None,
                mudancas=mudancas,
            )
        )
    return entradas
