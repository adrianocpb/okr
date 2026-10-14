import hashlib
import sqlite3
from contextlib import closing
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import override_settings

from apps.core import backup
from apps.core.backup import ErroBackup
from apps.core.banco import sqlite as banco_sqlite
from apps.core.tests.app_teste.models import ItemTeste

# transaction=True: os dados precisam estar efetivados para a cópia do banco.
pytestmark = pytest.mark.django_db(transaction=True)

CABECALHO_SQLITE = b"SQLite format 3\x00"


@pytest.fixture
def config(tmp_path):
    return backup.montar_config(tmp_path / "backups", backup.gerar_chave(), retencao=30)


@pytest.fixture
def dados_ficticios():
    ItemTeste.objects.create(nome="Item fictício 1", valor=Decimal("1.50"), empresa_id=1)
    ItemTeste.objects.create(nome="Item fictício 2", valor=Decimal("2.75"), empresa_id=2)


def sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def nomes_dos_itens(caminho: Path) -> list[str]:
    with closing(sqlite3.connect(caminho)) as conexao:
        return [
            linha[0]
            for linha in conexao.execute("SELECT nome FROM app_teste_itemteste ORDER BY nome")
        ]


def criar_banco_avulso(caminho: Path, tabela: str) -> None:
    with closing(sqlite3.connect(caminho)) as conexao:
        conexao.execute(f"CREATE TABLE {tabela} (id INTEGER PRIMARY KEY)")
        conexao.execute(f"INSERT INTO {tabela} DEFAULT VALUES")
        conexao.commit()


def test_backup_gera_arquivo_criptografado_com_manifesto(config, dados_ficticios):
    resultado = backup.criar_backup(config)

    assert resultado.arquivo.is_file()
    assert resultado.arquivo.with_suffix(".json").is_file()
    assert not resultado.arquivo.read_bytes().startswith(CABECALHO_SQLITE)
    assert banco_sqlite.verificar_integridade(resultado.arquivo)  # não abre como SQLite
    assert resultado.manifesto["sha256_arquivo"] == sha256(resultado.arquivo)
    assert resultado.manifesto["contagens"]["app_teste_itemteste"] == 2


def test_backup_e_restauracao_preservam_os_dados(config, dados_ficticios, tmp_path):
    resultado = backup.criar_backup(config)
    destino = tmp_path / "restaurado.sqlite3"

    restauracao = backup.restaurar_backup(resultado.arquivo, config, destino)

    assert restauracao.contagens == resultado.manifesto["contagens"]
    assert banco_sqlite.contar_registros(destino) == resultado.manifesto["contagens"]
    assert nomes_dos_itens(destino) == ["Item fictício 1", "Item fictício 2"]
    assert restauracao.backup_seguranca is None  # destino não existia


def test_restauracao_cria_backup_de_seguranca_do_banco_atual(config, dados_ficticios, tmp_path):
    resultado = backup.criar_backup(config)
    destino = tmp_path / "atual.sqlite3"
    criar_banco_avulso(destino, "tabela_anterior")

    restauracao = backup.restaurar_backup(resultado.arquivo, config, destino)

    assert restauracao.backup_seguranca is not None
    assert restauracao.backup_seguranca.name.startswith(backup.PREFIXO_SEGURANCA)
    manifesto_seguranca = backup.verificar_backup(restauracao.backup_seguranca, config.chave)
    assert manifesto_seguranca["contagens"] == {"tabela_anterior": 1}
    assert "tabela_anterior" not in banco_sqlite.contar_registros(destino)


def test_restauracao_com_chave_errada_falha_sem_alterar_o_banco(config, dados_ficticios, tmp_path):
    resultado = backup.criar_backup(config)
    destino = tmp_path / "atual.sqlite3"
    criar_banco_avulso(destino, "dados_atuais")
    hash_antes = sha256(destino)
    config_errada = backup.montar_config(config.diretorio, backup.gerar_chave(), retencao=30)

    with pytest.raises(ErroBackup, match="chave incorreta"):
        backup.restaurar_backup(resultado.arquivo, config_errada, destino)

    assert sha256(destino) == hash_antes


def test_backup_adulterado_e_recusado(config, dados_ficticios, tmp_path):
    resultado = backup.criar_backup(config)
    conteudo = bytearray(resultado.arquivo.read_bytes())
    conteudo[-1] ^= 0xFF
    resultado.arquivo.write_bytes(bytes(conteudo))

    with pytest.raises(ErroBackup, match="checksum"):
        backup.restaurar_backup(resultado.arquivo, config, tmp_path / "destino.sqlite3")

    assert not (tmp_path / "destino.sqlite3").exists()


def test_verificar_backup_valida_sem_restaurar(config, dados_ficticios):
    resultado = backup.criar_backup(config)

    manifesto = backup.verificar_backup(resultado.arquivo, config.chave)

    assert manifesto["arquivo"] == resultado.arquivo.name


