from django import forms

from apps.cadastros.models import Ciclo, Empresa, Pessoa
from apps.core.formularios import CampoVersao
from apps.okrs import selectors
from apps.okrs.models import Iniciativa, Objetivo, ResultadoChave


class CampoCiclo(forms.ModelChoiceField):
    def label_from_instance(self, ciclo):
        rotulo = f"{ciclo.rotulo} ({ciclo.periodo})"
        return f"{rotulo} — arquivado" if ciclo.arquivado else rotulo


class CampoPessoa(forms.ModelChoiceField):
    def label_from_instance(self, pessoa):
        return f"{pessoa.nome} (arquivada)" if pessoa.arquivado else pessoa.nome


class ObjetivoForm(forms.Form):
    titulo = forms.CharField(label="Título", max_length=200)
    descricao = forms.CharField(
        label="Descrição", required=False, widget=forms.Textarea(attrs={"rows": 4})
    )
    ciclo = CampoCiclo(label="Ciclo", queryset=Ciclo.objects.none(), empty_label="Selecione…")
    owner = CampoPessoa(
        label="Owner",
        queryset=Pessoa.objects.none(),
        empty_label="Selecione…",
        help_text="Responsável pela condução do objetivo.",
    )
    sponsor = CampoPessoa(
        label="Sponsor",
        queryset=Pessoa.objects.none(),
        empty_label="Selecione…",
        help_text="Patrocinador: apoia e ajuda a remover impedimentos.",
    )
    status = forms.ChoiceField(
        label="Status", choices=Objetivo.Status.choices, initial=Objetivo.Status.ATIVO
    )
    comentario_status = forms.CharField(
        label="Comentário do status",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Obrigatório ao concluir ou cancelar o objetivo.",
    )
    versao = CampoVersao(required=False)

    def __init__(self, *args, empresa: Empresa, objetivo: Objetivo | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ciclo"].queryset = selectors.ciclos_para_objetivo(
            empresa, objetivo.ciclo if objetivo else None
        )
        pessoas = selectors.pessoas_para_responsabilidade(
            empresa, *((objetivo.owner, objetivo.sponsor) if objetivo else ())
        )
        self.fields["owner"].queryset = pessoas
        self.fields["sponsor"].queryset = pessoas

    def dados(self) -> dict:
        return {
            campo: self.cleaned_data[campo]
            for campo in (
                "titulo",
                "descricao",
                "ciclo",
                "owner",
                "sponsor",
                "status",
                "comentario_status",
            )
        }


def _decimal_para_formulario(numero):
    """Decimal('100.5000') → '100,5' (sem zeros à direita, com vírgula)."""
    if numero is None:
        return None
    texto = format(numero.normalize(), "f")
    return texto.replace(".", ",")


