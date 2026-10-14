from django.urls import path

from apps.cadastros import views, views_ciclos

app_name = "cadastros"

urlpatterns = [
    path("empresas/", views.empresa_lista, name="empresa_lista"),
    path("empresas/nova/", views.empresa_nova, name="empresa_nova"),
    path("empresas/<int:pk>/", views.empresa_detalhe, name="empresa_detalhe"),
    path("empresas/<int:pk>/editar/", views.empresa_editar, name="empresa_editar"),
    path("empresas/<int:pk>/arquivar/", views.empresa_arquivar, name="empresa_arquivar"),
    path("empresas/<int:pk>/reativar/", views.empresa_reativar, name="empresa_reativar"),
    path("pessoas/", views.pessoa_lista, name="pessoa_lista"),
    path("pessoas/nova/", views.pessoa_nova, name="pessoa_nova"),
    path("pessoas/<int:pk>/", views.pessoa_detalhe, name="pessoa_detalhe"),
    path("pessoas/<int:pk>/editar/", views.pessoa_editar, name="pessoa_editar"),
    path("pessoas/<int:pk>/arquivar/", views.pessoa_arquivar, name="pessoa_arquivar"),
    path("pessoas/<int:pk>/reativar/", views.pessoa_reativar, name="pessoa_reativar"),
    path("ciclos/", views_ciclos.ciclo_lista, name="ciclo_lista"),
    path("ciclos/novo/", views_ciclos.ciclo_anual_novo, name="ciclo_anual_novo"),
    path("ciclos/<int:pk>/", views_ciclos.ciclo_detalhe, name="ciclo_detalhe"),
    path("ciclos/<int:pk>/editar/", views_ciclos.ciclo_editar, name="ciclo_editar"),
    path("ciclos/<int:pk>/arquivar/", views_ciclos.ciclo_arquivar, name="ciclo_arquivar"),
    path("ciclos/<int:pk>/reativar/", views_ciclos.ciclo_reativar, name="ciclo_reativar"),
    path(
        "ciclos/<int:pk>/trimestres/novo/",
        views_ciclos.ciclo_trimestre_novo,
        name="ciclo_trimestre_novo",
    ),
    path(
        "ciclos/<int:pk>/trimestres/gerar/",
        views_ciclos.ciclo_gerar_trimestres,
        name="ciclo_gerar_trimestres",
    ),
]
