from django.urls import path

from apps.contas import views

app_name = "contas"

urlpatterns = [
    path("entrar/", views.entrar, name="entrar"),
    path("sair/", views.sair, name="sair"),
    path("minha-senha/", views.trocar_senha, name="trocar_senha"),
    path("usuarios/", views.usuario_lista, name="usuario_lista"),
    path("usuarios/novo/", views.usuario_novo, name="usuario_novo"),
    path(
        "usuarios/<int:pk>/redefinir-senha/",
        views.usuario_redefinir_senha,
        name="usuario_redefinir_senha",
    ),
    path("usuarios/<int:pk>/ativo/", views.usuario_ativo, name="usuario_ativo"),
]