def test_retencao_mantem_apenas_os_mais_recentes(tmp_path):
    config = backup.montar_config(tmp_path / "backups", backup.gerar_chave(), retencao=3)
    for dia in range(1, 6):
        backup.criar_backup(config, agora=datetime(2026, 10, dia, 2, 0))

    restantes = sorted(p.name for p in config.diretorio.glob(f"*{backup.EXTENSAO}"))
    assert restantes == [
        "okr-20261003-020000-000000.okrbak",
        "okr-20261004-020000-000000.okrbak",
        "okr-20261005-020000-000000.okrbak",
    ]
    assert len(list(config.diretorio.glob("*.json"))) == 3


def test_retencao_nao_remove_backups_de_seguranca(tmp_path):
    config = backup.montar_config(tmp_path / "backups", backup.gerar_chave(), retencao=1)
    origem = tmp_path / "origem.sqlite3"
    criar_banco_avulso(origem, "qualquer")
    backup.criar_backup(config, origem=origem, prefixo=backup.PREFIXO_SEGURANCA)

    backup.criar_backup(config, agora=datetime(2026, 10, 1))
    backup.criar_backup(config, agora=datetime(2026, 10, 2))

    nomes = [p.name for p in config.diretorio.glob(f"*{backup.EXTENSAO}")]
    assert sum(n.startswith(backup.PREFIXO_SEGURANCA) for n in nomes) == 1
    assert sum(n.startswith(backup.PREFIXO_DIARIO) for n in nomes) == 1


def test_configuracao_recusa_pasta_dentro_do_repositorio():
    with pytest.raises(ErroBackup, match="dentro do repositório"):
        backup.montar_config(Path(settings.BASE_DIR) / "backups", backup.gerar_chave(), 30)


@pytest.mark.parametrize(
    ("diretorio", "chave", "retencao", "trecho"),
    [
        ("", "CHAVE", 30, "OKR_BACKUP_DIR"),
        ("PASTA", "", 30, "OKR_BACKUP_CHAVE"),
        ("PASTA", "chave-invalida", 30, "inválida"),
        ("PASTA", "VALIDA", 0, "OKR_BACKUP_RETENCAO"),
    ],
)
def test_configuracao_recusa_valores_invalidos(tmp_path, diretorio, chave, retencao, trecho):
    diretorio = str(tmp_path) if diretorio == "PASTA" else diretorio
    chave = backup.gerar_chave() if chave in {"CHAVE", "VALIDA"} else chave

    with pytest.raises(ErroBackup, match=trecho):
        backup.montar_config(diretorio, chave, retencao)


def test_comando_backup_banco(tmp_path, dados_ficticios, capsys):
    with override_settings(
        OKR_BACKUP_DIR=str(tmp_path / "backups"),
        OKR_BACKUP_CHAVE=backup.gerar_chave(),
        OKR_BACKUP_RETENCAO=30,
    ):
        call_command("backup_banco")

    saida = capsys.readouterr().out
    assert "Backup criado" in saida
    assert len(list((tmp_path / "backups").glob(f"*{backup.EXTENSAO}"))) == 1


def test_comando_backup_banco_sem_configuracao_informa_o_que_falta():
    with pytest.raises(CommandError, match="OKR_BACKUP_DIR"):
        call_command("backup_banco")


def test_comando_restaurar_exige_confirmacao(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "não")
    with (
        override_settings(
            OKR_BACKUP_DIR=str(tmp_path / "backups"),
            OKR_BACKUP_CHAVE=backup.gerar_chave(),
        ),
        pytest.raises(CommandError, match="cancelada"),
    ):
        call_command("restaurar_banco", str(tmp_path / "qualquer.okrbak"))


def test_comando_gerar_chave_produz_chave_valida(tmp_path, capsys):
    call_command("gerar_chave_backup")

    chave = capsys.readouterr().out.strip()
    assert backup.montar_config(tmp_path, chave, 30).chave == chave.encode()


def test_comando_verificar_backup(tmp_path, dados_ficticios, capsys):
    chave = backup.gerar_chave()
    config = backup.montar_config(tmp_path / "backups", chave, 30)
    resultado = backup.criar_backup(config)

    with override_settings(OKR_BACKUP_DIR=str(config.diretorio), OKR_BACKUP_CHAVE=chave):
        call_command("verificar_banco", backup=str(resultado.arquivo))

    assert "Backup íntegro" in capsys.readouterr().out


def test_comando_verificar_backup_com_chave_errada_falha(tmp_path, dados_ficticios):
    config = backup.montar_config(tmp_path / "backups", backup.gerar_chave(), 30)
    resultado = backup.criar_backup(config)

    with (
        override_settings(
            OKR_BACKUP_DIR=str(config.diretorio), OKR_BACKUP_CHAVE=backup.gerar_chave()
        ),
        pytest.raises(CommandError, match="chave incorreta"),
    ):
        call_command("verificar_banco", backup=str(resultado.arquivo))
