"""Backup e restauração do banco de dados, com criptografia.

Fluxo do backup:
  cópia consistente (API de backup do SQLite) em pasta temporária local
  → verificação de integridade → criptografia (Fernet: AES-128-CBC + HMAC-SHA256)
  → gravação atômica em OKR_BACKUP_DIR com manifesto e checksum → retenção.

Fluxo da restauração:
  checksum → descriptografia → verificação de integridade
  → backup de segurança do banco atual → substituição → conferência das contagens.

A cópia não criptografada existe apenas na pasta temporária do sistema, nunca na
pasta de backups (que pode estar sincronizada ou compartilhada).
"""

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import connection
from django.utils import timezone

from apps.core.banco import sqlite
from apps.core.erros import ErroDeNegocio

logger = logging.getLogger("okr")

FORMATO = 1
EXTENSAO = ".okrbak"
PREFIXO_DIARIO = "okr-"
PREFIXO_SEGURANCA = "antes-restauracao-"


class ErroBackup(ErroDeNegocio):
    pass


@dataclass(frozen=True)
class ConfigBackup:
    diretorio: Path
    chave: bytes
    retencao: int


@dataclass
class ResultadoBackup:
    arquivo: Path
    manifesto: dict
    removidos: list[Path] = field(default_factory=list)


@dataclass
class ResultadoRestauracao:
    destino: Path
    backup_seguranca: Path | None
    contagens: dict[str, int]
    manifesto: dict


def gerar_chave() -> str:
    return Fernet.generate_key().decode()


def montar_config(diretorio: str | Path, chave: str | bytes, retencao: int) -> ConfigBackup:
    if not str(diretorio).strip():
        raise ErroBackup("Defina a pasta de backups na variável OKR_BACKUP_DIR.")
    pasta = Path(diretorio).expanduser().resolve()
    raiz = Path(settings.BASE_DIR).resolve()
    if pasta == raiz or pasta.is_relative_to(raiz):
        raise ErroBackup(
            "A pasta de backups não pode ficar dentro do repositório do código. "
            "Escolha uma pasta externa em OKR_BACKUP_DIR."
        )
    chave_bytes = chave.encode() if isinstance(chave, str) else chave
    if not chave_bytes:
        raise ErroBackup(
            "Defina a chave de criptografia em OKR_BACKUP_CHAVE "
            "(gere uma com: python manage.py gerar_chave_backup)."
        )
    try:
        Fernet(chave_bytes)
    except ValueError as exc:
        raise ErroBackup("A chave em OKR_BACKUP_CHAVE é inválida.") from exc
    if retencao < 1:
        raise ErroBackup("OKR_BACKUP_RETENCAO deve ser 1 ou mais.")
    return ConfigBackup(diretorio=pasta, chave=chave_bytes, retencao=retencao)


def config_das_settings() -> ConfigBackup:
    return montar_config(
        settings.OKR_BACKUP_DIR, settings.OKR_BACKUP_CHAVE, settings.OKR_BACKUP_RETENCAO
    )


def caminho_banco_atual() -> Path:
    _exigir_sqlite()
    return Path(settings.DATABASES["default"]["NAME"])


def _exigir_sqlite() -> None:
    if connection.vendor != "sqlite":
        raise ErroBackup(
            "Backup pela aplicação disponível apenas para SQLite "
            f"(banco atual: {connection.vendor}). No PostgreSQL será usado pg_dump "
            "ou o backup do provedor (fase de servidor)."
        )


def _sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _gravar_atomicamente(destino: Path, dados: bytes) -> None:
    temporario = destino.with_name(destino.name + ".parcial")
    temporario.write_bytes(dados)
    os.replace(temporario, destino)


def _manifesto_de(arquivo: Path) -> Path:
    return arquivo.with_suffix(".json")


def criar_backup(
    config: ConfigBackup,
    *,
    origem: Path | None = None,
    prefixo: str = PREFIXO_DIARIO,
    agora: datetime | None = None,
) -> ResultadoBackup:
    """Cria um backup criptografado do banco em uso (ou do arquivo `origem`)."""
    if origem is None:
        _exigir_sqlite()
    agora = agora or timezone.localtime()
    config.diretorio.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="okr-backup-") as pasta_temporaria:
        copia = Path(pasta_temporaria) / "copia.sqlite3"
        if origem is None:
            connection.ensure_connection()
            sqlite.copiar_de_conexao(connection.connection, copia)
        else:
            sqlite.copiar_arquivo(origem, copia)

        problemas = sqlite.verificar_integridade(copia)
        if problemas:
            raise ErroBackup(
                f"O banco de origem falhou na verificação de integridade: {problemas[:3]}"
            )
        contagens = sqlite.contar_registros(copia)
        migracoes = sqlite.migracoes_aplicadas(copia)
        dados = copia.read_bytes()

    cifrado = Fernet(config.chave).encrypt(dados)
    nome = f"{prefixo}{agora:%Y%m%d-%H%M%S-%f}"
    arquivo = config.diretorio / f"{nome}{EXTENSAO}"
    manifesto = {
        "formato": FORMATO,
        "arquivo": arquivo.name,
        "criado_em": agora.isoformat(),
        "motor": "sqlite",
        "criptografia": "fernet",
        "sha256_arquivo": _sha256(cifrado),
        "sha256_banco": _sha256(dados),
        "tamanho_banco": len(dados),
        "contagens": contagens,
        "migracoes": migracoes,
    }
    _gravar_atomicamente(arquivo, cifrado)
    _gravar_atomicamente(
        _manifesto_de(arquivo), json.dumps(manifesto, ensure_ascii=False, indent=2).encode()
    )

    removidos = aplicar_retencao(config) if prefixo == PREFIXO_DIARIO else []
    logger.info("Backup criado: %s (%d bytes de banco)", arquivo, len(dados))
    return ResultadoBackup(arquivo=arquivo, manifesto=manifesto, removidos=removidos)


