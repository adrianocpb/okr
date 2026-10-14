from datetime import date

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import ModeloArquivavel
from apps.core.texto import chave_busca, espacos_simples


class Empresa(ModeloArquivavel):
    """Empresa do grupo. Campos definidos em Q-01: somente nome e sigla."""

    nome = models.CharField("nome", max_length=150)
    sigla = models.CharField(
        "sigla",
        max_length=20,
        unique=True,
        error_messages={"unique": "Já existe uma empresa com esta sigla."},
    )
    # Nome sem acentos e em minúsculas: garante unicidade e permite busca
    # sem distinção de acentos em qualquer banco.
    chave_nome = models.CharField(max_length=150, unique=True, editable=False)

    campos_nao_auditados = frozenset({"chave_nome"})

    class Meta:
        verbose_name = "empresa"
        verbose_name_plural = "empresas"
        ordering = ["chave_nome"]

    def __str__(self):
        return f"{self.sigla} — {self.nome}"

    @property
    def empresa_para_auditoria(self) -> int | None:
        return self.pk

    def clean(self):
        self.nome = espacos_simples(self.nome)
        self.sigla = espacos_simples(self.sigla).upper()
        self.chave_nome = chave_busca(self.nome)
        if (
            self.chave_nome
            and Empresa.objects.exclude(pk=self.pk).filter(chave_nome=self.chave_nome).exists()
        ):
            raise ValidationError({"nome": "Já existe uma empresa com este nome."})

    def validate_unique(self, exclude=None):
        # A unicidade de chave_nome é verificada em clean() com mensagem no campo
        # "nome"; a restrição do banco permanece como proteção final.
        super().validate_unique(exclude={*(exclude or ()), "chave_nome"})


class Pessoa(ModeloArquivavel):
    """Pessoa que pode assumir responsabilidades em OKRs (independe de login).

    Pode estar vinculada a várias empresas do grupo (Q-02).
    """

    nome = models.CharField("nome", max_length=150)
    email = models.EmailField(
        "e-mail",
        null=True,
        blank=True,
        unique=True,
        error_messages={"unique": "Já existe uma pessoa com este e-mail."},
    )
    empresas = models.ManyToManyField(
        Empresa,
        through="VinculoPessoaEmpresa",
        related_name="pessoas",
        verbose_name="empresas",
    )
    chave_nome = models.CharField(max_length=150, editable=False, db_index=True)

    campos_nao_auditados = frozenset({"chave_nome"})

    class Meta:
        verbose_name = "pessoa"
        verbose_name_plural = "pessoas"
        ordering = ["chave_nome", "id"]

    def __str__(self):
        return self.nome

    def clean(self):
        self.nome = espacos_simples(self.nome)
        self.email = (self.email or "").strip().lower() or None
        self.chave_nome = chave_busca(self.nome)


class VinculoPessoaEmpresa(models.Model):
    pessoa = models.ForeignKey(Pessoa, on_delete=models.PROTECT, related_name="vinculos")
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name="vinculos")
    criado_em = models.DateTimeField("vinculado em", auto_now_add=True)

    class Meta:
        verbose_name = "vínculo de pessoa com empresa"
        verbose_name_plural = "vínculos de pessoas com empresas"
        constraints = [
            models.UniqueConstraint(
                fields=["pessoa", "empresa"], name="vinculo_pessoa_empresa_unico"
            )
        ]

    def __str__(self):
        return f"{self.pessoa} em {self.empresa.sigla}"


