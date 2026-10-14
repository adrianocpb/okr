"""Formatação de valores e da regra de medição dos KRs para exibição (pt-BR)."""

from decimal import Decimal

from django.utils import formats

UNIDADES_PREFIXADAS = {"R$", "US$", "€", "£"}


def valor(numero: Decimal | None, casas: int = 0, unidade: str = "") -> str:
    """1234.5, 2, 'R$' → 'R$ 1.234,50'; 12.5, 1, '%' → '12,5%'; 30, 0, 'dias' → '30 dias'."""
    if numero is None:
        return "—"
    texto = formats.number_format(numero, casas, use_l10n=True, force_grouping=True)
    if not unidade:
        return texto
    if unidade in UNIDADES_PREFIXADAS:
        return f"{unidade} {texto}"
    if unidade == "%":
        return f"{texto}%"
    return f"{texto} {unidade}"


def percentual(numero: Decimal | None) -> str:
    if numero is None:
        return "—"
    casas = 0 if numero == numero.to_integral() else 1
    return f"{formats.number_format(numero, casas, use_l10n=True)}%"


def resumo_medicao(kr) -> str:
    """Descrição curta da forma de medir o KR."""
    casas, unidade = kr.casas_decimais, kr.unidade

    def fmt(numero):
        return valor(numero, casas, unidade)

    tipo = kr.TipoMedicao
    if kr.tipo_medicao == tipo.NUMERICO:
        sentido = "crescente" if kr.regra == kr.Regra.CRESCENTE else "decrescente"
        return f"De {fmt(kr.valor_inicial)} para {fmt(kr.meta)} ({sentido})"
    if kr.tipo_medicao == tipo.MANUTENCAO:
        if kr.regra == kr.Regra.MANTER_ACIMA:
            return f"Manter ≥ {fmt(kr.limite_inferior)}"
        if kr.regra == kr.Regra.MANTER_ABAIXO:
            return f"Manter ≤ {fmt(kr.limite_superior)}"
        return f"Manter entre {fmt(kr.limite_inferior)} e {fmt(kr.limite_superior)}"
    if kr.tipo_medicao == tipo.BINARIO:
        return "Concluído ou não concluído (sim/não)"
    total = len(kr.marcos.all())
    return f"{total} marco{'s' if total != 1 else ''} de conclusão"
