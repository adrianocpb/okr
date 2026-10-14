from django.core.management.base import BaseCommand, CommandError

from apps.core.backup import ErroBackup, config_das_settings, criar_backup


class Command(BaseCommand):
    help = "Cria um backup criptografado do banco em OKR_BACKUP_DIR e aplica a retenção."

    def handle(self, *args, **options):
        try:
            resultado = criar_backup(config_das_settings())
        except ErroBackup as exc:
            raise CommandError(exc.mensagem) from exc

        total = sum(resultado.manifesto["contagens"].values())
        self.stdout.write(self.style.SUCCESS(f"Backup criado: {resultado.arquivo}"))
        self.stdout.write(
            f"Tabelas: {len(resultado.manifesto['contagens'])}; registros: {total}; "
            f"tamanho do banco: {resultado.manifesto['tamanho_banco']} bytes."
        )
        for removido in resultado.removidos:
            self.stdout.write(f"Removido pela retenção: {removido.name}")
