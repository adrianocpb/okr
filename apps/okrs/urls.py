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
]
