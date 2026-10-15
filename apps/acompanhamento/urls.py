from django.urls import path

from apps.acompanhamento import views

app_name = "acompanhamento"

urlpatterns = [
    path("krs/<int:kr_pk>/checkins/novo/", views.checkin_novo, name="checkin_novo"),
    path("checkins/<int:pk>/retificar/", views.checkin_retificar, name="checkin_retificar"),
]
