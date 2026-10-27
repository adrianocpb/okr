from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("sistema/", views.inicio, name="inicio"),
    path("saude/", views.saude, name="saude"),
]
