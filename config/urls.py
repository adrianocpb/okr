from django.urls import include, path

urlpatterns = [
    path("", include("apps.core.urls")),
    path("", include("apps.cadastros.urls")),
    path("", include("apps.okrs.urls")),
]
