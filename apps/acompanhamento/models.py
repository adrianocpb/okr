"""Histórico de acompanhamento (somente inserção), separado do histórico de alterações."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.cadastros.models import Pessoa
from apps.core.models import ModeloSomenteInsercao
from apps.okrs.dominio import progresso as dominio
from apps.okrs.models import Marco, ResultadoChave


def _campo_valor(rotulo: str) -> models.DecimalField:
    return models.DecimalField(rotulo, max_digits=18, decimal_places=4, null=True, blank=True)


class CheckIn(ModeloSomenteInsercao):
    """Registro periódico de acompanhamento de um KR.

    Nunca é editado nem excluído: correções são feitas por um novo check-in de
    retificação, que aponta para o original. A configuração de medição vigente no
    momento do registro é copiada, para que o progresso histórico seja reproduzível
    mesmo que a meta mude depois.
    """

    class Status(models.TextChoices):
        NO_RITMO = "no_ritmo", "No ritmo"
        ATENCAO = "atencao", "Atenção"
        EM_RISCO = "em_risco", "Em risco"
        CONCLUIDO = "concluido", "Concluído"

    kr = models.ForeignKey(
        ResultadoChave, on_delete=models.PROTECT, related_name="checkins", verbose_name="KR"
    )
    data_referencia = models.DateField("data de referência")
    valor = _campo_valor("valor medido")
    concluido = models.BooleanField("concluído", null=True, blank=True)
    status_informado = models.CharField("status", max_length=12, choices=Status.choices)
    comentario = models.TextField("comentário", blank=True)
    dificuldades = models.TextField("dificuldades, riscos ou impedimentos", blank=True)
    proximos_passos = models.TextField("próximos passos", blank=True)

    # Autoria: sem login, a pessoa é apenas informada (não verificada). Com login,
    # o usuário autenticado também é registrado.
    autor_informado = models.ForeignKey(
        Pessoa, on_delete=models.PROTECT, related_name="checkins", verbose_name="autor informado"
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="usuário que registrou",
    )
    registrado_em = models.DateTimeField("registrado em", default=timezone.now, editable=False)

    # Cópia da medição vigente no momento do registro.
    tipo_medicao_vigente = models.CharField(
        max_length=12, choices=ResultadoChave.TipoMedicao.choices
    )
    regra_vigente = models.CharField(max_length=15, blank=True)
    valor_inicial_vigente = _campo_valor("valor inicial vigente")
    meta_vigente = _campo_valor("meta vigente")
    limite_inferior_vigente = _campo_valor("limite mínimo vigente")
    limite_superior_vigente = _campo_valor("limite máximo vigente")
    total_marcos_vigente = models.PositiveSmallIntegerField(null=True, blank=True)

    retifica = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="retificacao",
        verbose_name="retifica o check-in",
    )
    justificativa_retificacao = models.TextField("justificativa da retificação", blank=True)

    marcos_concluidos = models.ManyToManyField(
        Marco, through="CheckInMarco", related_name="checkins", blank=True
    )

    class Meta:
        verbose_name = "check-in"
        verbose_name_plural = "check-ins"
        ordering = ["-data_referencia", "-registrado_em", "-id"]
        indexes = [models.Index(fields=["kr", "data_referencia"], name="checkin_kr_data_idx")]

    def __str__(self):
        return f"Check-in de {self.data_referencia:%d/%m/%Y} · {self.kr}"

    @property
    def retificado(self) -> bool:
        return hasattr(self, "retificacao")

    @property
    def autor_verificado(self) -> bool:
        return self.registrado_por_id is not None

    def medicao_vigente(self) -> dominio.Medicao:
        return dominio.Medicao(
            tipo=dominio.TipoMedicao(self.tipo_medicao_vigente),
            regra=dominio.Regra(self.regra_vigente) if self.regra_vigente else None,
            valor_inicial=self.valor_inicial_vigente,
            meta=self.meta_vigente,
            limite_inferior=self.limite_inferior_vigente,
            limite_superior=self.limite_superior_vigente,
        )

    def progresso(self, marcos_concluidos: int | None = None) -> dominio.Progresso:
        """Progresso deste check-in calculado com a medição da época."""
        if (
            self.tipo_medicao_vigente == ResultadoChave.TipoMedicao.MARCOS
            and marcos_concluidos is None
        ):
            marcos_concluidos = self.marcos_concluidos.count()
        return dominio.calcular(
            self.medicao_vigente(),
            valor=self.valor,
            concluido=self.concluido,
            marcos_concluidos=marcos_concluidos,
            marcos_total=self.total_marcos_vigente,
        )


class CheckInMarco(ModeloSomenteInsercao):
    """Marco registrado como concluído em um check-in."""

    checkin = models.ForeignKey(CheckIn, on_delete=models.PROTECT, related_name="itens_marcos")
    marco = models.ForeignKey(Marco, on_delete=models.PROTECT, related_name="itens_checkin")

    class Meta:
        verbose_name = "marco concluído no check-in"
        verbose_name_plural = "marcos concluídos nos check-ins"
        constraints = [
            models.UniqueConstraint(fields=["checkin", "marco"], name="checkin_marco_unico")
        ]
