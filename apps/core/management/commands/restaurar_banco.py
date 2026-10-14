from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from apps.core.backup import (
    ErroBackup,
    caminho_banco_atual,
    config_das_settings,
    restaurar_backup,
)

CONFIRMACAO = "RESTAURAR"


class Command(BaseCommand):
    help = (
        "Restaura um backup criptografado sobre o banco atual. Execute com a aplicação parada. "
        "Um backup de segurança do banco atual é criado antes da substituição."
    )

    def add_arguments(self, parser):
        parser.add_argument("arquivo", help="Caminho do arquivo .okrbak a restaurar.")
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help=f"Não pedir a digitação de {CONFIRMACAO} (uso em scripts).",
        )

    def handle(self, *args, arquivo, confirmar, **options):
        try:
            config = config_das_settings()
            destino = caminho_banco_atual()
        except ErroBackup as exc:
            raise CommandError(exc.mensagem) from exc

        self.stdout.write(f"Backup a restaurar: {arquivo}")
        self.stdout.write(f"Banco que será substituído: {destino}")
        if not confirmar:
            resposta = input(f"Confirme digitando {CONFIRMACAO}: ").strip()
            if resposta != CONFIRMACAO:
                raise CommandError("Restauração cancelada: confirmação não informada.")

        connections.close_all()
        try:
            resultado = restaurar_backup(Path(arquivo), config, destino)
        except ErroBackup as exc:
            raise CommandError(exc.mensagem) from exc

        self.stdout.write(self.style.SUCCESS("Banco restaurado com sucesso."))
        if resultado.backup_seguranca:
            self.stdout.write(
                f"Backup de segurança do banco anterior: {resultado.backup_seguranca}"
            )
        self.stdout.write(
            f"Registros restaurados: {sum(resultado.contagens.values())} "
            f"em {len(resultado.contagens)} tabelas."
        )
        self.stdout.write(
            "Próximo passo: execute 'python manage.py migrate' antes de iniciar a aplicação."
        )
