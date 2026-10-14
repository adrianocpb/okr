"""Configurações de produção (servidor).

Ainda não há implantação: este módulo existe para que as exigências mínimas de
segurança sejam verificadas desde já. Ele recusa iniciar com configuração
insegura. Não lê `.env`; as variáveis vêm do ambiente do servidor.
"""

from django.core.exceptions import ImproperlyConfigured

from config import env

from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, SECRET_KEY

if env.booleano("DJANGO_DEBUG", padrao=False):
    raise ImproperlyConfigured("DJANGO_DEBUG não pode estar ativo em produção.")
DEBUG = False

if not SECRET_KEY or len(SECRET_KEY) < 50 or SECRET_KEY.startswith(("inseguro", "django-insecure")):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY ausente ou fraca: defina uma chave aleatória com 50 ou mais caracteres."
    )

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS deve listar os domínios do servidor.")

# HTTPS obrigatório e cookies protegidos.
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False

# Preload de HSTS é um compromisso difícil de reverter (lista dos navegadores);
# só deve ser avaliado com o domínio definitivo, na etapa de servidor (E14).
SILENCED_SYSTEM_CHECKS = ["security.W021"]
