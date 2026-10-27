from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm

from apps.contas.services import normalizar_email


class EntrarForm(AuthenticationForm):
    """Login pelo e-mail (guardado em `username`, em minúsculas)."""

    error_messages = {
        "invalid_login": "E-mail ou senha incorretos.",
        "inactive": "Esta conta está desativada. Fale com o administrador.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "E-mail"
        self.fields["username"].widget.attrs.update({"autocomplete": "email", "inputmode": "email"})

    def clean_username(self):
        return normalizar_email(self.cleaned_data.get("username"))


class TrocarSenhaForm(SetPasswordForm):
    """Nova senha (duas vezes); a senha atual não é pedida porque a sessão já é do usuário."""


class UsuarioForm(forms.Form):
    nome = forms.CharField(label="Nome", max_length=300)
    email = forms.EmailField(label="E-mail")
    administrador = forms.BooleanField(
        label="Administrador",
        required=False,
        help_text="Pode cadastrar e desativar usuários e redefinir senhas.",
    )
