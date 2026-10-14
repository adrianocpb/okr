from django import forms

from apps.cadastros.models import Ciclo, Empresa, Pessoa
from apps.core.formularios import CampoVersao
from apps.okrs import selectors
from apps.okrs.models import Objetivo


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


class VinculoForm(forms.Form):
    objetivo_anual = forms.ModelChoiceField(
        label="Objetivo anual", queryset=Objetivo.objects.none(), empty_label="Selecione…"
    )

    def __init__(self, *args, objetivo: Objetivo, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["objetivo_anual"].queryset = selectors.anuais_vinculaveis(objetivo)
