"""Configurações de produção (servidor).

Usado na publicação no Fly.io (ver docs/PUBLICAR-FLY.md). Recusa iniciar com
configuração insegura. Não lê `.env`; as variáveis vêm do ambiente do servidor
(fly.toml e `fly secrets`).
"""

from django.core.exceptions import ImproperlyConfigured

from config import env

from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, DATABASES, MIDDLEWARE, SECRET_KEY

if env.booleano("DJANGO_DEBUG", padrao=False):
    raise ImproperlyConfigured("DJANGO_DEBUG não pode estar ativo em produção.")
DEBUG = False

if not SECRET_KEY or len(SECRET_KEY) < 50 or SECRET_KEY.startswith(("inseguro", "django-insecure")):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY ausente ou fraca: defina uma chave aleatória com 50 ou mais caracteres."
    )

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS deve listar os domínios do servidor.")

CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if not host.startswith(".")]

# Arquivos estáticos servidos pela aplicação, com nomes versionados e compressão.
MIDDLEWARE = [
    MIDDLEWARE[0],
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# SQLite no disco permanente do servidor: mesmos ajustes do ambiente local.
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {}).update(
        {
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;",
            "transaction_mode": "IMMEDIATE",
        }
    )

# HTTPS obrigatório e cookies protegidos. A verificação de saúde do Fly.io chega
# por HTTP interno e fica fora do redirecionamento.
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^saude/$"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False

# Preload de HSTS é um compromisso difícil de reverter (lista dos navegadores);
# só deve ser avaliado com o domínio definitivo, na etapa de servidor (E14).
SILENCED_SYSTEM_CHECKS = ["security.W021"]
