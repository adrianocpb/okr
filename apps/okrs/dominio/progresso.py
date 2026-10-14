"""Cálculo de progresso dos KRs (Especificação Funcional §7).

Tipos de medição:
- NUMÉRICO (crescente/decrescente): (atual − inicial) / (meta − inicial) × 100.
  O valor não é truncado: pode ser negativo (regressão) ou passar de 100% (superação).
- MANUTENÇÃO (manter ≥, ≤ ou entre limites): atendido ou não; sem percentual.
- BINÁRIO: 0% ou 100%.
- MARCOS: marcos concluídos / total × 100 (pesos iguais, Q-10).

Percentuais de KRs diferentes não são comparáveis e nunca são somados ou
agregados (Q-09); cada KR é exibido com seu próprio progresso.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

CEM = Decimal(100)


class TipoMedicao(StrEnum):
    NUMERICO = "numerico"
    MANUTENCAO = "manutencao"
    BINARIO = "binario"
    MARCOS = "marcos"


class Regra(StrEnum):
    CRESCENTE = "crescente"
    DECRESCENTE = "decrescente"
    MANTER_ACIMA = "manter_acima"
    MANTER_ABAIXO = "manter_abaixo"
    MANTER_ENTRE = "manter_entre"


REGRAS_POR_TIPO = {
    TipoMedicao.NUMERICO: {Regra.CRESCENTE, Regra.DECRESCENTE},
    TipoMedicao.MANUTENCAO: {Regra.MANTER_ACIMA, Regra.MANTER_ABAIXO, Regra.MANTER_ENTRE},
    TipoMedicao.BINARIO: set(),
    TipoMedicao.MARCOS: set(),
}


class ErroDeMedicao(ValueError):
    """Configuração de medição inválida (mensagem em português, para o usuário)."""


@dataclass(frozen=True)
class Medicao:
    tipo: TipoMedicao
    regra: Regra | None = None
    valor_inicial: Decimal | None = None
    meta: Decimal | None = None
    limite_inferior: Decimal | None = None
    limite_superior: Decimal | None = None


@dataclass(frozen=True)
class Progresso:
    """Resultado do cálculo para um valor medido.

    `percentual` é o valor real (pode ser < 0 ou > 100) ou None quando o tipo não
    tem percentual (manutenção). `atendido` só se aplica a manutenção.
    `distancia` (manutenção) indica quanto falta para voltar ao limite.
    """

    percentual: Decimal | None
    atendido: bool | None = None
    distancia: Decimal | None = None

    @property
    def percentual_barra(self) -> Decimal | None:
        """Percentual limitado a 0–100, apenas para desenhar a barra."""
        if self.percentual is None:
            return None
        return min(max(self.percentual, Decimal(0)), CEM)


def validar(medicao: Medicao) -> None:
    """Confere se a configuração permite calcular o progresso. Lança ErroDeMedicao."""
    permitidas = REGRAS_POR_TIPO[medicao.tipo]
    if permitidas and medicao.regra not in permitidas:
        raise ErroDeMedicao("Escolha uma regra compatível com o tipo de medição.")
    if not permitidas and medicao.regra is not None:
        raise ErroDeMedicao("Este tipo de medição não usa regra de evolução.")

    if medicao.tipo == TipoMedicao.NUMERICO:
        inicial, meta = medicao.valor_inicial, medicao.meta
        if inicial is None or meta is None:
            raise ErroDeMedicao("Informe o valor inicial e a meta.")
        if meta == inicial:
            raise ErroDeMedicao("A meta deve ser diferente do valor inicial.")
        if medicao.regra == Regra.CRESCENTE and meta < inicial:
            raise ErroDeMedicao(
                "Em métricas crescentes, a meta deve ser maior que o valor inicial."
            )
        if medicao.regra == Regra.DECRESCENTE and meta > inicial:
            raise ErroDeMedicao(
                "Em métricas decrescentes, a meta deve ser menor que o valor inicial."
            )

    if medicao.tipo == TipoMedicao.MANUTENCAO:
        inferior, superior = medicao.limite_inferior, medicao.limite_superior
        if medicao.regra in (Regra.MANTER_ACIMA, Regra.MANTER_ENTRE) and inferior is None:
            raise ErroDeMedicao("Informe o limite mínimo.")
        if medicao.regra in (Regra.MANTER_ABAIXO, Regra.MANTER_ENTRE) and superior is None:
            raise ErroDeMedicao("Informe o limite máximo.")
        if medicao.regra == Regra.MANTER_ENTRE and inferior >= superior:
            raise ErroDeMedicao("O limite mínimo deve ser menor que o limite máximo.")


def progresso_numerico(valor_inicial: Decimal, meta: Decimal, atual: Decimal) -> Progresso:
    if meta == valor_inicial:
        raise ErroDeMedicao("A meta deve ser diferente do valor inicial.")
    percentual = (atual - valor_inicial) / (meta - valor_inicial) * CEM
    return Progresso(percentual=_arredondar(percentual))


def progresso_manutencao(
    regra: Regra,
    atual: Decimal,
    limite_inferior: Decimal | None = None,
    limite_superior: Decimal | None = None,
) -> Progresso:
    distancia = Decimal(0)
    if regra in (Regra.MANTER_ACIMA, Regra.MANTER_ENTRE) and atual < limite_inferior:
        distancia = limite_inferior - atual
    if regra in (Regra.MANTER_ABAIXO, Regra.MANTER_ENTRE) and atual > limite_superior:
        distancia = atual - limite_superior
    return Progresso(percentual=None, atendido=distancia == 0, distancia=distancia)


def progresso_binario(concluido: bool) -> Progresso:
    return Progresso(percentual=CEM if concluido else Decimal(0))


def progresso_marcos(concluidos: int, total: int) -> Progresso:
    if total <= 0:
        raise ErroDeMedicao("Cadastre ao menos um marco para calcular o progresso.")
    if not 0 <= concluidos <= total:
        raise ErroDeMedicao("Quantidade de marcos concluídos inválida.")
    return Progresso(percentual=_arredondar(Decimal(concluidos) / Decimal(total) * CEM))


def calcular(
    medicao: Medicao,
    *,
    valor: Decimal | None = None,
    concluido: bool | None = None,
    marcos_concluidos: int | None = None,
    marcos_total: int | None = None,
) -> Progresso:
    """Calcula o progresso de uma medição a partir do dado informado no check-in."""
    validar(medicao)
    if medicao.tipo == TipoMedicao.NUMERICO:
        _exigir(valor, "Informe o valor medido.")
        return progresso_numerico(medicao.valor_inicial, medicao.meta, valor)
    if medicao.tipo == TipoMedicao.MANUTENCAO:
        _exigir(valor, "Informe o valor medido.")
        return progresso_manutencao(
            medicao.regra, valor, medicao.limite_inferior, medicao.limite_superior
        )
    if medicao.tipo == TipoMedicao.BINARIO:
        _exigir(concluido, "Informe se foi concluído.")
        return progresso_binario(concluido)
    _exigir(marcos_concluidos, "Informe os marcos concluídos.")
    return progresso_marcos(marcos_concluidos, marcos_total or 0)


def _exigir(valor, mensagem: str) -> None:
    if valor is None:
        raise ErroDeMedicao(mensagem)


def _arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
