from django import forms
from django.db.models import Q

from apps.cadastros import selectors
from apps.cadastros.models import Empresa, Pessoa
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
