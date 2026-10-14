"""Configurações para a suíte de testes automatizados.

Não lê `.env`: os testes devem dar o mesmo resultado em qualquer máquina e no CI.
O pytest-django cria um banco de teste isolado (em memória, no SQLite).
"""

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "chave-exclusiva-para-testes-automatizados"
ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost"]

# Hash rápido: os testes não avaliam a força do armazenamento de senhas.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
