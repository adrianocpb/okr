from django import forms
from django.db.models import Q

from apps.cadastros import selectors
from apps.cadastros.models import Ciclo, Empresa, Pessoa
from apps.core.acesso import EscopoAcesso
from apps.core.formularios import CampoVersao


class EmpresaForm(forms.Form):
    nome = forms.CharField(label="Nome", max_length=150)
    sigla = forms.CharField(
        label="Sigla",
        max_length=20,
        help_text="Identificação curta, por exemplo ABC. É gravada em maiúsculas.",
    )
    versao = CampoVersao(required=False)


class CampoData(forms.DateField):
    """Data com seletor nativo do navegador (envia AAAA-MM-DD, aceito pelo Django)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("widget", forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
        super().__init__(**kwargs)


class CicloAnualForm(forms.Form):
    empresa = forms.ModelChoiceField(
        label="Empresa", queryset=Empresa.objects.none(), empty_label="Selecione…"
    )
    ano = forms.IntegerField(label="Ano", min_value=2000, max_value=2100)
    data_inicio = CampoData(
        label="Data de início",
        required=False,
        help_text="Deixe as datas em branco para usar o ano civil (01/01 a 31/12).",
    )
    data_fim = CampoData(label="Data de término", required=False)

    def __init__(self, *args, escopo: EscopoAcesso, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["empresa"].queryset = selectors.empresas_para_vinculo(escopo).order_by("sigla")


class TrimestreForm(forms.Form):
    trimestre = forms.TypedChoiceField(label="Trimestre", choices=Ciclo.TRIMESTRES, coerce=int)
    data_inicio = CampoData(
        label="Data de início",
        required=False,
        help_text="Deixe as datas em branco para usar o período padrão do trimestre.",
    )
    data_fim = CampoData(label="Data de término", required=False)


class CicloEdicaoForm(forms.Form):
    ano = forms.IntegerField(label="Ano", min_value=2000, max_value=2100)
    trimestre = forms.TypedChoiceField(label="Trimestre", choices=Ciclo.TRIMESTRES, coerce=int)
    data_inicio = CampoData(label="Data de início")
    data_fim = CampoData(label="Data de término")
    versao = CampoVersao(required=False)

    def __init__(self, *args, ciclo: Ciclo, **kwargs):
        super().__init__(*args, **kwargs)
        # Empresa, tipo e ciclo anual não mudam; o trimestre herda o ano do ciclo anual.
        del self.fields["trimestre" if ciclo.tipo == Ciclo.Tipo.ANUAL else "ano"]


class CampoEmpresas(forms.ModelMultipleChoiceField):
    def label_from_instance(self, empresa):
        rotulo = f"{empresa.sigla} — {empresa.nome}"
        return f"{rotulo} (arquivada)" if empresa.arquivado else rotulo


class PessoaForm(forms.Form):
    nome = forms.CharField(label="Nome", max_length=150)
    email = forms.EmailField(label="E-mail", required=False, help_text="Opcional.")
    empresas = CampoEmpresas(
        label="Empresas",
        queryset=Empresa.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        help_text="Empresas do grupo às quais a pessoa está vinculada.",
        error_messages={"required": "Selecione ao menos uma empresa."},
    )
    versao = CampoVersao(required=False)

    def __init__(self, *args, escopo: EscopoAcesso, pessoa: Pessoa | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        disponiveis = selectors.empresas_para_vinculo(escopo)
        if pessoa is not None:
            # Mantém visíveis (e marcadas) empresas já vinculadas, mesmo que arquivadas.
            atuais = escopo.filtrar(pessoa.empresas.all(), campo="id")
            opcoes = Empresa.objects.filter(Q(pk__in=disponiveis) | Q(pk__in=atuais))
        else:
            opcoes = disponiveis
        self.fields["empresas"].queryset = opcoes.order_by("sigla")
