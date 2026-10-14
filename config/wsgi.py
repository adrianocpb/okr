"""Ponto de entrada WSGI (servidores como gunicorn, na fase de servidor)."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()
