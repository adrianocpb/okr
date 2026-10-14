from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    """Conta de acesso ao sistema.

    Criada desde a primeira migração para permitir a inclusão futura do login
    corporativo sem trocar o modelo de usuário. A ligação com Pessoa (cadastro
    de negócio) será adicionada na etapa de autenticação (E13).
    """

    class Meta(AbstractUser.Meta):
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
