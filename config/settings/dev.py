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