def aplicar_retencao(config: ConfigBackup) -> list[Path]:
    """Mantém apenas os `retencao` backups diários mais recentes.

    Backups de segurança (feitos antes de restaurações) não são removidos.
    """
    arquivos = sorted(config.diretorio.glob(f"{PREFIXO_DIARIO}*{EXTENSAO}"))
    excedentes = arquivos[: max(len(arquivos) - config.retencao, 0)]
    for arquivo in excedentes:
        arquivo.unlink()
        _manifesto_de(arquivo).unlink(missing_ok=True)
        logger.info("Backup removido pela retenção: %s", arquivo)
    return excedentes


def abrir_backup(arquivo: Path, chave: bytes) -> tuple[bytes, dict]:
    """Confere o checksum e descriptografa. Retorna (conteúdo do banco, manifesto)."""
    arquivo = Path(arquivo)
    if not arquivo.is_file():
        raise ErroBackup(f"Arquivo de backup não encontrado: {arquivo}")
    caminho_manifesto = _manifesto_de(arquivo)
    if not caminho_manifesto.is_file():
        raise ErroBackup(f"Manifesto do backup não encontrado: {caminho_manifesto}")
    manifesto = json.loads(caminho_manifesto.read_text(encoding="utf-8"))
    if manifesto.get("formato") != FORMATO:
        raise ErroBackup(f"Formato de backup não suportado: {manifesto.get('formato')}")

    cifrado = arquivo.read_bytes()
    if _sha256(cifrado) != manifesto["sha256_arquivo"]:
        raise ErroBackup("O arquivo de backup está corrompido (checksum não confere).")
    try:
        dados = Fernet(chave).decrypt(cifrado)
    except InvalidToken as exc:
        raise ErroBackup(
            "Não foi possível descriptografar: chave incorreta ou arquivo adulterado."
        ) from exc
    if _sha256(dados) != manifesto["sha256_banco"]:
        raise ErroBackup("O conteúdo descriptografado não confere com o manifesto.")
    return dados, manifesto


def verificar_backup(arquivo: Path, chave: bytes) -> dict:
    """Valida um backup por completo sem restaurá-lo. Retorna o manifesto."""
    dados, manifesto = abrir_backup(arquivo, chave)
    with tempfile.TemporaryDirectory(prefix="okr-verificacao-") as pasta_temporaria:
        copia = Path(pasta_temporaria) / "verificacao.sqlite3"
        copia.write_bytes(dados)
        problemas = sqlite.verificar_integridade(copia)
        if problemas:
            raise ErroBackup(f"O banco contido no backup falhou na verificação: {problemas[:3]}")
        if sqlite.contar_registros(copia) != manifesto["contagens"]:
            raise ErroBackup("As contagens do banco no backup não conferem com o manifesto.")
    return manifesto


def restaurar_backup(arquivo: Path, config: ConfigBackup, destino: Path) -> ResultadoRestauracao:
    """Restaura o backup sobre `destino`, criando antes um backup de segurança dele.

    Deve ser executado com a aplicação parada. Nada é alterado no destino se o
    backup for inválido, estiver corrompido ou a chave estiver incorreta.
    """
    destino = Path(destino)
    dados, manifesto = abrir_backup(arquivo, config.chave)

    with tempfile.TemporaryDirectory(prefix="okr-restauracao-") as pasta_temporaria:
        copia = Path(pasta_temporaria) / "restaurar.sqlite3"
        copia.write_bytes(dados)
        problemas = sqlite.verificar_integridade(copia)
        if problemas:
            raise ErroBackup(f"O banco contido no backup falhou na verificação: {problemas[:3]}")
        contagens = sqlite.contar_registros(copia)

        seguranca = None
        if destino.exists():
            seguranca = criar_backup(config, origem=destino, prefixo=PREFIXO_SEGURANCA).arquivo
            logger.info("Backup de segurança antes da restauração: %s", seguranca)

        destino.parent.mkdir(parents=True, exist_ok=True)
        sqlite.copiar_arquivo(copia, destino)

    contagens_destino = sqlite.contar_registros(destino)
    if contagens_destino != contagens:
        raise ErroBackup(
            "A restauração terminou, mas as contagens do banco não conferem. "
            f"Restaure o backup de segurança: {seguranca}"
        )
    logger.info("Banco restaurado a partir de %s em %s", arquivo, destino)
    return ResultadoRestauracao(
        destino=destino, backup_seguranca=seguranca, contagens=contagens, manifesto=manifesto
    )
