from django.urls import include, path

from apps.core.erros import ConflitoDeVersao, ErroDeNegocio


def view_erro_de_negocio(request):
    raise ErroDeNegocio("Regra de negócio fictícia violada.")


def view_conflito(request):
    raise ConflitoDeVersao()


def view_erro_inesperado(request):
    raise RuntimeError("falha inesperada fictícia")


urlpatterns = [
    path("", include("apps.core.urls")),
    path("", include("apps.cadastros.urls")),
    path("", include("apps.okrs.urls")),
    path("teste/erro-negocio/", view_erro_de_negocio),
    path("teste/conflito/", view_conflito),
    path("teste/erro-inesperado/", view_erro_inesperado),
]
