from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.auditoria.selectors import historico_legivel
from apps.cadastros import selectors, services
from apps.cadastros.forms import CicloAnualForm, CicloEdicaoForm, TrimestreForm
from apps.cadastros.models import Ciclo
from apps.cadastros.views import _alternar_arquivamento, _executar, _filtros, _pagina
from apps.core.acesso import ator_da_requisicao, escopo_da_requisicao
from apps.core.erros import ErroDeNegocio


def _inteiro(valor: str) -> int | None:
    return int(valor) if valor.isdigit() else None


def ciclo_lista(request):
    escopo = escopo_da_requisicao(request)
    filtros, filtros_qs = _filtros(request, "empresa", "ano", "tipo", "situacao", "arquivados")
    situacao = filtros["situacao"] if filtros["situacao"] in selectors.SITUACOES_CICLO else ""
    ciclos = selectors.listar_ciclos(
        escopo,
        empresa_id=_inteiro(filtros["empresa"]),
        ano=_inteiro(filtros["ano"]),
        tipo=filtros["tipo"],
        situacao=situacao,
        incluir_arquivados=filtros["arquivados"] == "1",
    )
    return render(
        request,
        "cadastros/ciclo_lista.html",
        {
            "pagina": _pagina(request, ciclos),
            "filtros": filtros,
            "filtrado": any(filtros.values()),
            "empresa_id": _inteiro(filtros["empresa"]),
            "ano": _inteiro(filtros["ano"]),
            "empresas": selectors.listar_empresas(escopo, situacao="todas"),
            "anos": selectors.anos_com_ciclos(escopo),
            "tipos": Ciclo.Tipo.choices,
            "situacoes": selectors.SITUACOES_CICLO,
            "filtros_qs": filtros_qs,
        },
    )


def ciclo_detalhe(request, pk):
    ciclo = selectors.obter_ciclo(escopo_da_requisicao(request), pk)
    contexto = {"ciclo": ciclo, "historico": historico_legivel(ciclo)}
    if ciclo.tipo == Ciclo.Tipo.ANUAL:
        trimestres = list(selectors.trimestres_do_ciclo(ciclo))
        ativos = {t.trimestre for t in trimestres if not t.arquivado}
        contexto.update(
            trimestres=trimestres,
            faltam_trimestres=len(ativos) < 4,
            pode_gerar=services.anual_regular(ciclo) and len(ativos) < 4,
        )
    return render(request, "cadastros/ciclo_detalhe.html", contexto)


def ciclo_anual_novo(request):
    escopo = escopo_da_requisicao(request)
    inicial = {}
    if _inteiro(request.GET.get("empresa", "")):
        inicial["empresa"] = int(request.GET["empresa"])
    form = CicloAnualForm(request.POST or None, initial=inicial, escopo=escopo)
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        ciclo = _executar(
            form,
            lambda: services.criar_ciclo_anual(
                empresa_id=dados["empresa"].pk,
                ano=dados["ano"],
                data_inicio=dados["data_inicio"],
                data_fim=dados["data_fim"],
                ator=ator_da_requisicao(request),
                escopo=escopo,
            ),
        )
        if ciclo:
            messages.success(request, f"Ciclo anual {ciclo} cadastrado.")
            return redirect("cadastros:ciclo_detalhe", pk=ciclo.pk)
    return render(request, "cadastros/ciclo_anual_form.html", {"form": form})


def ciclo_trimestre_novo(request, pk):
    escopo = escopo_da_requisicao(request)
    anual = selectors.obter_ciclo(escopo, pk)
    if anual.tipo != Ciclo.Tipo.ANUAL:
        raise ErroDeNegocio("Trimestres só podem ser criados em ciclos anuais.")
    inicial = {}
    if request.GET.get("trimestre", "") in {"1", "2", "3", "4"}:
        inicial["trimestre"] = int(request.GET["trimestre"])
    form = TrimestreForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        ciclo = _executar(
            form,
            lambda: services.criar_trimestre(
                ciclo_anual_id=anual.pk,
                trimestre=dados["trimestre"],
                data_inicio=dados["data_inicio"],
                data_fim=dados["data_fim"],
                ator=ator_da_requisicao(request),
                escopo=escopo,
            ),
        )
        if ciclo:
            messages.success(request, f"Ciclo {ciclo} cadastrado.")
            return redirect("cadastros:ciclo_detalhe", pk=ciclo.pk)
    sugestoes = [
        (numero, rotulo, services.periodo_padrao_do_trimestre(anual, numero))
        for numero, rotulo in Ciclo.TRIMESTRES
    ]
    return render(
        request,
        "cadastros/ciclo_trimestre_form.html",
        {"form": form, "anual": anual, "sugestoes": sugestoes},
    )


def ciclo_editar(request, pk):
    escopo = escopo_da_requisicao(request)
    ciclo = selectors.obter_ciclo(escopo, pk)
    inicial = {
        "ano": ciclo.ano,
        "trimestre": ciclo.trimestre,
        "data_inicio": ciclo.data_inicio,
        "data_fim": ciclo.data_fim,
        "versao": ciclo.versao,
    }
    form = CicloEdicaoForm(request.POST or None, initial=inicial, ciclo=ciclo)
    if request.method == "POST" and form.is_valid():
        dados = dict(form.cleaned_data)
        versao = dados.pop("versao") or 0
        atualizado = _executar(
            form,
            lambda: services.atualizar_ciclo(
                pk, dados=dados, versao=versao, ator=ator_da_requisicao(request), escopo=escopo
            ),
        )
        if atualizado:
            messages.success(request, f"Ciclo {atualizado} atualizado.")
            return redirect("cadastros:ciclo_detalhe", pk=pk)
    return render(request, "cadastros/ciclo_editar.html", {"form": form, "ciclo": ciclo})


@require_POST
def ciclo_gerar_trimestres(request, pk):
    try:
        criados = services.gerar_trimestres(
            pk, ator=ator_da_requisicao(request), escopo=escopo_da_requisicao(request)
        )
    except ValidationError as erro:
        messages.error(request, " ".join(erro.messages))
    except ErroDeNegocio as erro:
        messages.error(request, erro.mensagem)
    else:
        rotulos = ", ".join(f"T{c.trimestre}" for c in criados)
        messages.success(request, f"Trimestres criados: {rotulos}.")
    return redirect("cadastros:ciclo_detalhe", pk=pk)


@require_POST
def ciclo_arquivar(request, pk):
    escopo, ator = escopo_da_requisicao(request), ator_da_requisicao(request)
    _alternar_arquivamento(
        request,
        lambda versao: services.arquivar_ciclo(pk, versao=versao, ator=ator, escopo=escopo),
        "Ciclo arquivado. Os registros e o histórico foram preservados.",
    )
    return redirect("cadastros:ciclo_detalhe", pk=pk)


@require_POST
def ciclo_reativar(request, pk):
    escopo, ator = escopo_da_requisicao(request), ator_da_requisicao(request)
    _alternar_arquivamento(
        request,
        lambda versao: services.reativar_ciclo(pk, versao=versao, ator=ator, escopo=escopo),
        "Ciclo reativado.",
    )
    return redirect("cadastros:ciclo_detalhe", pk=pk)
