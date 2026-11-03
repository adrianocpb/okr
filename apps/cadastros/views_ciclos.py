from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Prefetch, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.auditoria.selectors import historico_legivel
from apps.cadastros import selectors, services
from apps.cadastros.forms import CicloAnualForm, CicloEdicaoForm, TrimestreForm
from apps.cadastros.models import Ciclo
from apps.core.acesso import ator_da_requisicao, escopo_da_requisicao
from apps.core.erros import ErroDeNegocio
from apps.core.views_apoio import alternar_arquivamento as _alternar_arquivamento
from apps.core.views_apoio import executar as _executar
from apps.core.views_apoio import filtros as _filtros
from apps.core.views_apoio import pagina as _pagina
from apps.okrs import selectors as okrs_selectors


def _inteiro(valor: str) -> int | None:
    return int(valor) if valor.isdigit() else None


def ciclo_lista(request):
    """Ciclos anuais, cada um com seus trimestres e bimestres logo abaixo."""
    escopo = escopo_da_requisicao(request)
    filtros, filtros_qs = _filtros(request, "empresa", "ano", "situacao", "arquivados")
    situacao = filtros["situacao"] if filtros["situacao"] in selectors.SITUACOES_CICLO else ""
    arquivados = filtros["arquivados"] == "1"
    subciclos = _com_contagem(Ciclo.objects.all()).order_by("data_inicio", "tipo")
    if not arquivados:
        subciclos = subciclos.filter(arquivado_em__isnull=True)
    anuais = (
        _com_contagem(
            selectors.listar_ciclos(
                escopo,
                empresa_id=_inteiro(filtros["empresa"]),
                ano=_inteiro(filtros["ano"]),
                tipo=Ciclo.Tipo.ANUAL,
                situacao=situacao,
                incluir_arquivados=arquivados,
            )
        )
        .select_related("empresa")
        .prefetch_related(Prefetch("subciclos", queryset=subciclos, to_attr="subciclos_lista"))
    )
    pagina_atual = _pagina(request, anuais)
    for anual in pagina_atual.object_list:
        anual.trimestres_lista = [
            c for c in anual.subciclos_lista if c.tipo == Ciclo.Tipo.TRIMESTRAL
        ]
        anual.bimestres_lista = [c for c in anual.subciclos_lista if c.tipo == Ciclo.Tipo.BIMESTRAL]
    return render(
        request,
        "cadastros/ciclo_lista.html",
        {
            "pagina": pagina_atual,
            "filtros": filtros,
            "filtrado": any(filtros.values()),
            "empresa_id": _inteiro(filtros["empresa"]),
            "ano": _inteiro(filtros["ano"]),
            "empresas": selectors.listar_empresas(escopo, situacao="todas"),
            "anos": selectors.anos_com_ciclos(escopo),
            "situacoes": selectors.SITUACOES_CICLO,
            "filtros_qs": filtros_qs,
        },
    )


ABAS_SUBCICLO = {"tri": Ciclo.Tipo.TRIMESTRAL, "bi": Ciclo.Tipo.BIMESTRAL}


def _com_contagem(subciclos):
    return subciclos.annotate(
        total_objetivos=Count("objetivos", filter=~Q(objetivos__status="cancelado"))
    )


