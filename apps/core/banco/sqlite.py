"""Cópia, verificação e contagem de bancos SQLite."""

import sqlite3
from contextlib import closing
from pathlib import Path


def _abrir_leitura(caminho: Path) -> sqlite3.Connection:
    # Conexão comum (as funções deste módulo só leem por ela). O modo "ro" do
    # SQLite falha em alguns casos com bancos em modo WAL, que as cópias herdam.
    if not Path(caminho).is_file():
        raise FileNotFoundError(f"Banco não encontrado: {caminho}")
    return sqlite3.connect(caminho)


def copiar_de_conexao(origem: sqlite3.Connection, destino: Path) -> None:
    """Copia um banco aberto usando a API de backup online do SQLite.

    A cópia é consistente mesmo com a aplicação em uso. Se o destino existir,
    seu conteúdo é substituído pelo da origem.
    """
    with closing(sqlite3.connect(destino)) as conexao_destino:
        origem.backup(conexao_destino)


def copiar_arquivo(origem: Path, destino: Path) -> None:
    with closing(_abrir_leitura(origem)) as conexao_origem:
        copiar_de_conexao(conexao_origem, destino)


def verificar_integridade(caminho: Path) -> list[str]:
    """Executa `PRAGMA integrity_check`. Retorna a lista de problemas (vazia se íntegro)."""
    try:
        with closing(_abrir_leitura(caminho)) as conexao:
            resultado = [linha[0] for linha in conexao.execute("PRAGMA integrity_check")]
    except sqlite3.DatabaseError as exc:
        return [str(exc)]
    return [] if resultado == ["ok"] else resultado


def contar_registros(caminho: Path) -> dict[str, int]:
    with closing(_abrir_leitura(caminho)) as conexao:
        tabelas = [
            linha[0]
            for linha in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            tabela: conexao.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
            for tabela in tabelas
        }


def migracoes_aplicadas(caminho: Path) -> dict[str, str]:
    """Última migração aplicada por app (informativo, para o manifesto do backup)."""
    with closing(_abrir_leitura(caminho)) as conexao:
        try:
            linhas = conexao.execute(
                "SELECT app, name FROM django_migrations ORDER BY id"
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
    return dict(linhas)
