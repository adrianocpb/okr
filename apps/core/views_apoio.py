"""Auxiliares comuns às views dos módulos (paginação, filtros, erros, arquivamento)."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.utils.http import urlencode

from apps.core.erros import ErroDeNegocio
from apps.core.formularios import aplicar_erros

ITENS_POR_PAGINA = 25


def pagina(request, queryset):
    return Paginator(queryset, ITENS_POR_PAGINA).get_page(request.GET.get("pagina"))


def filtros(request, *nomes):
    """Lê filtros da querystring. Retorna (valores, querystring sem a página)."""
    valores = {nome: request.GET.get(nome, "").strip() for nome in nomes}
    return valores, urlencode({k: v for k, v in valores.items() if v})


def inteiro(valor: str) -> int | None:
    return int(valor) if valor.isdigit() else None


def executar(form, operacao):
    """Executa a operação do service e leva eventuais erros para o formulário."""
    try:
        return operacao()
    except ValidationError as erro:
        aplicar_erros(form, erro)
    except ErroDeNegocio as erro:
        form.add_error(None, erro.mensagem)
    return None


def alternar_arquivamento(request, operacao, mensagem_sucesso):
    """Executa arquivar/reativar com a versão enviada pelo formulário."""
    try:
        versao = int(request.POST.get("versao", ""))
    except ValueError:
        messages.error(request, "Requisição inválida: versão do registro ausente.")
        return
    try:
        operacao(versao)
    except ErroDeNegocio as erro:
        messages.error(request, erro.mensagem)
    else:
        messages.success(request, mensagem_sucesso)
