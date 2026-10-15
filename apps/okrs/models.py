from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.cadastros.models import Ciclo, Empresa, Pessoa
from apps.core.models import ModeloBase
from apps.core.texto import chave_busca, espacos_simples
from apps.okrs.dominio import progresso as dominio


def problema_do_responsavel(pessoa: Pessoa, empresa_id: int | None) -> str | None:
    """Regra para atribuir responsabilidade (Q-02b): pessoa ativa e vinculada à empresa.

    Vale no momento da atribuição; uma atribuição existente não é invalidada depois.
    """
    if pessoa.arquivado:
        return "Pessoa arquivada não pode receber novas responsabilidades."
    if empresa_id and not pessoa.vinculos.filter(empresa_id=empresa_id).exists():
        return "A pessoa precisa estar vinculada à empresa do objetivo."
    return None


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
            problema = problema_do_responsavel(getattr(self, campo), self.empresa_id)
            if problema:
                erros[campo] = problema

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


def _campo_valor(rotulo: str) -> models.DecimalField:
    return models.DecimalField(rotulo, max_digits=18, decimal_places=4, null=True, blank=True)


class ResultadoChave(ModeloBase):
    """Resultado-chave (KR): medida verificável de um objetivo.

    Tem um único responsável principal e **não** possui Owner nem Sponsor.
    O valor atual não é digitado aqui: virá dos check-ins (E7).
    """

    class TipoMedicao(models.TextChoices):
        NUMERICO = dominio.TipoMedicao.NUMERICO, "Numérico (valor absoluto ou percentual)"
        MANUTENCAO = dominio.TipoMedicao.MANUTENCAO, "Manutenção (manter em um patamar)"
        BINARIO = dominio.TipoMedicao.BINARIO, "Binário (sim/não)"
        MARCOS = dominio.TipoMedicao.MARCOS, "Marcos (etapas de conclusão)"

    class Regra(models.TextChoices):
        CRESCENTE = dominio.Regra.CRESCENTE, "Crescente (maior é melhor)"
        DECRESCENTE = dominio.Regra.DECRESCENTE, "Decrescente (menor é melhor)"
        MANTER_ACIMA = dominio.Regra.MANTER_ACIMA, "Manter igual ou acima do mínimo"
        MANTER_ABAIXO = dominio.Regra.MANTER_ABAIXO, "Manter igual ou abaixo do máximo"
        MANTER_ENTRE = dominio.Regra.MANTER_ENTRE, "Manter entre mínimo e máximo"

    class Status(models.TextChoices):
        ATIVO = "ativo", "Ativo"
        CONCLUIDO = "concluido", "Concluído"
        CANCELADO = "cancelado", "Cancelado"

    FREQUENCIA_PADRAO_DIAS = 14  # quinzenal

    objetivo = models.ForeignKey(
        Objetivo, on_delete=models.PROTECT, related_name="krs", verbose_name="objetivo"
    )
    titulo = models.CharField("título", max_length=200)
    descricao = models.TextField("descrição", blank=True)
    responsavel = models.ForeignKey(
        Pessoa,
        on_delete=models.PROTECT,
        related_name="krs_como_responsavel",
        verbose_name="responsável",
    )
    tipo_medicao = models.CharField("tipo de medição", max_length=12, choices=TipoMedicao.choices)
    regra = models.CharField("regra de evolução", max_length=15, choices=Regra.choices, blank=True)
    unidade = models.CharField("unidade", max_length=30, blank=True)
    casas_decimais = models.PositiveSmallIntegerField(
        "casas decimais", default=0, validators=[MaxValueValidator(4)]
    )
    valor_inicial = _campo_valor("valor inicial")
    meta = _campo_valor("meta")
    limite_inferior = _campo_valor("limite mínimo")
    limite_superior = _campo_valor("limite máximo")
    frequencia_checkin_dias = models.PositiveSmallIntegerField(
        "frequência de check-in (dias)",
        default=FREQUENCIA_PADRAO_DIAS,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
    )
    status = models.CharField("status", max_length=12, choices=Status.choices, default=Status.ATIVO)
    chave_titulo = models.CharField(max_length=200, editable=False, db_index=True)

    campos_nao_auditados = frozenset({"chave_titulo"})

    # Campos usados por cada tipo; os demais são limpos ao salvar.
    CAMPOS_POR_TIPO = {
        TipoMedicao.NUMERICO: {"regra", "unidade", "valor_inicial", "meta"},
        TipoMedicao.MANUTENCAO: {"regra", "unidade", "limite_inferior", "limite_superior"},
        TipoMedicao.BINARIO: set(),
        TipoMedicao.MARCOS: set(),
    }

    class Meta:
        verbose_name = "resultado-chave"
        verbose_name_plural = "resultados-chave"
        ordering = ["objetivo_id", "id"]

    def __str__(self):
        return self.titulo

    @property
    def empresa_para_auditoria(self) -> int | None:
        return self.objetivo.empresa_id if self.objetivo_id else None

    def medicao(self) -> dominio.Medicao:
        return dominio.Medicao(
            tipo=dominio.TipoMedicao(self.tipo_medicao),
            regra=dominio.Regra(self.regra) if self.regra else None,
            valor_inicial=self.valor_inicial,
            meta=self.meta,
            limite_inferior=self.limite_inferior,
            limite_superior=self.limite_superior,
        )

    def _limpar_campos_nao_usados(self) -> None:
        usados = self.CAMPOS_POR_TIPO.get(self.tipo_medicao, set())
        if "regra" not in usados:
            self.regra = ""
        if "unidade" not in usados:
            self.unidade = ""
        for campo in ("valor_inicial", "meta", "limite_inferior", "limite_superior"):
            if campo not in usados:
                setattr(self, campo, None)
        # Limites que a regra de manutenção não usa também são descartados.
        if self.regra == self.Regra.MANTER_ACIMA:
            self.limite_superior = None
        if self.regra == self.Regra.MANTER_ABAIXO:
            self.limite_inferior = None

    def clean(self):
        self.titulo = espacos_simples(self.titulo)
        self.descricao = (self.descricao or "").strip()
        self.unidade = espacos_simples(self.unidade)
        self.chave_titulo = chave_busca(self.titulo)
        if self.tipo_medicao in self.CAMPOS_POR_TIPO:
            self._limpar_campos_nao_usados()

        erros = {}
        anterior = (
            ResultadoChave.objects.filter(pk=self.pk)
            .values("responsavel_id", "tipo_medicao")
            .first()
            if self.pk
            else None
        ) or {}
        if anterior and self.tipo_medicao != anterior["tipo_medicao"] and self.checkins.exists():
            erros["tipo_medicao"] = (
                "O tipo de medição não pode mudar depois de registrados check-ins. "
                "Cancele este KR e crie outro, preservando o histórico."
            )
        if self.responsavel_id and self.responsavel_id != anterior.get("responsavel_id"):
            problema = problema_do_responsavel(
                self.responsavel, self.objetivo.empresa_id if self.objetivo_id else None
            )
            if problema:
                erros["responsavel"] = problema

        if self.tipo_medicao in self.CAMPOS_POR_TIPO:
            try:
                dominio.validar(self.medicao())
            except dominio.ErroDeMedicao as exc:
                erros[self._campo_do_erro(str(exc))] = str(exc)
        if erros:
            raise ValidationError(erros)

    def _campo_do_erro(self, mensagem: str) -> str:
        """Associa a mensagem de validação da medição ao campo mais adequado do formulário."""
        if "regra" in mensagem:
            return "regra"
        if "limite máximo" in mensagem and "mínimo deve" not in mensagem:
            return "limite_superior"
        if "limite" in mensagem:
            return "limite_inferior"
        return "meta"


class Marco(models.Model):
    """Etapa de um KR do tipo Marcos. Todos os marcos têm o mesmo peso (Q-10)."""

    kr = models.ForeignKey(
        ResultadoChave, on_delete=models.PROTECT, related_name="marcos", verbose_name="KR"
    )
    descricao = models.CharField("descrição", max_length=200)
    ordem = models.PositiveSmallIntegerField("ordem")
    prazo = models.DateField("prazo", null=True, blank=True)

    class Meta:
        verbose_name = "marco"
        verbose_name_plural = "marcos"
        ordering = ["kr_id", "ordem", "id"]

    def __str__(self):
        return f"{self.ordem}. {self.descricao}"
