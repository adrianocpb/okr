"""Configurações de desenvolvimento local.

Lê o arquivo `.env` da raiz (se existir) antes de carregar as configurações
comuns. Executar somente em 127.0.0.1.
"""

from config import env

env.carregar_dotenv()

from .base import *  # noqa: E402, F403
from .base import DATABASES  # noqa: E402

DEBUG = env.booleano("DJANGO_DEBUG", padrao=True)

# Chave fixa apenas para facilitar o primeiro uso local; nunca aceita em produção.
SECRET_KEY = env.texto("DJANGO_SECRET_KEY") or "inseguro-somente-desenvolvimento-local"

ALLOWED_HOSTS = env.lista("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")

# Logs também em arquivo rotativo (var/logs/okr.log, fora do Git).
_pasta_logs = BASE_DIR / "var" / "logs"  # noqa: F405
_pasta_logs.mkdir(parents=True, exist_ok=True)
LOGGING["handlers"]["arquivo"] = {  # noqa: F405
    "class": "logging.handlers.RotatingFileHandler",
    "filename": _pasta_logs / "okr.log",
    "maxBytes": 5 * 1024 * 1024,
    "backupCount": 5,
    "encoding": "utf-8",
    "formatter": "padrao",
}
for _logger in ("okr", "django.request"):
    LOGGING["loggers"][_logger]["handlers"].append("arquivo")  # noqa: F405

# Ajustes do SQLite local: WAL e espera em caso de bloqueio reduzem erros de
# "database is locked"; transações IMMEDIATE evitam falhas ao promover leitura
# para escrita. Específico do SQLite e restrito a este arquivo.
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {}).update(
        {
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;",
            "transaction_mode": "IMMEDIATE",
        }
    )