class CampoValor(forms.DecimalField):
    """Valor decimal digitado em formato brasileiro (ex.: 1.234,56)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("max_digits", 18)
        kwargs.setdefault("decimal_places", 4)
        kwargs.setdefault("localize", True)
        kwargs.setdefault("widget", forms.TextInput(attrs={"inputmode": "decimal"}))
        super().__init__(**kwargs)


TipoKR = ResultadoChave.TipoMedicao
RegraKR = ResultadoChave.Regra


class KRForm(forms.Form):
    titulo = forms.CharField(label="Título", max_length=200)
    descricao = forms.CharField(
        label="Descrição", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    responsavel = CampoPessoa(
        label="Responsável",
        queryset=Pessoa.objects.none(),
        empty_label="Selecione…",
        help_text="Responsável principal pelo KR.",
    )
    tipo_medicao = forms.ChoiceField(
        label="Tipo de medição", choices=TipoKR.choices, widget=forms.RadioSelect
    )
    sentido = forms.ChoiceField(
        label="Sentido",
        required=False,
        choices=[
            (RegraKR.CRESCENTE, RegraKR.CRESCENTE.label),
            (RegraKR.DECRESCENTE, RegraKR.DECRESCENTE.label),
        ],
        widget=forms.RadioSelect,
    )
    regra_manutencao = forms.ChoiceField(
        label="Regra",
        required=False,
        choices=[
            (RegraKR.MANTER_ACIMA, RegraKR.MANTER_ACIMA.label),
            (RegraKR.MANTER_ABAIXO, RegraKR.MANTER_ABAIXO.label),
            (RegraKR.MANTER_ENTRE, RegraKR.MANTER_ENTRE.label),
        ],
        widget=forms.RadioSelect,
    )
    unidade = forms.CharField(
        label="Unidade",
        max_length=30,
        required=False,
        help_text="Exemplos: R$, %, clientes, dias, pontos.",
    )
    casas_decimais = forms.IntegerField(label="Casas decimais", min_value=0, max_value=4, initial=0)
    valor_inicial = CampoValor(label="Valor inicial", help_text="Valor no início do ciclo.")
    meta = CampoValor(label="Meta")
    limite_inferior = CampoValor(label="Limite mínimo")
    limite_superior = CampoValor(label="Limite máximo")
    frequencia_checkin_dias = forms.IntegerField(
        label="Frequência de check-in (dias)",
        min_value=1,
        max_value=365,
        initial=ResultadoChave.FREQUENCIA_PADRAO_DIAS,
        help_text="Padrão: 14 dias (quinzenal). Use 7 para semanal ou 30 para mensal.",
    )
    status = forms.ChoiceField(
        label="Status",
        choices=ResultadoChave.Status.choices,
        initial=ResultadoChave.Status.ATIVO,
    )
    versao = CampoVersao(required=False)

    # Campos exibidos conforme o tipo de medição (usado pelo template e pelo script da tela).
    CAMPOS_DO_TIPO = {
        "sentido": [TipoKR.NUMERICO],
        "valor_inicial": [TipoKR.NUMERICO],
        "meta": [TipoKR.NUMERICO],
        "regra_manutencao": [TipoKR.MANUTENCAO],
        "limite_inferior": [TipoKR.MANUTENCAO],
        "limite_superior": [TipoKR.MANUTENCAO],
        "unidade": [TipoKR.NUMERICO, TipoKR.MANUTENCAO],
        "casas_decimais": [TipoKR.NUMERICO, TipoKR.MANUTENCAO],
    }

    def __init__(self, *args, objetivo: Objetivo, kr: ResultadoChave | None = None, **kwargs):
        if kr is not None:
            kwargs.setdefault("initial", self.inicial_de(kr))
        super().__init__(*args, **kwargs)
        self.fields["responsavel"].queryset = selectors.pessoas_para_responsabilidade(
            objetivo.empresa, kr.responsavel if kr else None
        )

    @staticmethod
    def inicial_de(kr: ResultadoChave) -> dict:
        return {
            "titulo": kr.titulo,
            "descricao": kr.descricao,
            "responsavel": kr.responsavel_id,
            "tipo_medicao": kr.tipo_medicao,
            "sentido": kr.regra if kr.tipo_medicao == TipoKR.NUMERICO else "",
            "regra_manutencao": kr.regra if kr.tipo_medicao == TipoKR.MANUTENCAO else "",
            "unidade": kr.unidade,
            "casas_decimais": kr.casas_decimais,
            "valor_inicial": _decimal_para_formulario(kr.valor_inicial),
            "meta": _decimal_para_formulario(kr.meta),
            "limite_inferior": _decimal_para_formulario(kr.limite_inferior),
            "limite_superior": _decimal_para_formulario(kr.limite_superior),
            "frequencia_checkin_dias": kr.frequencia_checkin_dias,
            "status": kr.status,
            "versao": kr.versao,
        }

    def campos_com_tipos(self):
        """Pares (campo, tipos em que aparece) para o template marcar cada bloco."""
        for nome in self.fields:
            if nome == "versao":
                continue
            yield self[nome], " ".join(self.CAMPOS_DO_TIPO.get(nome, []))

    def clean(self):
        dados = super().clean()
        tipo = dados.get("tipo_medicao")
        if tipo == TipoKR.NUMERICO and not dados.get("sentido"):
            self.add_error("sentido", "Escolha se a métrica é crescente ou decrescente.")
        if tipo == TipoKR.MANUTENCAO and not dados.get("regra_manutencao"):
            self.add_error("regra_manutencao", "Escolha a regra de manutenção.")
        return dados

    def dados(self) -> dict:
        dados = self.cleaned_data
        tipo = dados["tipo_medicao"]
        regra = {
            TipoKR.NUMERICO: dados.get("sentido"),
            TipoKR.MANUTENCAO: dados.get("regra_manutencao"),
        }
        return {
            "titulo": dados["titulo"],
            "descricao": dados["descricao"],
            "responsavel": dados["responsavel"],
            "tipo_medicao": tipo,
            "regra": regra.get(tipo) or "",
            "unidade": dados["unidade"],
            "casas_decimais": dados["casas_decimais"],
            "valor_inicial": dados["valor_inicial"],
            "meta": dados["meta"],
            "limite_inferior": dados["limite_inferior"],
            "limite_superior": dados["limite_superior"],
            "frequencia_checkin_dias": dados["frequencia_checkin_dias"],
            "status": dados["status"],
        }


class MarcoForm(forms.Form):
    descricao = forms.CharField(label="Novo marco", max_length=200)
    prazo = forms.DateField(
        label="Prazo",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )


class VinculoForm(forms.Form):
    objetivo_anual = forms.ModelChoiceField(
        label="Objetivo anual", queryset=Objetivo.objects.none(), empty_label="Selecione…"
    )

    def __init__(self, *args, objetivo: Objetivo, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["objetivo_anual"].queryset = selectors.anuais_vinculaveis(objetivo)


class CampoKRs(forms.ModelMultipleChoiceField):
    def label_from_instance(self, kr):
        return (
            kr.titulo
            if kr.status == kr.Status.ATIVO
            else f"{kr.titulo} ({kr.get_status_display().lower()})"
        )


class IniciativaForm(forms.Form):
    titulo = forms.CharField(label="Título", max_length=200)
    descricao = forms.CharField(
        label="Descrição", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    responsavel = CampoPessoa(
        label="Responsável",
        queryset=Pessoa.objects.none(),
        empty_label="Selecione…",
        help_text="Responsável principal pela execução.",
    )
    prazo = forms.DateField(
        label="Prazo",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    status = forms.ChoiceField(
        label="Status", choices=Iniciativa.Status.choices, initial=Iniciativa.Status.NAO_INICIADA
    )
    krs = CampoKRs(
        label="KRs para os quais contribui",
        queryset=ResultadoChave.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            "Opcional. Apenas KRs deste objetivo. A iniciativa não altera o progresso dos KRs."
        ),
    )
    versao = CampoVersao(required=False)

    def __init__(self, *args, objetivo: Objetivo, iniciativa: Iniciativa | None = None, **kwargs):
        if iniciativa is not None:
            kwargs.setdefault(
                "initial",
                {
                    "titulo": iniciativa.titulo,
                    "descricao": iniciativa.descricao,
                    "responsavel": iniciativa.responsavel_id,
                    "prazo": iniciativa.prazo,
                    "status": iniciativa.status,
                    "krs": [kr.pk for kr in iniciativa.krs.all()],
                    "versao": iniciativa.versao,
                },
            )
        super().__init__(*args, **kwargs)
        self.fields["responsavel"].queryset = selectors.pessoas_para_responsabilidade(
            objetivo.empresa, iniciativa.responsavel if iniciativa else None
        )
        self.fields["krs"].queryset = objetivo.krs.order_by("id")

    def dados(self) -> dict:
        return {
            campo: self.cleaned_data[campo]
            for campo in ("titulo", "descricao", "responsavel", "prazo", "status")
        }

    def kr_ids(self) -> list[int]:
        return [kr.pk for kr in self.cleaned_data["krs"]]
