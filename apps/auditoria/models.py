from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone

from apps.core.acesso import Origem


class RegistroImutavel(Exception):
    """Tentativa de alterar ou excluir um registro que só admite inserção."""


class SomenteInsercaoQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RegistroImutavel("Registros de auditoria não podem ser alterados.")

    def delete(self):
        raise RegistroImutavel("Registros de auditoria não podem ser excluídos.")


class RegistroAlteracao(models.Model):
    """Histórico de alterações estruturais (separado do histórico de check-ins).

    Somente inserção: não há edição nem exclusão pela aplicação.
    """

    class Acao(models.TextChoices):
        CRIACAO = "criacao", "Criação"
        ALTERACAO = "alteracao", "Alteração"
        ARQUIVAMENTO = "arquivamento", "Arquivamento"
        REATIVACAO = "reativacao", "Reativação"
        VINCULO = "vinculo", "Vínculo"
        DESVINCULO = "desvinculo", "Desvínculo"

    data_hora = models.DateTimeField("data e hora", default=timezone.now, editable=False)
    tipo_conteudo = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, verbose_name="tipo de registro"
    )
    objeto_id = models.PositiveBigIntegerField("identificador do registro")
    objeto_descricao = models.CharField("descrição do registro", max_length=255)
    # Inteiro (e não FK) para que a auditoria não dependa do app de cadastros e
    # continue íntegra mesmo que a estrutura de empresas evolua.
    empresa_id = models.PositiveBigIntegerField("empresa", null=True, blank=True)
    acao = models.CharField("ação", max_length=20, choices=Acao.choices)
    alteracoes = models.JSONField("alterações", default=dict, encoder=DjangoJSONEncoder)
    ator_descricao = models.CharField("autor da alteração", max_length=255)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="usuário autenticado",
    )
    origem = models.CharField("origem", max_length=20, choices=Origem.CHOICES)

    objects = SomenteInsercaoQuerySet.as_manager()

    class Meta:
        verbose_name = "registro de alteração"
        verbose_name_plural = "registros de alteração"
        ordering = ["-data_hora", "-id"]
        indexes = [
            models.Index(fields=["tipo_conteudo", "objeto_id"], name="audit_objeto_idx"),
            models.Index(fields=["empresa_id", "data_hora"], name="audit_empresa_data_idx"),
        ]

    def __str__(self):
        quando = f"{self.data_hora:%d/%m/%Y %H:%M}"
        return f"{self.get_acao_display()} de {self.objeto_descricao} em {quando}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RegistroImutavel("Registros de auditoria não podem ser alterados.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroImutavel("Registros de auditoria não podem ser excluídos.")
