"""Quem está agindo (Ator) e o que pode acessar (EscopoAcesso).

Todos os services recebem um `Ator`, e todos os selectors de dados de empresa
recebem um `EscopoAcesso`. Com login, o `Ator` vem do usuário autenticado; o
`Ator.local()` fica para requisições sem usuário (por exemplo, nos testes de
services). O escopo ainda cobre todas as empresas: a restrição por empresa e
os perfis com permissões diferentes ficam para a etapa completa (E13).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from django.db.models import QuerySet


class Origem:
    INTERFACE = "interface"
    COMANDO = "comando"
    SISTEMA = "sistema"

    CHOICES = [
        (INTERFACE, "Interface"),
        (COMANDO, "Comando de administração"),
        (SISTEMA, "Sistema"),
    ]


@dataclass(frozen=True)
class Ator:
    descricao: str
    origem: str = Origem.INTERFACE
    usuario_id: int | None = None

    @property
    def verificado(self) -> bool:
        """Só há identidade verificada quando existe um usuário autenticado."""
        return self.usuario_id is not None

    @classmethod
    def local(cls) -> Ator:
        return cls(descricao="Usuário local (não autenticado)", origem=Origem.INTERFACE)

    @classmethod
    def comando(cls, nome: str) -> Ator:
        return cls(descricao=f"Comando {nome}", origem=Origem.COMANDO)


@dataclass(frozen=True)
class EscopoAcesso:
    """Conjunto de empresas acessíveis. `empresas_ids=None` significa todas."""

    empresas_ids: frozenset[int] | None

    @classmethod
    def todas(cls) -> EscopoAcesso:
        return cls(empresas_ids=None)

    @classmethod
    def restrito(cls, empresas_ids: Iterable[int]) -> EscopoAcesso:
        return cls(empresas_ids=frozenset(empresas_ids))

    def permite(self, empresa_id: int | None) -> bool:
        if self.empresas_ids is None:
            return True
        return empresa_id in self.empresas_ids

    @property
    def irrestrito(self) -> bool:
        return self.empresas_ids is None

    def filtrar(self, queryset: QuerySet, campo: str = "empresa_id") -> QuerySet:
        """Restringe um queryset às empresas do escopo, pelo campo informado."""
        if self.empresas_ids is None:
            return queryset
        return queryset.filter(**{f"{campo}__in": self.empresas_ids})


def ator_da_requisicao(request) -> Ator:
    """Quem está agindo: o usuário autenticado, ou o usuário local sem login."""
    usuario = getattr(request, "user", None)
    if usuario is not None and usuario.is_authenticated:
        return Ator(descricao=usuario.nome_exibicao, usuario_id=usuario.pk)
    return Ator.local()


def escopo_da_requisicao(request) -> EscopoAcesso:
    """Empresas acessíveis. Por enquanto, todas para qualquer usuário autenticado.

    Na etapa completa de autenticação (E13), o escopo passa a derivar das
    empresas autorizadas do usuário; views e services não precisam mudar.
    """
    return EscopoAcesso.todas()
