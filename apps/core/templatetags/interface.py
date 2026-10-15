"""Filtros de apresentação do design system RC+."""

from django import template

register = template.Library()

TONS_AVATAR = ("primario", "info", "sucesso", "alerta", "neutro")


@register.filter
def iniciais(nome: str) -> str:
    """Duas iniciais (primeiro e último nome) para avatares sem foto: "Ana Maria Souza" → "AS"."""
    partes = [parte for parte in str(nome or "").split() if parte[:1].isalnum()]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


@register.filter
def tom_avatar(chave) -> str:
    """Tom estável por registro (a mesma pessoa sempre tem a mesma cor)."""
    try:
        return TONS_AVATAR[int(chave) % len(TONS_AVATAR)]
    except TypeError, ValueError:
        return TONS_AVATAR[0]
