from datetime import date

from django import forms

from apps.acompanhamento.models import CheckIn
from apps.okrs import selectors as okrs
from apps.okrs.forms import CampoPessoa, CampoValor, _decimal_para_formulario
from apps.okrs.models import Iniciativa, Marco, ResultadoChave

Tipo = ResultadoChave.TipoMedicao


class CheckInForm(forms.Form):
    data_referencia = forms.DateField(
        label="Data de referência",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text="Data à qual o acompanhamento se refere (não pode ser futura).",
    )
    valor = CampoValor(label="Valor medido")
    concluido = forms.TypedChoiceField(
        label="Foi concluído?",
        choices=[("sim", "Sim"), ("nao", "Não")],
        coerce=lambda valor: valor == "sim",
        widget=forms.RadioSelect,
    )
    marcos = forms.ModelMultipleChoiceField(
        label="Marcos concluídos",
        queryset=Marco.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Marque todos os marcos concluídos até a data de referência.",
    )
    status_informado = forms.ChoiceField(
        label="Status", choices=CheckIn.Status.choices, widget=forms.RadioSelect
    )
    comentario = forms.CharField(
        label="Comentário de acompanhamento",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    dificuldades = forms.CharField(
        label="Dificuldades, riscos ou impedimentos",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    proximos_passos = forms.CharField(
        label="Próximos passos", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    autor_informado = CampoPessoa(
        label="Quem está registrando",
        queryset=None,
        empty_label="Selecione…",
        help_text="Sem login, a autoria é informada e aparece como não verificada.",
    )
    confirmar_ciclo_encerrado = forms.BooleanField(
        label="Confirmo o registro de um check-in após o fim do ciclo",
        required=False,
    )
    justificativa_retificacao = forms.CharField(
        label="Motivo da retificação",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="O check-in original continua no histórico, marcado como retificado.",
    )

    def __init__(
        self,
        *args,
        kr: ResultadoChave,
        hoje: date,
        original: CheckIn | None = None,
        **kwargs,
    ):
        ciclo = kr.objetivo.ciclo
        inicial = kwargs.setdefault("initial", {})
        inicial.setdefault("data_referencia", min(hoje, ciclo.data_fim))
        inicial.setdefault("autor_informado", kr.responsavel_id)
        if original is not None:
            inicial.update(self._inicial_da_retificacao(original))
        super().__init__(*args, **kwargs)

        self.fields["autor_informado"].queryset = okrs.pessoas_para_responsabilidade(
            kr.objetivo.empresa
        )
        if kr.unidade:
            self.fields["valor"].label = f"Valor medido ({kr.unidade})"
        self.fields["marcos"].queryset = kr.marcos.all()

        remover = {
            Tipo.NUMERICO: {"concluido", "marcos"},
            Tipo.MANUTENCAO: {"concluido", "marcos"},
            Tipo.BINARIO: {"valor", "marcos"},
            Tipo.MARCOS: {"valor", "concluido"},
        }[kr.tipo_medicao]
        if hoje <= ciclo.data_fim:
            remover.add("confirmar_ciclo_encerrado")
        if original is None:
            remover.add("justificativa_retificacao")
        else:
            remover.add("data_referencia")  # a retificação mantém a data do original
        for nome in remover:
            del self.fields[nome]

    @staticmethod
    def _inicial_da_retificacao(original: CheckIn) -> dict:
        return {
            "valor": _decimal_para_formulario(original.valor),
            "concluido": {True: "sim", False: "nao"}.get(original.concluido),
            "marcos": [m.pk for m in original.marcos_concluidos.all()],
            "status_informado": original.status_informado,
            "comentario": original.comentario,
            "dificuldades": original.dificuldades,
            "proximos_passos": original.proximos_passos,
            "autor_informado": original.autor_informado_id,
        }

    def dados(self) -> dict:
        dados = dict(self.cleaned_data)
        dados["marcos_ids"] = [m.pk for m in dados.pop("marcos", [])]
        return dados


class AtualizacaoIniciativaForm(forms.Form):
    data_referencia = forms.DateField(
        label="Data de referência",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    status = forms.ChoiceField(
        label="Status da iniciativa",
        choices=Iniciativa.Status.choices,
        widget=forms.RadioSelect,
        help_text="Passa a ser o status atual da iniciativa.",
    )
    comentario = forms.CharField(
        label="Comentário", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    dificuldades = forms.CharField(
        label="Dificuldades ou impedimentos",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    proximos_passos = forms.CharField(
        label="Próximos passos", required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    autor_informado = CampoPessoa(
        label="Quem está registrando",
        queryset=None,
        empty_label="Selecione…",
        help_text="Sem login, a autoria é informada e aparece como não verificada.",
    )

    def __init__(self, *args, iniciativa: Iniciativa, hoje: date, **kwargs):
        inicial = kwargs.setdefault("initial", {})
        inicial.setdefault("data_referencia", hoje)
        inicial.setdefault("status", iniciativa.status)
        inicial.setdefault("autor_informado", iniciativa.responsavel_id)
        super().__init__(*args, **kwargs)
        self.fields["autor_informado"].queryset = okrs.pessoas_para_responsabilidade(
            iniciativa.objetivo.empresa
        )
