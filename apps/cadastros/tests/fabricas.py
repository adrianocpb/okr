"""Criação de dados fictícios para os testes."""

from apps.cadastros import services
from apps.core.acesso import Ator, EscopoAcesso

ATOR = Ator.local()
TODAS = EscopoAcesso.todas()


def empresa(nome="Empresa Alfa", sigla="ALF"):
    return services.criar_empresa(nome=nome, sigla=sigla, ator=ATOR, escopo=TODAS)


def pessoa(nome="Fulana de Tal", email=None, empresas=()):
    return services.criar_pessoa(
        nome=nome,
        email=email,
        empresas_ids=[e.pk for e in empresas],
        ator=ATOR,
        escopo=TODAS,
    )
