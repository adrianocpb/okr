"""Gráfico de evolução de um KR, desenhado em SVG no servidor.

Sem bibliotecas de JavaScript: funciona sem internet e é testável. Cada ponto é um
check-in vigente (retificados ficam de fora, substituídos pela retificação). O eixo
horizontal cobre o período do ciclo; as linhas de referência mostram a linha de base
e a meta (numérico) ou os limites (manutenção) atuais do KR.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from apps.acompanhamento.models import CheckIn
from apps.okrs import formatacao
from apps.okrs.models import ResultadoChave

Tipo = ResultadoChave.TipoMedicao

LARGURA, ALTURA = 640, 240
MARGEM_ESQ, MARGEM_DIR, MARGEM_SUP, MARGEM_INF = 64, 16, 16, 32


@dataclass(frozen=True)
class Ponto:
    data: date
    valor: Decimal
    rotulo: str  # valor formatado para exibição
    status: str


@dataclass(frozen=True)
class Referencia:
    rotulo: str
    valor: Decimal


@dataclass
class Serie:
    kr: ResultadoChave
    pontos: list[Ponto]
    referencias: list[Referencia]
    eixo_percentual: bool
    inicio: date
    fim: date


@dataclass
class Desenho:
    """Coordenadas prontas para o template."""

    largura: int
    altura: int
    linha: str
    pontos: list[tuple[float, float, Ponto]] = field(default_factory=list)
    referencias: list[tuple[float, Referencia]] = field(default_factory=list)
    marcas_y: list[tuple[float, str]] = field(default_factory=list)
    marcas_x: list[tuple[float, str]] = field(default_factory=list)
    hoje_x: float | None = None


def _valor_do_checkin(kr: ResultadoChave, checkin: CheckIn) -> Decimal | None:
    if kr.tipo_medicao in (Tipo.NUMERICO, Tipo.MANUTENCAO):
        return checkin.valor
    return checkin.progresso(len(checkin.marcos_concluidos.all())).percentual


def serie_do_kr(kr: ResultadoChave) -> Serie:
    ciclo = kr.objetivo.ciclo
    checkins = (
        kr.checkins.filter(retificacao__isnull=True)
        .prefetch_related("marcos_concluidos")
        .order_by("data_referencia", "registrado_em", "id")
    )
    eixo_percentual = kr.tipo_medicao in (Tipo.BINARIO, Tipo.MARCOS)
    pontos = []
    for checkin in checkins:
        valor = _valor_do_checkin(kr, checkin)
        if valor is None:
            continue
        rotulo = (
            formatacao.percentual(valor)
            if eixo_percentual
            else formatacao.valor(valor, kr.casas_decimais, kr.unidade)
        )
        pontos.append(
            Ponto(checkin.data_referencia, valor, rotulo, checkin.get_status_informado_display())
        )

    def ref(rotulo, numero):
        texto = formatacao.valor(numero, kr.casas_decimais, kr.unidade)
        return Referencia(f"{rotulo}: {texto}", numero)

    referencias = []
    if kr.tipo_medicao == Tipo.NUMERICO:
        referencias = [ref("Linha de base", kr.valor_inicial), ref("Meta", kr.meta)]
    elif kr.tipo_medicao == Tipo.MANUTENCAO:
        if kr.limite_inferior is not None:
            referencias.append(ref("Mínimo", kr.limite_inferior))
        if kr.limite_superior is not None:
            referencias.append(ref("Máximo", kr.limite_superior))
    else:
        referencias = [Referencia("Conclusão: 100%", Decimal(100))]
    return Serie(kr, pontos, referencias, eixo_percentual, ciclo.data_inicio, ciclo.data_fim)


def desenhar(serie: Serie, hoje: date | None = None) -> Desenho:
    valores = [p.valor for p in serie.pontos] + [r.valor for r in serie.referencias]
    if serie.eixo_percentual:
        valores += [Decimal(0), Decimal(100)]
    minimo, maximo = min(valores), max(valores)
    if minimo == maximo:
        minimo, maximo = minimo - 1, maximo + 1
    folga = (maximo - minimo) * Decimal("0.08")
    minimo, maximo = minimo - folga, maximo + folga

    area_l = LARGURA - MARGEM_ESQ - MARGEM_DIR
    area_a = ALTURA - MARGEM_SUP - MARGEM_INF
    dias = max((serie.fim - serie.inicio).days, 1)

    def x(dia: date) -> float:
        return round(MARGEM_ESQ + area_l * (dia - serie.inicio).days / dias, 1)

    def y(valor: Decimal) -> float:
        return round(MARGEM_SUP + area_a * float((maximo - valor) / (maximo - minimo)), 1)

    pontos = [(x(p.data), y(p.valor), p) for p in serie.pontos]
    desenho = Desenho(
        largura=LARGURA,
        altura=ALTURA,
        linha=" ".join(f"{px},{py}" for px, py, _ in pontos),
        pontos=pontos,
        referencias=[(y(r.valor), r) for r in serie.referencias],
    )
    for i in range(5):
        valor = minimo + (maximo - minimo) * Decimal(i) / Decimal(4)
        rotulo = (
            formatacao.percentual(valor.quantize(Decimal(1)))
            if serie.eixo_percentual
            else formatacao.valor(valor, serie.kr.casas_decimais, "")
        )
        desenho.marcas_y.append((y(valor), rotulo))
    for dia in (serie.inicio, serie.fim):
        desenho.marcas_x.append((x(dia), dia.strftime("%d/%m/%Y")))
    if hoje and serie.inicio <= hoje <= serie.fim:
        desenho.hoje_x = x(hoje)
    return desenho
