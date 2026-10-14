"""Consultas do núcleo da aplicação."""

from dataclasses import dataclass

from django.db import DatabaseError, connection
from django.db.migrations.executor import MigrationExecutor

NOMES_MOTORES = {
    "sqlite": "SQLite",
    "postgresql": "PostgreSQL",
}


@dataclass(frozen=True)
class SituacaoBanco:
    conectado: bool
    motor: str
    migracoes_pendentes: int | None
    erro: str = ""


def situacao_banco() -> SituacaoBanco:
    """Verifica a conexão com o banco e se há migrações não aplicadas."""
    motor = NOMES_MOTORES.get(connection.vendor, connection.vendor)
    try:
        connection.ensure_connection()
        executor = MigrationExecutor(connection)
        plano = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except DatabaseError as exc:
        return SituacaoBanco(conectado=False, motor=motor, migracoes_pendentes=None, erro=str(exc))
    return SituacaoBanco(conectado=True, motor=motor, migracoes_pendentes=len(plano))
