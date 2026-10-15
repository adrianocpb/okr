from django.urls import path

from apps.auditoria import views

app_name = "auditoria"

urlpatterns = [
    path("auditoria/", views.auditoria_lista, name="auditoria_lista"),
]
