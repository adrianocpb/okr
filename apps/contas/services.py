"""Criação e manutenção de contas de acesso."""

import secrets

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from apps.contas.models import Usuario

# Sem caracteres que se confundem ao copiar (0/O, 1/l/I).
_ALFABETO_SENHA = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def gerar_senha_temporaria(tamanho: int = 14) -> str:
    return "".join(secrets.choice(_ALFABETO_SENHA) for _ in range(tamanho))


def normalizar_email(email: str) -> str:
    return (email or "").strip().lower()


@transaction.atomic
def criar_usuario(*, nome: str, email: str, administrador: bool = False) -> tuple[Usuario, str]:
    """Cria a conta e devolve a senha temporária, que só é exibida uma vez."""
    email = normalizar_email(email)
    nome = " ".join((nome or "").split())
    erros = {}
    if not nome:
        erros["nome"] = "Informe o nome."
    try:
        validate_email(email)
    except ValidationError:
        erros["email"] = "Informe um e-mail válido."
    if "email" not in erros and Usuario.objects.filter(username=email).exists():
        erros["email"] = "Já existe uma conta com este e-mail."
    if erros:
        raise ValidationError(erros)

    primeiro, _, resto = nome.partition(" ")
    senha = gerar_senha_temporaria()
    usuario = Usuario(
        username=email,
        email=email,
        first_name=primeiro[:150],
        last_name=resto[:150],
        is_staff=administrador,
        deve_trocar_senha=True,
    )
    usuario.set_password(senha)
    usuario.save()
    return usuario, senha


def redefinir_senha(usuario: Usuario) -> str:
    senha = gerar_senha_temporaria()
    usuario.set_password(senha)
    usuario.deve_trocar_senha = True
    usuario.save(update_fields=["password", "deve_trocar_senha"])
    return senha


def definir_ativo(usuario: Usuario, ativo: bool, *, por: Usuario) -> None:
    if usuario.pk == por.pk and not ativo:
        raise ValidationError("Você não pode desativar a própria conta.")
    usuario.is_active = ativo
    usuario.save(update_fields=["is_active"])
