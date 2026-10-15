import pytest

from apps.core.templatetags.interface import iniciais, tom_avatar


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("Ana Maria Souza", "AS"),
        ("ana", "AN"),
        ("  João   da Silva ", "JS"),
        ("Pessoa EF01-3", "PE"),
        ("", "?"),
        (None, "?"),
    ],
)
def test_iniciais(nome, esperado):
    assert iniciais(nome) == esperado


def test_tom_avatar_estavel_e_tolerante():
    assert tom_avatar(7) == tom_avatar(7)
    assert tom_avatar(0) != tom_avatar(1)
    assert tom_avatar("x") == "primario"
