"""Painel: visão consolidada dos OKRs, com filtros e alertas visuais.

Regras de agregação (Especificação §7.4): percentuais de KRs diferentes nunca são
somados nem tirados em média. Objetivos, empresas e o painel mostram apenas a
distribuição de KRs por situação e a situação mais crítica.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from django.db.models import Q
from django.urls import reverse

from apps.acompanhamento.selectors import detalhar_situacoes, situacoes_em_lote
from apps.core.acesso import EscopoAcesso
from apps.okrs import selectors as okrs
from apps.okrs.models import Iniciativa, Objetivo, ResultadoChave

# Situações de KR, da mais crítica para a menos crítica (Especificação §7.4).
SITUACOES_KR = {
    "em_risco": "Em risco",
    "atencao": "Atenção",
    "sem_checkin": "Sem check-in",
    "no_ritmo": "No ritmo",
    "concluido": "Concluído",
}
ORDEM_CRITICIDADE = list(SITUACOES_KR)

GRAVIDADE_ALTA, GRAVIDADE_MEDIA, GRAVIDADE_BAIXA = 1, 2, 3


@dataclass(frozen=True)
class Filtros:
    empresa_id: int | None = None
    ciclo_id: int | None = None
    data_de: date | None = None
    data_ate: date | None = None
    status_objetivo: str = Objetivo.Status.ATIVO
    situacao_kr: str = ""


@dataclass(frozen=True)
class Alerta:
    gravidade: int
    tipo: str
    texto: str
    rota: str  # nome da URL de detalhe; o link é montado só quando exibido
    pk: int
    empresa: str

    @property
    def url(self) -> str:
        return reverse(self.rota, args=[self.pk])


@dataclass
class Distribuicao:
    contagens: dict[str, int] = field(default_factory=dict)

    def adicionar(self, categoria: str) -> None:
        self.contagens[categoria] = self.contagens.get(categoria, 0) + 1

    @property
    def itens(self) -> list[tuple[str, str, int]]:
        """(código, rótulo, quantidade) na ordem de criticidade, só com quantidade > 0."""
        return [
            (codigo, SITUACOES_KR[codigo], self.contagens[codigo])
            for codigo in ORDEM_CRITICIDADE
            if self.contagens.get(codigo)
        ]

    @property
    def mais_critica(self) -> tuple[str, str] | None:
        itens = self.itens
        return (itens[0][0], itens[0][1]) if itens else None

    @property
    def total(self) -> int:
        return sum(self.contagens.values())


@dataclass
class CartaoObjetivo:
    objetivo: Objetivo
    krs: list[ResultadoChave]
    distribuicao: Distribuicao


@dataclass
class Painel:
    cartoes: list[CartaoObjetivo]
    distribuicao: Distribuicao
    alertas: list[Alerta]
    total_objetivos: int


def categoria_do_kr(kr: ResultadoChave) -> str:
    """Situação do KR para contagem: KR concluído conta como concluído; senão vale o
    status do último check-in; sem check-in, 'sem_checkin'."""
    if kr.status == ResultadoChave.Status.CONCLUIDO:
        return "concluido"
    return kr.situacao.status or "sem_checkin"


def _objetivos_filtrados(escopo: EscopoAcesso, filtros: Filtros):
    objetivos = okrs.listar_objetivos(
        escopo,
        empresa_id=filtros.empresa_id,
        ciclo_id=filtros.ciclo_id,
        status=filtros.status_objetivo,
    )
    if not filtros.ciclo_id:
        # Período por intervalo de datas: ciclos que se sobrepõem ao intervalo (Q-20).
        if filtros.data_ate:
            objetivos = objetivos.filter(ciclo__data_inicio__lte=filtros.data_ate)
        if filtros.data_de:
            objetivos = objetivos.filter(ciclo__data_fim__gte=filtros.data_de)
    return objetivos


def _alertas_de_kr(kr: ResultadoChave) -> list[Alerta]:
    empresa = kr.objetivo.empresa.sigla
    url = ("okrs:kr_detalhe", kr.pk)
    alertas = []
    situacao = kr.situacao
    if kr.status == ResultadoChave.Status.ATIVO:
        if situacao.status == "em_risco":
            alertas.append(Alerta(GRAVIDADE_ALTA, "KR em risco", kr.titulo, *url, empresa))
        elif situacao.status == "atencao":
            alertas.append(Alerta(GRAVIDADE_MEDIA, "KR em atenção", kr.titulo, *url, empresa))
        if situacao.progresso is not None and situacao.progresso.atendido is False:
            alertas.append(Alerta(GRAVIDADE_ALTA, "Fora do limite", kr.titulo, *url, empresa))
        if situacao.atrasado:
            dias = situacao.dias_em_atraso
            texto = f"{kr.titulo} — atrasado há {dias} dia{'s' if dias != 1 else ''}"
            alertas.append(Alerta(GRAVIDADE_MEDIA, "Check-in atrasado", texto, *url, empresa))
    if kr.responsavel.arquivado:
        alertas.append(
            Alerta(GRAVIDADE_BAIXA, "Responsável inativo", f"KR: {kr.titulo}", *url, empresa)
        )
    return alertas


def _alertas_de_objetivo(objetivo: Objetivo, krs: list[ResultadoChave]) -> list[Alerta]:
    empresa = objetivo.empresa.sigla
    url = ("okrs:objetivo_detalhe", objetivo.pk)
    alertas = []
    if objetivo.status == Objetivo.Status.ATIVO and not any(
        kr.status == ResultadoChave.Status.ATIVO for kr in krs
    ):
        alertas.append(Alerta(GRAVIDADE_BAIXA, "Objetivo sem KR", objetivo.titulo, *url, empresa))
    if objetivo.owner.arquivado or objetivo.sponsor.arquivado:
        alertas.append(
            Alerta(
                GRAVIDADE_BAIXA,
                "Responsável inativo",
                f"Objetivo: {objetivo.titulo}",
                *url,
                empresa,
            )
        )
    return alertas


def _alertas_de_iniciativas(objetivo_ids: list[int], hoje: date) -> list[Alerta]:
    iniciativas = (
        Iniciativa.objects.filter(objetivo_id__in=objetivo_ids)
        .exclude(status__in=Iniciativa.STATUS_ENCERRADOS)
        .filter(Q(prazo__lt=hoje) | Q(responsavel__arquivado_em__isnull=False))
        .select_related("objetivo__empresa", "responsavel")
    )
    alertas = []
    for iniciativa in iniciativas:
        url = ("okrs:iniciativa_detalhe", iniciativa.pk)
        empresa = iniciativa.objetivo.empresa.sigla
        if iniciativa.atrasada_em(hoje):
            texto = f"{iniciativa.titulo} — prazo {iniciativa.prazo:%d/%m/%Y}"
            alertas.append(Alerta(GRAVIDADE_MEDIA, "Iniciativa atrasada", texto, *url, empresa))
        if iniciativa.responsavel.arquivado:
            alertas.append(
                Alerta(
                    GRAVIDADE_BAIXA,
                    "Responsável inativo",
                    f"Iniciativa: {iniciativa.titulo}",
                    *url,
                    empresa,
                )
            )
    return alertas


def montar_painel(escopo: EscopoAcesso, filtros: Filtros, hoje: date) -> Painel:
    objetivos = list(_objetivos_filtrados(escopo, filtros))
    objetivos_por_id = {objetivo.pk: objetivo for objetivo in objetivos}
    krs = list(
        ResultadoChave.objects.filter(objetivo__in=list(objetivos_por_id))
        .exclude(status=ResultadoChave.Status.CANCELADO)
        .select_related("responsavel")
        .order_by("id")
    )
    for kr in krs:
        kr.objetivo = objetivos_por_id[kr.objetivo_id]  # reaproveita o objetivo já carregado
    # Sem textos de exibição: são montados depois, só para os objetivos da página.
    situacoes_em_lote(krs, hoje, detalhar=False)
    krs_por_objetivo: dict[int, list[ResultadoChave]] = defaultdict(list)
    for kr in krs:
        krs_por_objetivo[kr.objetivo_id].append(kr)

    cartoes, alertas, geral = [], [], Distribuicao()
    for objetivo in objetivos:
        dos_krs = krs_por_objetivo.get(objetivo.pk, [])
        distribuicao = Distribuicao()
        for kr in dos_krs:
            distribuicao.adicionar(categoria_do_kr(kr))
        if filtros.situacao_kr and not distribuicao.contagens.get(filtros.situacao_kr):
            continue
        for kr in dos_krs:
            geral.adicionar(categoria_do_kr(kr))
            alertas.extend(_alertas_de_kr(kr))
        alertas.extend(_alertas_de_objetivo(objetivo, dos_krs))
        cartoes.append(CartaoObjetivo(objetivo, dos_krs, distribuicao))

    alertas.extend(_alertas_de_iniciativas([c.objetivo.pk for c in cartoes], hoje))
    alertas.sort(key=lambda a: (a.gravidade, a.empresa, a.tipo, a.texto))
    cartoes.sort(key=_ordem_do_cartao)
    return Painel(
        cartoes=cartoes, distribuicao=geral, alertas=alertas, total_objetivos=len(cartoes)
    )


def _ordem_do_cartao(cartao: CartaoObjetivo):
    """Objetivos mais críticos primeiro; depois empresa e título."""
    critica = cartao.distribuicao.mais_critica
    posicao = ORDEM_CRITICIDADE.index(critica[0]) if critica else len(ORDEM_CRITICIDADE)
    objetivo = cartao.objetivo
    return (posicao, objetivo.empresa.sigla, objetivo.chave_titulo)


def detalhar_cartoes(cartoes: list[CartaoObjetivo], hoje: date) -> None:
    """Monta os textos de progresso dos KRs dos cartões exibidos na página."""
    detalhar_situacoes([kr for cartao in cartoes for kr in cartao.krs], hoje)