class Ciclo(ModeloArquivavel):
    """Ciclo de OKRs de uma empresa (Q-03: cada empresa tem os seus).

    Ciclos trimestrais pertencem a um ciclo anual da mesma empresa e ficam dentro
    do período dele. A situação (planejado, em andamento, encerrado) é calculada
    pelas datas.
    """

    class Tipo(models.TextChoices):
        ANUAL = "anual", "Anual"
        TRIMESTRAL = "trimestral", "Trimestral"

    class Situacao(models.TextChoices):
        PLANEJADO = "planejado", "Planejado"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        ENCERRADO = "encerrado", "Encerrado"

    TRIMESTRES = [
        (1, "1º trimestre"),
        (2, "2º trimestre"),
        (3, "3º trimestre"),
        (4, "4º trimestre"),
    ]

    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, related_name="ciclos", verbose_name="empresa"
    )
    tipo = models.CharField("tipo", max_length=12, choices=Tipo.choices)
    ano = models.PositiveSmallIntegerField(
        "ano",
        validators=[MinValueValidator(2000), MaxValueValidator(2100)],
        help_text="Ano de referência do ciclo (pode diferir do ano civil em anos fiscais).",
    )
    trimestre = models.PositiveSmallIntegerField(
        "trimestre", null=True, blank=True, choices=TRIMESTRES
    )
    ciclo_anual = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="trimestres",
        verbose_name="ciclo anual",
    )
    data_inicio = models.DateField("data de início")
    data_fim = models.DateField("data de término")

    class Meta:
        verbose_name = "ciclo"
        verbose_name_plural = "ciclos"
        ordering = ["empresa__sigla", "-ano", "tipo", "trimestre"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(data_fim__gt=models.F("data_inicio")),
                name="ciclo_datas_validas",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(tipo="anual", trimestre__isnull=True, ciclo_anual__isnull=True)
                    | models.Q(
                        tipo="trimestral",
                        trimestre__gte=1,
                        trimestre__lte=4,
                        ciclo_anual__isnull=False,
                    )
                ),
                name="ciclo_tipo_coerente",
            ),
            models.UniqueConstraint(
                fields=["empresa", "ano"],
                condition=models.Q(tipo="anual", arquivado_em__isnull=True),
                name="ciclo_anual_unico_por_empresa",
            ),
            models.UniqueConstraint(
                fields=["ciclo_anual", "trimestre"],
                condition=models.Q(arquivado_em__isnull=True),
                name="ciclo_trimestre_unico",
            ),
        ]

    def __str__(self):
        return f"{self.empresa.sigla} · {self.rotulo}"

    @property
    def rotulo(self) -> str:
        if self.tipo == self.Tipo.TRIMESTRAL:
            return f"{self.ano} · T{self.trimestre}"
        return str(self.ano)

    @property
    def periodo(self) -> str:
        return f"{self.data_inicio:%d/%m/%Y} a {self.data_fim:%d/%m/%Y}"

    def situacao_em(self, hoje: date) -> str:
        if hoje < self.data_inicio:
            return self.Situacao.PLANEJADO
        if hoje > self.data_fim:
            return self.Situacao.ENCERRADO
        return self.Situacao.EM_ANDAMENTO

    @property
    def situacao(self) -> str:
        return self.situacao_em(timezone.localdate())

    @property
    def situacao_rotulo(self) -> str:
        return self.Situacao(self.situacao).label

    def clean(self):
        erros = {}
        if self.data_inicio and self.data_fim and self.data_fim <= self.data_inicio:
            erros["data_fim"] = "A data de término deve ser posterior à data de início."

        if self.tipo == self.Tipo.ANUAL:
            self.trimestre = None
            self.ciclo_anual = None
            self._validar_anual(erros)
        elif self.tipo == self.Tipo.TRIMESTRAL:
            self._validar_trimestral(erros)

        if not erros and not self.arquivado:
            conflito = self.conflito_de_periodo()
            if conflito:
                erros[NON_FIELD_ERRORS] = (
                    f"O período se sobrepõe ao ciclo {conflito.rotulo} ({conflito.periodo})."
                )
        if erros:
            raise ValidationError(erros)

    def _validar_anual(self, erros: dict) -> None:
        outros_ativos = Ciclo.objects.filter(arquivado_em__isnull=True).exclude(pk=self.pk)
        if (
            not self.arquivado
            and self.empresa_id
            and self.ano
            and outros_ativos.filter(
                tipo=self.Tipo.ANUAL, empresa_id=self.empresa_id, ano=self.ano
            ).exists()
        ):
            erros["ano"] = f"Esta empresa já tem um ciclo anual de {self.ano}."
        if self.pk is None:
            return
        trimestres = self.trimestres.filter(arquivado_em__isnull=True)
        ano_anterior = Ciclo.objects.filter(pk=self.pk).values_list("ano", flat=True).first()
        if ano_anterior is not None and ano_anterior != self.ano and trimestres.exists():
            erros["ano"] = "Não é possível alterar o ano de um ciclo que já possui trimestres."
        if (
            self.data_inicio
            and self.data_fim
            and trimestres.filter(
                models.Q(data_inicio__lt=self.data_inicio) | models.Q(data_fim__gt=self.data_fim)
            ).exists()
        ):
            erros["data_inicio"] = (
                "O período deve continuar abrangendo todos os trimestres do ciclo."
            )

    def _validar_trimestral(self, erros: dict) -> None:
        anual = self.ciclo_anual
        if anual is None:
            erros["ciclo_anual"] = "Informe o ciclo anual ao qual o trimestre pertence."
            return
        if anual.tipo != self.Tipo.ANUAL:
            erros["ciclo_anual"] = "O trimestre deve pertencer a um ciclo anual."
            return
        # Empresa e ano vêm sempre do ciclo anual: um trimestre nunca fica em outra empresa.
        self.empresa_id = anual.empresa_id
        self.ano = anual.ano
        if self.trimestre not in (1, 2, 3, 4):
            erros["trimestre"] = "Escolha um trimestre de 1 a 4."
        elif (
            not self.arquivado
            and Ciclo.objects.filter(
                ciclo_anual=anual, trimestre=self.trimestre, arquivado_em__isnull=True
            )
            .exclude(pk=self.pk)
            .exists()
        ):
            erros["trimestre"] = f"O ciclo anual {anual.ano} já tem o {self.trimestre}º trimestre."
        if (
            self.data_inicio
            and self.data_fim
            and (self.data_inicio < anual.data_inicio or self.data_fim > anual.data_fim)
        ):
            erros["data_inicio"] = (
                f"O trimestre deve estar dentro do período do ciclo anual ({anual.periodo})."
            )

    def conflito_de_periodo(self):
        """Outro ciclo ativo do mesmo tipo e empresa com período sobreposto, se houver."""
        if not (self.empresa_id and self.data_inicio and self.data_fim):
            return None
        return (
            Ciclo.objects.filter(
                empresa_id=self.empresa_id,
                tipo=self.tipo,
                arquivado_em__isnull=True,
                data_inicio__lte=self.data_fim,
                data_fim__gte=self.data_inicio,
            )
            .exclude(pk=self.pk)
            .order_by("data_inicio")
            .first()
        )

    def validate_constraints(self, exclude=None):
        # As restrições do banco são verificadas em clean() com mensagens amigáveis
        # associadas aos campos; no banco elas permanecem como proteção final.
        return None
