"""Dados fictícios para os testes de OKRs."""

from decimal import Decimal

from apps.cadastros.tests import fabricas as cadastros
from apps.cadastros.tests.fabricas import ATOR, TODAS
from apps.okrs import services


class Cenario:
    """Empresa com pessoas, ciclo anual 2026 e trimestres T1 e T2."""

    def __init__(self, nome="Alfa", sigla="ALF"):
        self.empresa = cadastros.empresa(nome=nome, sigla=sigla)
        self.ana = cadastros.pessoa(nome=f"Ana {sigla}", empresas=[self.empresa])
        self.bruno = cadastros.pessoa(nome=f"Bruno {sigla}", empresas=[self.empresa])
        self.anual = cadastros.ciclo_anual(self.empresa, 2026)
        self.t1 = cadastros.trimestre(self.anual, 1)
        self.t2 = cadastros.trimestre(self.anual, 2)

    def objetivo(self, titulo="Crescer receita", ciclo=None, owner=None, sponsor=None, **extra):
        dados = {
            "titulo": titulo,
            "descricao": "",
            "ciclo": ciclo or self.anual,
            "owner": owner or self.ana,
            "sponsor": sponsor or self.bruno,
            "status": "ativo",
            "comentario_status": "",
            **extra,
        }
        return services.criar_objetivo(
            empresa_id=self.empresa.pk, dados=dados, ator=ATOR, escopo=TODAS
        )

    def kr(self, objetivo, titulo="Novos clientes", responsavel=None, **medicao):
        dados = {
            "titulo": titulo,
            "responsavel": responsavel or self.ana,
            "tipo_medicao": "numerico",
            "regra": "crescente",
            "unidade": "clientes",
            "valor_inicial": Decimal("100"),
            "meta": Decimal("150"),
            **medicao,
        }
        return services.criar_kr(objetivo_id=objetivo.pk, dados=dados, ator=ATOR, escopo=TODAS)

    def iniciativa(self, objetivo, titulo="Campanha de vendas", krs=(), responsavel=None, **extra):
        dados = {"titulo": titulo, "responsavel": responsavel or self.bruno, **extra}
        return services.criar_iniciativa(
            objetivo_id=objetivo.pk,
            dados=dados,
            kr_ids=[kr.pk for kr in krs],
            ator=ATOR,
            escopo=TODAS,
        )