def ciclo_detalhe(request, pk):
    escopo = escopo_da_requisicao(request)
    ciclo = selectors.obter_ciclo(escopo, pk)
    objetivos = list(okrs_selectors.listar_objetivos(escopo, ciclo_id=ciclo.pk))
    okrs_selectors.detalhar_objetivos(objetivos)
    contexto = {"ciclo": ciclo, "objetivos": objetivos, "historico": historico_legivel(ciclo)}
    if ciclo.tipo == Ciclo.Tipo.ANUAL:
        okrs_selectors.marcar_desdobramento(objetivos)
        trimestres = list(_com_contagem(selectors.subciclos_do_ciclo(ciclo, Ciclo.Tipo.TRIMESTRAL)))
        bimestres = list(_com_contagem(selectors.subciclos_do_ciclo(ciclo, Ciclo.Tipo.BIMESTRAL)))
        aba = request.GET.get("sub", "")
        if aba not in ABAS_SUBCICLO:
            aba = "bi" if bimestres and not trimestres else "tri"
        regular = services.anual_regular(ciclo)
        ativos_tri = {t.trimestre for t in trimestres if not t.arquivado}
        ativos_bi = {b.bimestre for b in bimestres if not b.arquivado}
        contexto.update(
            trimestres=trimestres,
            bimestres=bimestres,
            aba=aba,
            subciclos_aba=trimestres if aba == "tri" else bimestres,
            faltam_trimestres=len(ativos_tri) < 4,
            faltam_bimestres=len(ativos_bi) < 6,
            pode_gerar=regular and len(ativos_tri) < 4,
            pode_gerar_bimestres=regular and len(ativos_bi) < 6,
        )
    else:
        okrs_selectors.marcar_contribuicoes(objetivos)
        anual = ciclo.ciclo_anual
        irmaos = list(
            selectors.subciclos_do_ciclo(anual, ciclo.tipo).filter(arquivado_em__isnull=True)
        )
        posicao = next((i for i, c in enumerate(irmaos) if c.pk == ciclo.pk), None)
        outro_tipo = (
            Ciclo.Tipo.BIMESTRAL if ciclo.tipo == Ciclo.Tipo.TRIMESTRAL else Ciclo.Tipo.TRIMESTRAL
        )
        mesmo_periodo = selectors.subciclos_do_ciclo(anual, outro_tipo).filter(
            arquivado_em__isnull=True,
            data_inicio__lte=ciclo.data_fim,
            data_fim__gte=ciclo.data_inicio,
        )
        desdobrados = {
            anual_obj.pk for objetivo in objetivos for anual_obj in objetivo.contribui_lista
        }
        sem_desdobramento = [
            objetivo
            for objetivo in okrs_selectors.listar_objetivos(escopo, ciclo_id=anual.pk)
            if objetivo.pk not in desdobrados and objetivo.status != "cancelado"
        ]
        contexto.update(
            irmaos=irmaos,
            anterior=irmaos[posicao - 1] if posicao else None,
            proximo=irmaos[posicao + 1]
            if posicao is not None and posicao + 1 < len(irmaos)
            else None,
            mesmo_periodo=list(mesmo_periodo),
            sem_desdobramento=sem_desdobramento,
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
                dividir_trimestres=dados["dividir_trimestres"],
                dividir_bimestres=dados["dividir_bimestres"],
                ator=ator_da_requisicao(request),
                escopo=escopo,
            ),
        )
        if ciclo:
            divisoes = [
                nome
                for marcado, nome in (
                    (dados["dividir_trimestres"], "trimestres"),
                    (dados["dividir_bimestres"], "bimestres"),
                )
                if marcado
            ]
            extra = f", com {' e '.join(divisoes)}" if divisoes else ""
            messages.success(request, f"Ciclo anual {ciclo} cadastrado{extra}.")
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
        "bimestre": ciclo.bimestre,
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
def ciclo_gerar_bimestres(request, pk):
    try:
        criados = services.gerar_subciclos(
            pk,
            tipo=Ciclo.Tipo.BIMESTRAL,
            ator=ator_da_requisicao(request),
            escopo=escopo_da_requisicao(request),
        )
    except ValidationError as erro:
        messages.error(request, " ".join(erro.messages))
    except ErroDeNegocio as erro:
        messages.error(request, erro.mensagem)
    else:
        rotulos = ", ".join(c.sigla_subciclo for c in criados)
        messages.success(request, f"Bimestres criados: {rotulos}.")
    return redirect(f"{reverse('cadastros:ciclo_detalhe', args=[pk])}?sub=bi")


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
