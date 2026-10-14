"""Cor de progresso do KR (Especificação §7.5, decisões Q-12 e Q-22).

A cor migra do vermelho ao verde à medida que o valor se aproxima da meta:
0% (ou menos) vermelho, 50% laranja/amarelo, 90% ou mais (inclusive acima de
100%) verde, com interpolação contínua entre esses pontos. A cor sempre é
exibida junto com o número; nunca é a única informação.
"""

from decimal import Decimal

from apps.okrs.dominio.progresso import Progresso

VERMELHO = (0xD6, 0x45, 0x45)
LARANJA_AMARELO = (0xF0, 0xA2, 0x02)
VERDE = (0x2F, 0x9E, 0x44)
CINZA = "#9aa5b1"

# (percentual, cor): pontos de referência da escala, em ordem crescente.
PONTOS = ((Decimal(0), VERMELHO), (Decimal(50), LARANJA_AMARELO), (Decimal(90), VERDE))


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def cor_do_percentual(percentual: Decimal) -> str:
    if percentual <= PONTOS[0][0]:
        return _hex(PONTOS[0][1])
    if percentual >= PONTOS[-1][0]:
        return _hex(PONTOS[-1][1])
    for (p0, c0), (p1, c1) in zip(PONTOS, PONTOS[1:], strict=False):
        if p0 <= percentual <= p1:
            fator = float((percentual - p0) / (p1 - p0))
            return _hex(tuple(round(a + (b - a) * fator) for a, b in zip(c0, c1, strict=True)))
    raise AssertionError("percentual fora da escala")  # pragma: no cover


def cor_do_progresso(progresso: Progresso | None) -> str:
    """Cor para exibição. Sem dado (sem check-in): cinza."""
    if progresso is None:
        return CINZA
    if progresso.atendido is not None:
        return _hex(VERDE if progresso.atendido else VERMELHO)
    return cor_do_percentual(progresso.percentual)
