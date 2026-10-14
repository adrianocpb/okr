from django import template

from apps.okrs import formatacao

register = template.Library()


@register.filter
def valor_kr(numero, kr):
    """Formata um valor na unidade e nas casas decimais do KR."""
    return formatacao.valor(numero, kr.casas_decimais, kr.unidade)


@register.filter
def percentual(numero):
    return formatacao.percentual(numero)


@register.filter
def resumo_medicao(kr):
    return formatacao.resumo_medicao(kr)
