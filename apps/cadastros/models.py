from django.core.exceptions import ValidationError
from django.db import models

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
