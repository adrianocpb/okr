from datetime import date

from django.shortcuts import render
from django.utils import timezone

from apps.cadastros import selectors as cadastros
from apps.core.acesso import escopo_da_requisicao
from apps.core.views_apoio import filtros, inteiro, pagina
from apps.okrs.models import Objetivo
from apps.painel import selectors

LIMITE_ALERTAS = 30


def _data(valor: str) -> date | None:
    try:
        return date.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def painel(request):
    escopo = escopo_da_requisicao(request)
    hoje = timezone.localdate()
    valores, filtros_qs = filtros(request, "empresa", "ciclo", "de", "ate", "status", "situacao")

    # Padrões: objetivos ativos dos ciclos em andamento hoje.
    status = valores["status"] if "status" in request.GET else Objetivo.Status.ATIVO
    if status not in Objetivo.Status.values:
        status = ""
    ciclo_id = inteiro(valores["ciclo"])
    data_de, data_ate = _data(valores["de"]), _data(valores["ate"])
    periodo_padrao = not ciclo_id and not data_de and not data_ate
    if periodo_padrao:
        data_de = data_ate = hoje

    filtro = selectors.Filtros(
        empresa_id=inteiro(valores["empresa"]),
        ciclo_id=ciclo_id,
        data_de=data_de,
        data_ate=data_ate,
        status_objetivo=status,
        situacao_kr=valores["situacao"] if valores["situacao"] in selectors.SITUACOES_KR else "",
    )
    resultado = selectors.montar_painel(escopo, filtro, hoje)
    pagina_atual = pagina(request, resultado.cartoes)
    selectors.detalhar_cartoes(pagina_atual.object_list, hoje)
    return render(
        request,
        "painel/painel.html",
        {
            "painel": resultado,
            "pagina": pagina_atual,
            "alertas": resultado.alertas[:LIMITE_ALERTAS],
            "alertas_ocultos": max(len(resultado.alertas) - LIMITE_ALERTAS, 0),
            "filtro": filtro,
            "periodo_padrao": periodo_padrao,
            "hoje": hoje,
            "empresas": cadastros.listar_empresas(escopo, situacao="todas"),
            "ciclos": cadastros.listar_ciclos(
                escopo, empresa_id=filtro.empresa_id, incluir_arquivados=True
            ),
            "status_opcoes": Objetivo.Status.choices,
            "situacoes": selectors.SITUACOES_KR,
            "filtrado": any(valores.values()),
            "filtros_qs": filtros_qs,
        },
    )
