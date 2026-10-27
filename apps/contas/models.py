from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Conta de acesso ao sistema.

    O login é feito pelo e-mail, guardado também em `username` (em minúsculas),
    para aproveitar a autenticação nativa do Django. Contas são criadas pelo
    Administrador (`is_staff`) com uma senha temporária, que deve ser trocada no
    primeiro acesso. A ligação com Pessoa e o login corporativo (SSO) ficam para
    a etapa completa de autenticação (E13).
    """

    deve_trocar_senha = models.BooleanField("deve trocar a senha no próximo acesso", default=False)

    class Meta(AbstractUser.Meta):
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    @property
    def nome_exibicao(self) -> str:
        return self.get_full_name() or self.email or self.username

    @property
    def administrador(self) -> bool:
        return self.is_staff or self.is_superuser
