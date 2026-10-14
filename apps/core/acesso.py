"""Quem está agindo (Ator) e o que pode acessar (EscopoAcesso).

Todos os services recebem um `Ator`, e todos os selectors de dados de empresa
recebem um `EscopoAcesso`. Na versão local, sem login, usa-se `Ator.local()` e
`EscopoAcesso.todas()`. Quando a autenticação existir (E13), esses objetos
passam a ser construídos a partir do usuário autenticado, sem mudar as regras.
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

    def filtrar(self, queryset: QuerySet, campo: str = "empresa_id") -> QuerySet:
        """Restringe um queryset às empresas do escopo, pelo campo informado."""
        if self.empresas_ids is None:
            return queryset
        return queryset.filter(**{f"{campo}__in": self.empresas_ids})
