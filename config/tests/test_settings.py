"""Testes das regras de configuração por ambiente.

As configurações de produção são carregadas em um processo separado, porque o
Django só pode ser configurado uma vez por processo.
"""

import os
import string
import subprocess
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

from config import env

CHAVE_VALIDA = string.ascii_letters + string.digits  # 62 caracteres variados, fictícia


def executar_com_settings_prod(comando, **variaveis):
    ambiente = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "DATABASE_"))}
    ambiente.update({"DJANGO_SETTINGS_MODULE": "config.settings.prod", **variaveis})
    return subprocess.run(
        [sys.executable, *comando],
        cwd=env.BASE_DIR,
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=60,
    )


def carregar_settings_prod(**variaveis):
    return executar_com_settings_prod(["-c", "import django; django.setup()"], **variaveis)


def test_prod_recusa_secret_key_ausente():
    resultado = carregar_settings_prod(DJANGO_ALLOWED_HOSTS="okr.exemplo.com")

    assert resultado.returncode != 0
    assert "DJANGO_SECRET_KEY" in resultado.stderr


def test_prod_recusa_secret_key_fraca():
    resultado = carregar_settings_prod(
        DJANGO_SECRET_KEY="inseguro-somente-desenvolvimento-local",
        DJANGO_ALLOWED_HOSTS="okr.exemplo.com",
    )

    assert resultado.returncode != 0
    assert "DJANGO_SECRET_KEY" in resultado.stderr


def test_prod_recusa_debug_ativo():
    resultado = carregar_settings_prod(
        DJANGO_SECRET_KEY=CHAVE_VALIDA,
        DJANGO_ALLOWED_HOSTS="okr.exemplo.com",
        DJANGO_DEBUG="true",
    )

    assert resultado.returncode != 0
    assert "DJANGO_DEBUG" in resultado.stderr


def test_prod_recusa_allowed_hosts_vazio():
    resultado = carregar_settings_prod(DJANGO_SECRET_KEY=CHAVE_VALIDA)

    assert resultado.returncode != 0
    assert "DJANGO_ALLOWED_HOSTS" in resultado.stderr


def test_prod_inicia_com_configuracao_segura():
    resultado = carregar_settings_prod(
        DJANGO_SECRET_KEY=CHAVE_VALIDA,
        DJANGO_ALLOWED_HOSTS="okr.exemplo.com",
    )

    assert resultado.returncode == 0, resultado.stderr


def test_prod_passa_no_check_deploy_sem_avisos():
    resultado = executar_com_settings_prod(
        ["manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        DJANGO_SECRET_KEY=CHAVE_VALIDA,
        DJANGO_ALLOWED_HOSTS="okr.exemplo.com",
    )

    assert resultado.returncode == 0, resultado.stderr


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("true", True), ("Sim", True), ("1", True), ("false", False), ("não", False), ("0", False)],
)
def test_booleano_aceita_valores_conhecidos(monkeypatch, valor, esperado):
    monkeypatch.setenv("OKR_TESTE_BOOL", valor)

    assert env.booleano("OKR_TESTE_BOOL") is esperado


def test_booleano_recusa_valor_desconhecido(monkeypatch):
    monkeypatch.setenv("OKR_TESTE_BOOL", "talvez")

    with pytest.raises(ImproperlyConfigured):
        env.booleano("OKR_TESTE_BOOL")


def test_banco_sqlite_relativo_e_resolvido_a_partir_da_raiz(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///var/okr-teste.sqlite3")

    config = env.banco()

    assert config["NAME"] == str(env.BASE_DIR / "var" / "okr-teste.sqlite3")


def test_banco_sqlite_absoluto_cria_a_pasta(monkeypatch, tmp_path):
    destino = tmp_path / "dados" / "okr.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{destino.as_posix()}")

    config = env.banco()

    assert config["NAME"] == str(destino)
    assert destino.parent.is_dir()
