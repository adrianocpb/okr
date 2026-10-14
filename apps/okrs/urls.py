from django.urls import path

from apps.okrs import views

app_name = "okrs"

urlpatterns = [
    path("objetivos/", views.objetivo_lista, name="objetivo_lista"),
    path("objetivos/novo/", views.objetivo_novo, name="objetivo_novo"),
    path("objetivos/<int:pk>/", views.objetivo_detalhe, name="objetivo_detalhe"),
    path("objetivos/<int:pk>/editar/", views.objetivo_editar, name="objetivo_editar"),
    path("objetivos/<int:pk>/vincular/", views.objetivo_vincular, name="objetivo_vincular"),
    path(
        "objetivos/<int:pk>/vinculos/<int:vinculo_pk>/remover/",
        views.objetivo_desvincular,
        name="objetivo_desvincular",
    ),
    path("objetivos/<int:objetivo_pk>/krs/novo/", views.kr_novo, name="kr_novo"),
    path("krs/<int:pk>/", views.kr_detalhe, name="kr_detalhe"),
    path("krs/<int:pk>/editar/", views.kr_editar, name="kr_editar"),
    path("krs/<int:pk>/marcos/", views.marco_adicionar, name="marco_adicionar"),
    path(
        "krs/<int:pk>/marcos/<int:marco_pk>/remover/",
        views.marco_remover,
        name="marco_remover",
    ),
]
