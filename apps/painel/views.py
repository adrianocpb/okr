from django.shortcuts import render
from django.utils import timezone

from apps.cadastros import selectors as cadastros
from apps.core.acesso import escopo_da_requisicao
from apps.core.views_apoio import filtros, inteiro, pagina
from apps.okrs.models import Objetivo
from apps.painel import selectors

LIMITE_ALERTAS = 30
TODOS_OS_CICLOS = "todos"


def painel(request):
    escopo = escopo_da_requisicao(request)
    hoje = timezone.localdate()
    valores, filtros_qs = filtros(request, "empresa", "ciclo", "status", "situacao")

    # Padrões: objetivos ativos dos ciclos em andamento hoje.
    status = valores["status"] if "status" in request.GET else Objetivo.Status.ATIVO
    if status not in Objetivo.Status.values:
        status = ""
    # Ciclo: um ciclo escolhido, "todos" (sem recorte de datas) ou, por padrão,
    # os ciclos em andamento hoje (anual, trimestre e bimestre que incluem hoje).
    ciclo_id = inteiro(valores["ciclo"])
    todos_os_ciclos = valores["ciclo"] == TODOS_OS_CICLOS
    periodo_padrao = not ciclo_id and not todos_os_ciclos
    data_de = data_ate = hoje if periodo_padrao else None

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
            "grupos_ciclo": cadastros.opcoes_de_ciclo(escopo, empresa_id=filtro.empresa_id),
            "ciclo_id": ciclo_id,
            "todos_os_ciclos": todos_os_ciclos,
            "status_opcoes": Objetivo.Status.choices,
            "situacoes": selectors.SITUACOES_KR,
            "filtrado": any(valores.values()),
            "filtros_qs": filtros_qs,
        },
    )
