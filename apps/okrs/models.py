from django.core.exceptions import ValidationError
from django.db import models

from apps.cadastros.models import Ciclo, Empresa, Pessoa
from apps.core.models import ModeloBase
from apps.core.texto import chave_busca, espacos_simples


class Objetivo(ModeloBase):
    """Objetivo de uma empresa em um ciclo, com Owner e Sponsor obrigatórios.

    Objetivos não são excluídos nem arquivados: encerram-se pelo status
    (Concluído ou Cancelado), preservando o histórico.
    """

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        ATIVO = "ativo", "Ativo"
        CONCLUIDO = "concluido", "Concluído"
        CANCELADO = "cancelado", "Cancelado"

    STATUS_QUE_EXIGEM_COMENTARIO = frozenset({Status.CONCLUIDO, Status.CANCELADO})

    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, related_name="objetivos", verbose_name="empresa"
    )
    ciclo = models.ForeignKey(
        Ciclo, on_delete=models.PROTECT, related_name="objetivos", verbose_name="ciclo"
    )
    titulo = models.CharField("título", max_length=200)
    descricao = models.TextField("descrição", blank=True)
    owner = models.ForeignKey(
        Pessoa,
        on_delete=models.PROTECT,
        related_name="objetivos_como_owner",
        verbose_name="owner",
    )
    sponsor = models.ForeignKey(
        Pessoa,
        on_delete=models.PROTECT,
        related_name="objetivos_como_sponsor",
        verbose_name="sponsor",
    )
    status = models.CharField("status", max_length=12, choices=Status.choices, default=Status.ATIVO)
    comentario_status = models.TextField("comentário do status", blank=True)
    chave_titulo = models.CharField(max_length=200, editable=False, db_index=True)

    campos_nao_auditados = frozenset({"chave_titulo"})

    class Meta:
        verbose_name = "objetivo"
        verbose_name_plural = "objetivos"
        ordering = [
            "empresa__sigla",
            "-ciclo__ano",
            "ciclo__tipo",
            "ciclo__trimestre",
            "chave_titulo",
        ]

    def __str__(self):
        return self.titulo

    @property
    def encerrado(self) -> bool:
        return self.status in self.STATUS_QUE_EXIGEM_COMENTARIO

    @property
    def mesma_pessoa_owner_sponsor(self) -> bool:
        return self.owner_id is not None and self.owner_id == self.sponsor_id

    def clean(self):
        self.titulo = espacos_simples(self.titulo)
        self.descricao = (self.descricao or "").strip()
        self.comentario_status = (self.comentario_status or "").strip()
        self.chave_titulo = chave_busca(self.titulo)

        anterior = (
            Objetivo.objects.filter(pk=self.pk).values("ciclo_id", "owner_id", "sponsor_id").first()
            if self.pk
            else None
        ) or {}
        erros = {}

        if self.ciclo_id and self.empresa_id:
            if self.ciclo.empresa_id != self.empresa_id:
                erros["ciclo"] = "O ciclo deve ser da mesma empresa do objetivo."
            elif self.ciclo.arquivado and self.ciclo_id != anterior.get("ciclo_id"):
                erros["ciclo"] = "Ciclo arquivado não pode receber objetivos."
            elif (
                anterior
                and self.ciclo_id != anterior.get("ciclo_id")
                and VinculoObjetivo.objects.filter(
                    models.Q(objetivo_anual_id=self.pk) | models.Q(objetivo_trimestral_id=self.pk)
                ).exists()
            ):
                erros["ciclo"] = "Remova os vínculos com outros objetivos antes de trocar o ciclo."

        # Responsáveis: só pessoas ativas e vinculadas à empresa (Q-02b). A regra vale
        # ao atribuir; uma atribuição já existente não é invalidada depois.
        for campo in ("owner", "sponsor"):
            pessoa_id = getattr(self, f"{campo}_id")
            if not pessoa_id or pessoa_id == anterior.get(f"{campo}_id"):
                continue
            pessoa = getattr(self, campo)
            if pessoa.arquivado:
                erros[campo] = "Pessoa arquivada não pode receber novas responsabilidades."
            elif (
                self.empresa_id and not pessoa.vinculos.filter(empresa_id=self.empresa_id).exists()
            ):
                erros[campo] = "A pessoa precisa estar vinculada à empresa do objetivo."

        if self.status in self.STATUS_QUE_EXIGEM_COMENTARIO and not self.comentario_status:
            erros["comentario_status"] = "Informe um comentário ao concluir ou cancelar o objetivo."
        if erros:
            raise ValidationError(erros)


class VinculoObjetivo(models.Model):
    """Desdobramento explícito: objetivo trimestral ligado a um objetivo anual.

    Opcional e N:N (um trimestral pode contribuir para mais de um anual). Sempre
    dentro da mesma empresa (Q-06) e com o trimestre pertencente ao ano do anual.
    """

    objetivo_anual = models.ForeignKey(
        Objetivo,
        on_delete=models.PROTECT,
        related_name="vinculos_como_anual",
        verbose_name="objetivo anual",
    )
    objetivo_trimestral = models.ForeignKey(
        Objetivo,
        on_delete=models.PROTECT,
        related_name="vinculos_como_trimestral",
        verbose_name="objetivo trimestral",
    )
    criado_em = models.DateTimeField("vinculado em", auto_now_add=True)

    class Meta:
        verbose_name = "vínculo entre objetivos"
        verbose_name_plural = "vínculos entre objetivos"
        constraints = [
            models.UniqueConstraint(
                fields=["objetivo_anual", "objetivo_trimestral"], name="vinculo_objetivo_unico"
            )
        ]

    def __str__(self):
        return f"{self.objetivo_trimestral} → {self.objetivo_anual}"

    def clean(self):
        anual, trimestral = self.objetivo_anual, self.objetivo_trimestral
        if anual.ciclo.tipo != Ciclo.Tipo.ANUAL:
            raise ValidationError("O objetivo de destino deve estar em um ciclo anual.")
        if trimestral.ciclo.tipo != Ciclo.Tipo.TRIMESTRAL:
            raise ValidationError("O objetivo de origem deve estar em um ciclo trimestral.")
        if anual.empresa_id != trimestral.empresa_id:
            raise ValidationError("Só é possível vincular objetivos da mesma empresa.")
        if trimestral.ciclo.ciclo_anual_id != anual.ciclo_id:
            raise ValidationError(
                "O trimestre do objetivo deve pertencer ao ciclo anual do objetivo de destino."
            )
        if (
            VinculoObjetivo.objects.filter(objetivo_anual=anual, objetivo_trimestral=trimestral)
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError("Estes objetivos já estão vinculados.")
