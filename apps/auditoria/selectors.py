"""Histórico de alterações em formato legível para as telas."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.utils import formats, timezone

from apps.auditoria.services import historico_do_objeto

ROTULOS_ESPECIAIS = {
    "empresa": "Empresa",
    "objetivo_anual": "Objetivo anual",
    "objetivo_trimestral": "Objetivo trimestral",
    "kr": "KR",
    "marco": "Marco",
}
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


def _choices(modelo: type[models.Model], campo: str) -> dict:
    try:
        return dict(modelo._meta.get_field(campo).flatchoices)
    except FieldDoesNotExist, AttributeError:
        return {}


def _relacionado(modelo: type[models.Model], campo: str):
    """Modelo apontado pelo campo, se ele for uma chave estrangeira."""
    try:
        definicao = modelo._meta.get_field(campo)
    except FieldDoesNotExist:
        return None
    return definicao.related_model if definicao.many_to_one else None


class _Tradutor:
    """Converte valores gravados na auditoria em texto, resolvendo referências e opções."""

    def __init__(self, modelo: type[models.Model]):
        self.modelo = modelo
        self.cache: dict = {}

    def __call__(self, campo: str, valor) -> str:
        if valor is None or valor == "":
            return "—"
        opcoes = _choices(self.modelo, campo)
        if valor in opcoes:
            return str(opcoes[valor])
        relacionado = _relacionado(self.modelo, campo)
        if relacionado is not None and isinstance(valor, int):
            chave = (relacionado, valor)
            if chave not in self.cache:
                registro = relacionado._default_manager.filter(pk=valor).first()
                self.cache[chave] = str(registro) if registro else f"registro nº {valor}"
            return self.cache[chave]
        if _eh_decimal(self.modelo, campo) and isinstance(valor, str):
            return _decimal_legivel(valor)
        return _texto(valor)


def _eh_decimal(modelo: type[models.Model], campo: str) -> bool:
    try:
        return isinstance(modelo._meta.get_field(campo), models.DecimalField)
    except FieldDoesNotExist:
        return False


def _decimal_legivel(valor: str) -> str:
    """'150.0000' → '150'; '1234.5000' → '1.234,5' (sem zeros desnecessários, em pt-BR)."""
    try:
        numero = Decimal(valor).normalize()
    except InvalidOperation:
        return valor
    casas = max(-numero.as_tuple().exponent, 0)
    return formats.number_format(numero, casas, use_l10n=True, force_grouping=True)


def historico_legivel(objeto: models.Model) -> list[EntradaHistorico]:
    modelo = type(objeto)
    traduzir = _Tradutor(modelo)
    entradas = []
    for registro in historico_do_objeto(objeto).select_related("usuario"):
        mudancas = [
            Mudanca(
                campo=_rotulo(modelo, campo),
                antes=traduzir(campo, valores.get("antes")),
                depois=traduzir(campo, valores.get("depois")),
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
