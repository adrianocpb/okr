"""Leitura de variáveis de ambiente e montagem da configuração do banco.

Todo acesso a variáveis de ambiente das settings passa por aqui, para que os
nomes e as regras de conversão fiquem em um único lugar.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

VALORES_VERDADEIROS = {"1", "true", "sim", "yes", "on"}
VALORES_FALSOS = {"0", "false", "nao", "não", "no", "off", ""}


def carregar_dotenv() -> None:
    """Carrega o arquivo `.env` da raiz do projeto, sem sobrescrever o ambiente.

    Usado somente em desenvolvimento. Em produção as variáveis vêm do ambiente
    do servidor, e nos testes não se lê `.env` para manter os resultados
    independentes da máquina.
    """
    load_dotenv(BASE_DIR / ".env", override=False)


def texto(nome: str, padrao: str = "") -> str:
    return os.environ.get(nome, padrao).strip()


def booleano(nome: str, padrao: bool = False) -> bool:
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    valor = valor.strip().lower()
    if valor in VALORES_VERDADEIROS:
        return True
    if valor in VALORES_FALSOS:
        return False
    raise ImproperlyConfigured(f"Valor inválido para {nome}: {valor!r} (use true ou false).")


def lista(nome: str, padrao: str = "") -> list[str]:
    return [item.strip() for item in texto(nome, padrao).split(",") if item.strip()]


def banco(padrao: str = "sqlite:///var/okr.sqlite3") -> dict:
    """Monta `DATABASES["default"]` a partir de `DATABASE_URL`.

    Caminhos relativos de SQLite são resolvidos a partir da raiz do projeto (e
    não da pasta de onde o comando foi executado), e a pasta do arquivo é
    criada se não existir.
    """
    config = dj_database_url.parse(texto("DATABASE_URL", padrao), conn_max_age=0)
    if config["ENGINE"] == "django.db.backends.sqlite3":
        caminho = Path(config["NAME"])
        if not caminho.is_absolute():
            caminho = BASE_DIR / caminho
        caminho.parent.mkdir(parents=True, exist_ok=True)
        config["NAME"] = str(caminho)
    return config
