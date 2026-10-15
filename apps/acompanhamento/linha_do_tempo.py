"""Linha do tempo do objetivo: acompanhamento (check-ins e atualizações de iniciativas)
e alterações estruturais (auditoria) do objetivo, de seus KRs e de suas iniciativas.

Os dois históricos continuam distintos (categoria e aparência diferentes); a linha do
tempo apenas os apresenta em ordem cronológica, com filtro por tipo.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

from django.urls import reverse

from apps.acompanhamento.models import AtualizacaoIniciativa
from apps.acompanhamento.selectors import checkins_do_kr
from apps.auditoria.selectors import Mudanca, entradas_legiveis, registros_de_objetos
from apps.okrs.models import Objetivo

CATEGORIAS = {
    "": "Tudo",
    "checkin": "Check-ins",
    "atualizacao": "Atualizações de iniciativas",
    "alteracao": "Alterações",
}


@dataclass
class ItemLinhaDoTempo:
    momento: datetime
    categoria: str
    titulo: str
    url: str
    autor: str
    autor_verificado: bool
    data_referencia: date | None = None
    rotulo_status: str = ""
    resumo: str = ""
    retificado: bool = False
    retificacao: bool = False
    detalhes: list[tuple[str, str]] = field(default_factory=list)
    mudancas: list[Mudanca] = field(default_factory=list)

    @property
    def acompanhamento(self) -> bool:
        return self.categoria != "alteracao"


def _detalhes(registro) -> list[tuple[str, str]]:
    pares = [
        ("Comentário", registro.comentario),
        ("Dificuldades", registro.dificuldades),
        ("Próximos passos", registro.proximos_passos),
    ]
    return [(rotulo, texto) for rotulo, texto in pares if texto]


def _itens_de_checkins(objetivo: Objetivo) -> list[ItemLinhaDoTempo]:
    itens = []
    for kr in objetivo.krs.prefetch_related("marcos").order_by("id"):
        for checkin in checkins_do_kr(kr):
            detalhes = _detalhes(checkin)
            if checkin.retifica_id:
                detalhes.insert(0, ("Motivo da retificação", checkin.justificativa_retificacao))
            itens.append(
                ItemLinhaDoTempo(
                    momento=checkin.registrado_em,
                    categoria="checkin",
                    titulo=f"Check-in · {kr.titulo}",
                    url=reverse("okrs:kr_detalhe", args=[kr.pk]),
                    autor=checkin.autor_informado.nome,
                    autor_verificado=checkin.autor_verificado,
                    data_referencia=checkin.data_referencia,
                    rotulo_status=checkin.get_status_informado_display(),
                    resumo=checkin.situacao.texto,
                    retificado=checkin.retificado,
                    retificacao=checkin.retifica_id is not None,
                    detalhes=detalhes,
                )
            )
    return itens


def _itens_de_atualizacoes(objetivo: Objetivo) -> list[ItemLinhaDoTempo]:
    atualizacoes = AtualizacaoIniciativa.objects.filter(
        iniciativa__objetivo=objetivo
    ).select_related("iniciativa", "autor_informado")
    return [
        ItemLinhaDoTempo(
            momento=atualizacao.registrado_em,
            categoria="atualizacao",
            titulo=f"Atualização · {atualizacao.iniciativa.titulo}",
            url=reverse("okrs:iniciativa_detalhe", args=[atualizacao.iniciativa_id]),
            autor=atualizacao.autor_informado.nome,
            autor_verificado=atualizacao.autor_verificado,
            data_referencia=atualizacao.data_referencia,
            rotulo_status=atualizacao.get_status_display(),
            detalhes=_detalhes(atualizacao),
        )
        for atualizacao in atualizacoes
    ]


def _itens_de_alteracoes(objetivo: Objetivo) -> list[ItemLinhaDoTempo]:
    objetos = [objetivo, *objetivo.krs.all(), *objetivo.iniciativas.all()]
    return [
        ItemLinhaDoTempo(
            momento=entrada.data_hora,
            categoria="alteracao",
            titulo=f"{entrada.acao} · {entrada.tipo_registro}: {entrada.objeto_descricao}",
            url=entrada.url_objeto,
            autor=entrada.autor,
            autor_verificado=entrada.autor_verificado,
            mudancas=entrada.mudancas,
        )
        for entrada in entradas_legiveis(registros_de_objetos(objetos))
    ]


def linha_do_tempo(objetivo: Objetivo, categoria: str = "") -> list[ItemLinhaDoTempo]:
    """Itens do mais recente ao mais antigo, opcionalmente de uma só categoria."""
    fontes = {
        "checkin": _itens_de_checkins,
        "atualizacao": _itens_de_atualizacoes,
        "alteracao": _itens_de_alteracoes,
    }
    escolhidas = [fontes[categoria]] if categoria in fontes else list(fontes.values())
    itens = [item for fonte in escolhidas for item in fonte(objetivo)]
    return sorted(itens, key=lambda item: item.momento, reverse=True)
