"""Apoio às views com formulários."""

from django import forms
from django.core.exceptions import ValidationError


class CampoVersao(forms.IntegerField):
    """Campo oculto com a versão do registro que está sendo editado."""

    widget = forms.HiddenInput

    def __init__(self, **kwargs):
        super().__init__(min_value=1, **kwargs)


def aplicar_erros(form: forms.Form, erro: ValidationError) -> None:
    """Leva os erros de validação do modelo/service para o formulário.

    Erros de campos que não existem no formulário viram erros gerais.
    """
    if hasattr(erro, "error_dict"):
        for campo, mensagens in erro.message_dict.items():
            destino = campo if campo in form.fields else None
            for mensagem in mensagens:
                form.add_error(destino, mensagem)
    else:
        for mensagem in erro.messages:
            form.add_error(None, mensagem)
