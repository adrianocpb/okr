from django.db import models


class ModeloBase(models.Model):
    """Campos comuns às entidades editáveis.

    `versao` implementa o bloqueio otimista: toda alteração feita pelos services
    incrementa o número e é recusada se a versão de origem estiver desatualizada.
    Alterações devem passar por `apps.core.services`, nunca por `save()` direto
    a partir das views.
    """

    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)
    versao = models.PositiveIntegerField("versão", default=1, editable=False)

    class Meta:
        abstract = True


class ModeloArquivavel(ModeloBase):
    """Entidade que não é excluída fisicamente: é arquivada e pode ser reativada."""

    arquivado_em = models.DateTimeField("arquivado em", null=True, blank=True, editable=False)

    class Meta:
        abstract = True

    @property
    def arquivado(self) -> bool:
        return self.arquivado_em is not None
