"""Criação de dados fictícios para os testes."""

from apps.cadastros import services
from apps.core.acesso import Ator, EscopoAcesso

ATOR = Ator.local()
TODAS = EscopoAcesso.todas()


def empresa(nome="Empresa Alfa", sigla="ALF"):
    return services.criar_empresa(nome=nome, sigla=sigla, ator=ATOR, escopo=TODAS)


def ciclo_anual(empresa, ano=2026, data_inicio=None, data_fim=None):
    return services.criar_ciclo_anual(
        empresa_id=empresa.pk,
        ano=ano,
        data_inicio=data_inicio,
        data_fim=data_fim,
        ator=ATOR,
        escopo=TODAS,
    )


def trimestre(anual, numero=1, data_inicio=None, data_fim=None):
    return services.criar_trimestre(
        ciclo_anual_id=anual.pk,
        trimestre=numero,
        data_inicio=data_inicio,
        data_fim=data_fim,
        ator=ATOR,
        escopo=TODAS,
    )


def pessoa(nome="Fulana de Tal", email=None, empresas=()):
    return services.criar_pessoa(
        nome=nome,
        email=email,
        empresas_ids=[e.pk for e in empresas],
        ator=ATOR,
        escopo=TODAS,
    )
