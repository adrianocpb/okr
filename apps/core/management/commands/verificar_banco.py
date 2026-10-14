from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.backup import ErroBackup, caminho_banco_atual, config_das_settings, verificar_backup
from apps.core.banco import sqlite


class Command(BaseCommand):
    help = "Verifica a integridade do banco atual ou, com --backup, de um arquivo de backup."

    def add_arguments(self, parser):
        parser.add_argument(
            "--backup",
            metavar="ARQUIVO",
            help="Valida um backup (checksum, descriptografia e integridade) sem restaurá-lo.",
        )

    def handle(self, *args, backup=None, **options):
        try:
            if backup:
                manifesto = verificar_backup(Path(backup), config_das_settings().chave)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Backup íntegro: {backup} (criado em {manifesto['criado_em']})."
                    )
                )
                return
            caminho = caminho_banco_atual()
        except ErroBackup as exc:
            raise CommandError(exc.mensagem) from exc

        problemas = sqlite.verificar_integridade(caminho)
        if problemas:
            raise CommandError(f"Banco com problemas de integridade: {problemas[:5]}")
        self.stdout.write(self.style.SUCCESS(f"Banco íntegro: {caminho}"))
