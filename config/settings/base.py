"""Configurações comuns a todos os ambientes.

Os ambientes específicos (dev, test, prod) importam este módulo e ajustam o que
for necessário. Segredos e caminhos vêm de variáveis de ambiente (config.env).
"""

from config import env

BASE_DIR = env.BASE_DIR

SECRET_KEY = env.texto("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env.lista("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.contas",
    "apps.auditoria",
    "apps.cadastros",
    "apps.okrs",
    "apps.acompanhamento",
    "apps.painel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.ErroDeNegocioMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": env.banco()}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Modelo de usuário próprio desde a primeira migração (ver docs/ARQUITETURA.md §4).
AUTH_USER_MODEL = "contas.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Localização: português do Brasil, fuso de São Paulo, datas armazenadas em UTC.
LANGUAGE_CODE = "pt-br"
LANGUAGES = [("pt-br", "Português (Brasil)")]
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Cabeçalhos de segurança válidos em qualquer ambiente.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True

# Backup (ver docs/ARQUITETURA.md §11). A pasta deve ficar fora do repositório.
OKR_BACKUP_DIR = env.texto("OKR_BACKUP_DIR")
OKR_BACKUP_CHAVE = env.texto("OKR_BACKUP_CHAVE")
OKR_BACKUP_RETENCAO = env.inteiro("OKR_BACKUP_RETENCAO", 30)

# Logs: console em todos os ambientes; dev acrescenta arquivo em var/logs.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "padrao": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "padrao"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "okr": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
