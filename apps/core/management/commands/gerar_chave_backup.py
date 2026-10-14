from django.core.management.base import BaseCommand

from apps.core.backup import gerar_chave


class Command(BaseCommand):
    help = "Gera uma nova chave de criptografia para os backups (OKR_BACKUP_CHAVE)."

    def handle(self, *args, **options):
        self.stdout.write(gerar_chave())
        self.stderr.write(
            "\nCopie a chave acima para OKR_BACKUP_CHAVE no arquivo .env e guarde uma cópia "
            "em local seguro fora deste computador (por exemplo, um gerenciador de senhas).\n"
            "Sem esta chave, os backups criptografados com ela NÃO podem ser restaurados.\n"
            "Trocar a chave não afeta backups antigos, que continuam exigindo a chave anterior."
        )
