"""Consultas de check-ins e situação de progresso dos KRs."""

from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone

from apps.acompanhamento.models import CheckIn
from apps.okrs import formatacao
from apps.okrs.dominio import progresso as dominio
from apps.okrs.dominio.cor import cor_do_progresso
from apps.okrs.models import Objetivo, ResultadoChave

Tipo = ResultadoChave.TipoMedicao


@dataclass(frozen=True)
class SituacaoProgresso:
    """O que a tela mostra sobre o progresso de um KR (ou de um check-in)."""

    progresso: dominio.Progresso | None
    cor: str
    texto: str
    status: str = ""  # código do status informado no check-in
    status_rotulo: str = ""
    data_ultimo_checkin: date | None = None
    proximo_checkin: date | None = None
    dias_em_atraso: int = 0

    @property
    def atrasado(self) -> bool:
        return self.dias_em_atraso > 0


def checkin_vigente(kr: ResultadoChave) -> CheckIn | None:
    """Check-in que vale para o KR: o de data de referência mais recente que não foi
    retificado; em empate, o registrado por último."""
    return (
        kr.checkins.filter(retificacao__isnull=True)
        .select_related("autor_informado")
        .order_by("-data_referencia", "-registrado_em", "-id")
        .first()
    )


def checkins_do_kr(kr: ResultadoChave) -> list[CheckIn]:
    """Histórico completo do KR, do mais recente ao mais antigo, com o progresso de
    cada check-in calculado pela medição da época (em `checkin.situacao`)."""
    checkins = list(
        kr.checkins.select_related("autor_informado", "registrado_por", "retifica", "retificacao")
        .prefetch_related("marcos_concluidos")
        .order_by("-data_referencia", "-registrado_em", "-id")
    )
    for checkin in checkins:
        progresso = checkin.progresso(len(checkin.marcos_concluidos.all()))
        checkin.situacao = SituacaoProgresso(
            progresso=progresso,
            cor=cor_do_progresso(progresso),
            texto=texto_do_progresso(
                kr,
                progresso,
                valor=checkin.valor,
                concluido=checkin.concluido,
                marcos=(len(checkin.marcos_concluidos.all()), checkin.total_marcos_vigente),
            ),
        )
    return checkins


def texto_do_progresso(kr, progresso, *, valor=None, concluido=None, marcos=None) -> str:
    def fmt(numero):
        return formatacao.valor(numero, kr.casas_decimais, kr.unidade)

    if kr.tipo_medicao == Tipo.NUMERICO:
        return f"{formatacao.percentual(progresso.percentual)} · {fmt(valor)}"
    if kr.tipo_medicao == Tipo.MANUTENCAO:
        if progresso.atendido:
            return f"Dentro do limite · {fmt(valor)}"
        return f"Fora do limite · {fmt(valor)} ({fmt(progresso.distancia)} além do limite)"
    if kr.tipo_medicao == Tipo.BINARIO:
        return "Concluído" if concluido else "Não concluído"
    feitos, total = marcos
    return f"{feitos} de {total} marcos · {formatacao.percentual(progresso.percentual)}"


def _progresso_atual(kr: ResultadoChave, vigente: CheckIn) -> dominio.Progresso:
    """Último valor medido avaliado com a configuração atual do KR.

    Se a meta mudou depois do último check-in, o progresso atual já reflete a nova
    meta; cada check-in do histórico continua com o cálculo da sua época.
    """
    if kr.tipo_medicao == Tipo.MARCOS:
        marcos_atuais = {m.pk for m in kr.marcos.all()}
        feitos = len(marcos_atuais & {m.pk for m in vigente.marcos_concluidos.all()})
        return dominio.calcular(
            kr.medicao(), marcos_concluidos=feitos, marcos_total=len(marcos_atuais)
        )
    return dominio.calcular(kr.medicao(), valor=vigente.valor, concluido=vigente.concluido)


def proximo_checkin(kr: ResultadoChave, vigente: CheckIn | None) -> date:
    base = vigente.data_referencia if vigente else kr.objetivo.ciclo.data_inicio
    return base + timedelta(days=kr.frequencia_checkin_dias)


def dias_em_atraso(kr: ResultadoChave, vigente: CheckIn | None, hoje: date) -> int:
    """Dias além da frequência de check-in. Só conta para KR e objetivo ativos, com o
    ciclo em andamento."""
    ciclo = kr.objetivo.ciclo
    if (
        kr.status != ResultadoChave.Status.ATIVO
        or kr.objetivo.status != Objetivo.Status.ATIVO
        or not ciclo.data_inicio <= hoje <= ciclo.data_fim
    ):
        return 0
    return max((hoje - proximo_checkin(kr, vigente)).days, 0)


def situacao_do_kr(kr: ResultadoChave, hoje: date | None = None) -> SituacaoProgresso:
    hoje = hoje or timezone.localdate()
    vigente = checkin_vigente(kr)
    atraso = dias_em_atraso(kr, vigente, hoje)
    proxima = proximo_checkin(kr, vigente)
    if vigente is None:
        return SituacaoProgresso(
            progresso=None,
            cor=cor_do_progresso(None),
            texto="Sem check-in",
            proximo_checkin=proxima,
            dias_em_atraso=atraso,
        )
    try:
        progresso = _progresso_atual(kr, vigente)
        marcos_total = len(kr.marcos.all())
    except dominio.ErroDeMedicao:
        progresso = vigente.progresso()
        marcos_total = vigente.total_marcos_vigente
    feitos = (
        len({m.pk for m in vigente.marcos_concluidos.all()} & {m.pk for m in kr.marcos.all()})
        if kr.tipo_medicao == Tipo.MARCOS
        else None
    )
    return SituacaoProgresso(
        progresso=progresso,
        cor=cor_do_progresso(progresso),
        texto=texto_do_progresso(
            kr,
            progresso,
            valor=vigente.valor,
            concluido=vigente.concluido,
            marcos=(feitos, marcos_total),
        ),
        status=vigente.status_informado,
        status_rotulo=vigente.get_status_informado_display(),
        data_ultimo_checkin=vigente.data_referencia,
        proximo_checkin=proxima,
        dias_em_atraso=atraso,
    )


def atualizacoes_da_iniciativa(iniciativa) -> list:
    return list(
        iniciativa.atualizacoes.select_related("autor_informado", "registrado_por").order_by(
            "-data_referencia", "-registrado_em", "-id"
        )
    )
