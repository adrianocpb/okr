from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.contas import services


class Command(BaseCommand):
    help = (
        "Cria uma conta de Administrador com senha temporária (mostrada uma vez). "
        "Use para o primeiro acesso; os demais usuários são criados na tela Usuários."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--nome", required=True)

    def handle(self, *args, email, nome, **options):
        try:
            usuario, senha = services.criar_usuario(nome=nome, email=email, administrador=True)
        except ValidationError as erro:
            raise CommandError(" ".join(erro.messages)) from erro
        self.stdout.write(f"Administrador criado: {usuario.email}")
        self.stdout.write(f"Senha temporária: {senha}")
        self.stderr.write(
            "\nEntre no sistema com este e-mail e a senha temporária; no primeiro acesso "
            "será pedida uma senha nova. A senha temporária não é exibida de novo."
        )
