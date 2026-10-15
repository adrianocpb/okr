"""Histórico de alterações em formato legível para as telas."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import Q
from django.urls import NoReverseMatch, reverse
from django.utils import formats, timezone

from apps.auditoria.models import RegistroAlteracao
from apps.auditoria.services import historico_do_objeto
from apps.core.acesso import EscopoAcesso

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
    tipo_registro: str = ""
    objeto_descricao: str = ""
    url_objeto: str = ""


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


# Tela de detalhe de cada tipo de registro auditado (para links na auditoria).
URLS_DE_DETALHE = {
    "cadastros.empresa": "cadastros:empresa_detalhe",
    "cadastros.pessoa": "cadastros:pessoa_detalhe",
    "cadastros.ciclo": "cadastros:ciclo_detalhe",
    "okrs.objetivo": "okrs:objetivo_detalhe",
    "okrs.resultadochave": "okrs:kr_detalhe",
    "okrs.iniciativa": "okrs:iniciativa_detalhe",
}


def _url_do_objeto(tipo: ContentType, objeto_id: int) -> str:
    nome = URLS_DE_DETALHE.get(f"{tipo.app_label}.{tipo.model}")
    if not nome:
        return ""
    try:
        return reverse(nome, args=[objeto_id])
    except NoReverseMatch:
        return ""


def entradas_legiveis(registros) -> list[EntradaHistorico]:
    """Converte registros de auditoria (de qualquer tipo de objeto) em texto legível."""
    tradutores: dict = {}
    entradas = []
    for registro in registros:
        tipo = registro.tipo_conteudo
        modelo = tipo.model_class()
        traduzir = tradutores.setdefault(modelo, _Tradutor(modelo))
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
                tipo_registro=str(modelo._meta.verbose_name).capitalize() if modelo else "",
                objeto_descricao=registro.objeto_descricao,
                url_objeto=_url_do_objeto(tipo, registro.objeto_id),
            )
        )
    return entradas


def historico_legivel(objeto: models.Model) -> list[EntradaHistorico]:
    return entradas_legiveis(historico_do_objeto(objeto).select_related("usuario", "tipo_conteudo"))


# --------------------------------------------------------------- auditoria

TIPOS_AUDITADOS = {
    "empresa": ("cadastros", "empresa"),
    "pessoa": ("cadastros", "pessoa"),
    "ciclo": ("cadastros", "ciclo"),
    "objetivo": ("okrs", "objetivo"),
    "kr": ("okrs", "resultadochave"),
    "iniciativa": ("okrs", "iniciativa"),
}
ROTULOS_TIPOS = {
    "empresa": "Empresas",
    "pessoa": "Pessoas",
    "ciclo": "Ciclos",
    "objetivo": "Objetivos",
    "kr": "KRs",
    "iniciativa": "Iniciativas",
}


def listar_auditoria(
    escopo: EscopoAcesso,
    *,
    tipo: str = "",
    empresa_id: int | None = None,
    acao: str = "",
    data_de: date | None = None,
    data_ate: date | None = None,
):
    """Registros de alteração estrutural, filtrados e limitados pelo escopo.

    Com escopo restrito, só aparecem registros das empresas permitidas (alterações
    de dados pessoais sem empresa ficam visíveis apenas para acesso total).
    """
    registros = RegistroAlteracao.objects.select_related("usuario", "tipo_conteudo")
    if not escopo.irrestrito:
        registros = registros.filter(empresa_id__in=escopo.empresas_ids)
    if tipo in TIPOS_AUDITADOS:
        app, modelo = TIPOS_AUDITADOS[tipo]
        registros = registros.filter(tipo_conteudo__app_label=app, tipo_conteudo__model=modelo)
    if empresa_id:
        registros = registros.filter(empresa_id=empresa_id)
    if acao in RegistroAlteracao.Acao.values:
        registros = registros.filter(acao=acao)
    if data_de:
        registros = registros.filter(data_hora__date__gte=data_de)
    if data_ate:
        registros = registros.filter(data_hora__date__lte=data_ate)
    return registros.order_by("-data_hora", "-id")


def registros_de_objetos(objetos: list[models.Model]):
    """Registros de auditoria de vários objetos (de tipos diversos)."""
    filtro = Q(pk__in=[])
    por_tipo: dict = {}
    for objeto in objetos:
        tipo = ContentType.objects.get_for_model(objeto, for_concrete_model=True)
        por_tipo.setdefault(tipo.pk, []).append(objeto.pk)
    for tipo_id, ids in por_tipo.items():
        filtro |= Q(tipo_conteudo_id=tipo_id, objeto_id__in=ids)
    return RegistroAlteracao.objects.filter(filtro).select_related("usuario", "tipo_conteudo")
