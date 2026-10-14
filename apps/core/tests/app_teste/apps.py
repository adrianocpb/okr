from django.apps import AppConfig


class AppTesteConfig(AppConfig):
    """App instalado somente nas settings de teste (sem migrações; tabelas criadas no teste)."""

    name = "apps.core.tests.app_teste"
    label = "app_teste"
