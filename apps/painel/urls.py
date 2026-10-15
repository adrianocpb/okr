from django.urls import path

from apps.painel import views

app_name = "painel"

urlpatterns = [
    path("", views.painel, name="painel"),
]
