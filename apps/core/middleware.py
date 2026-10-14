import logging

from django.shortcuts import render

from apps.core.erros import ErroDeNegocio

logger = logging.getLogger("okr")


class ErroDeNegocioMiddleware:
    """Rede de segurança: erros de negócio não tratados viram uma página amigável.

    As views devem tratar os erros esperados no próprio formulário; este
    middleware evita que um erro de negócio escapado apareça como erro 500.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not isinstance(exception, ErroDeNegocio):
            return None
        logger.info("Erro de negócio em %s: %s", request.path, exception.mensagem)
        return render(
            request,
            "erro_negocio.html",
            {"mensagem": exception.mensagem},
            status=exception.status_http,
        )
