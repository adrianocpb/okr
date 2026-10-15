from datetime import date

from django.shortcuts import render

from apps.auditoria import selectors
from apps.auditoria.models import RegistroAlteracao
from apps.cadastros import selectors as cadastros
from apps.core.acesso import escopo_da_requisicao
from apps.core.views_apoio import filtros, inteiro, pagina


def _data(valor: str) -> date | None:
    try:
        return date.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def auditoria_lista(request):
    escopo = escopo_da_requisicao(request)
    valores, filtros_qs = filtros(request, "tipo", "empresa", "acao", "de", "ate")
    registros = selectors.listar_auditoria(
        escopo,
        tipo=valores["tipo"],
        empresa_id=inteiro(valores["empresa"]),
        acao=valores["acao"],
        data_de=_data(valores["de"]),
        data_ate=_data(valores["ate"]),
    )
    pagina_atual = pagina(request, registros)
    return render(
        request,
        "auditoria/auditoria_lista.html",
        {
            "pagina": pagina_atual,
            "entradas": selectors.entradas_legiveis(pagina_atual.object_list),
            "filtros": valores,
            "filtrado": any(valores.values()),
            "empresa_id": inteiro(valores["empresa"]),
            "tipos": selectors.ROTULOS_TIPOS,
            "acoes": RegistroAlteracao.Acao.choices,
            "empresas": cadastros.listar_empresas(escopo, situacao="todas"),
            "filtros_qs": filtros_qs,
        },
    )
