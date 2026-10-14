from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.auditoria.selectors import historico_legivel
from apps.cadastros import selectors as cadastros
from apps.core.acesso import ator_da_requisicao, escopo_da_requisicao
from apps.core.erros import ErroDeNegocio
from apps.core.views_apoio import executar as _executar
from apps.core.views_apoio import filtros as _filtros
from apps.core.views_apoio import pagina as _pagina
from apps.okrs import selectors, services
from apps.okrs.forms import KRForm, MarcoForm, ObjetivoForm, VinculoForm


def _inteiro(valor: str) -> int | None:
    return int(valor) if valor.isdigit() else None


def objetivo_lista(request):
    escopo = escopo_da_requisicao(request)
    filtros, filtros_qs = _filtros(request, "empresa", "ciclo", "status", "busca")
    empresa_id = _inteiro(filtros["empresa"])
    objetivos = selectors.listar_objetivos(
        escopo,
        empresa_id=empresa_id,
        ciclo_id=_inteiro(filtros["ciclo"]),
        status=filtros["status"],
        busca=filtros["busca"],
    )
    return render(
        request,
        "okrs/objetivo_lista.html",
        {
            "pagina": _pagina(request, objetivos),
            "filtros": filtros,
            "filtrado": any(filtros.values()),
            "empresa_id": empresa_id,
            "ciclo_id": _inteiro(filtros["ciclo"]),
            "empresas": cadastros.listar_empresas(escopo, situacao="todas"),
            "ciclos": cadastros.listar_ciclos(
                escopo, empresa_id=empresa_id, incluir_arquivados=True
            ),
            "status_opcoes": selectors.STATUS_FILTRO,
            "filtros_qs": filtros_qs,
        },
    )


def objetivo_detalhe(request, pk):
    objetivo = selectors.obter_objetivo(escopo_da_requisicao(request), pk)
    return render(
        request,
        "okrs/objetivo_detalhe.html",
        {
            "objetivo": objetivo,
            "vinculos": selectors.vinculos_do_objetivo(objetivo),
            "form_vinculo": VinculoForm(objetivo=objetivo),
            "krs": selectors.krs_do_objetivo(objetivo),
            "historico": historico_legivel(objetivo),
        },
    )


def objetivo_novo(request):
    escopo = escopo_da_requisicao(request)
    empresa_id = _inteiro(request.GET.get("empresa", ""))
    if empresa_id is None:
        # Primeiro passo: escolher a empresa (ciclos e pessoas dependem dela).
        return render(
            request,
            "okrs/objetivo_escolher_empresa.html",
            {"empresas": cadastros.empresas_para_vinculo(escopo).order_by("sigla")},
        )
    empresa = cadastros.obter_empresa(escopo, empresa_id)
    inicial = {}
    if _inteiro(request.GET.get("ciclo", "")):
        inicial["ciclo"] = int(request.GET["ciclo"])
    form = ObjetivoForm(request.POST or None, initial=inicial, empresa=empresa)
    if request.method == "POST" and form.is_valid():
        objetivo = _executar(
            form,
            lambda: services.criar_objetivo(
                empresa_id=empresa.pk,
                dados=form.dados(),
                ator=ator_da_requisicao(request),
                escopo=escopo,
            ),
        )
        if objetivo:
            messages.success(request, "Objetivo cadastrado.")
            return redirect("okrs:objetivo_detalhe", pk=objetivo.pk)
    return render(
        request, "okrs/objetivo_form.html", {"form": form, "empresa": empresa, "objetivo": None}
    )


def objetivo_editar(request, pk):
    escopo = escopo_da_requisicao(request)
    objetivo = selectors.obter_objetivo(escopo, pk)
    inicial = {
        "titulo": objetivo.titulo,
        "descricao": objetivo.descricao,
        "ciclo": objetivo.ciclo_id,
        "owner": objetivo.owner_id,
        "sponsor": objetivo.sponsor_id,
        "status": objetivo.status,
        "comentario_status": objetivo.comentario_status,
        "versao": objetivo.versao,
    }
    form = ObjetivoForm(
        request.POST or None, initial=inicial, empresa=objetivo.empresa, objetivo=objetivo
    )
    if request.method == "POST" and form.is_valid():
        atualizado = _executar(
            form,
            lambda: services.atualizar_objetivo(
                pk,
                dados=form.dados(),
                versao=form.cleaned_data["versao"] or 0,
                ator=ator_da_requisicao(request),
                escopo=escopo,
            ),
        )
        if atualizado:
            messages.success(request, "Objetivo atualizado.")
            return redirect("okrs:objetivo_detalhe", pk=pk)
    return render(
        request,
        "okrs/objetivo_form.html",
        {"form": form, "empresa": objetivo.empresa, "objetivo": objetivo},
    )


@require_POST
def objetivo_vincular(request, pk):
    escopo = escopo_da_requisicao(request)
    objetivo = selectors.obter_objetivo(escopo, pk)
    form = VinculoForm(request.POST, objetivo=objetivo)
    if not form.is_valid():
        messages.error(request, "Selecione um objetivo anual disponível.")
        return redirect("okrs:objetivo_detalhe", pk=pk)
    try:
        services.vincular(
            objetivo_trimestral_id=objetivo.pk,
            objetivo_anual_id=form.cleaned_data["objetivo_anual"].pk,
            ator=ator_da_requisicao(request),
            escopo=escopo,
        )
    except ValidationError as erro:
        messages.error(request, " ".join(erro.messages))
    except ErroDeNegocio as erro:
        messages.error(request, erro.mensagem)
    else:
        messages.success(request, "Objetivo vinculado ao objetivo anual.")
    return redirect("okrs:objetivo_detalhe", pk=pk)


@require_POST
def objetivo_desvincular(request, pk, vinculo_pk):
    try:
        services.desvincular(
            vinculo_pk, ator=ator_da_requisicao(request), escopo=escopo_da_requisicao(request)
        )
    except ErroDeNegocio as erro:
        messages.error(request, erro.mensagem)
    else:
        messages.success(request, "Vínculo removido. O registro permanece no histórico.")
    return redirect("okrs:objetivo_detalhe", pk=pk)


# --------------------------------------------------------------------- KRs


def kr_novo(request, objetivo_pk):
    escopo = escopo_da_requisicao(request)
    objetivo = selectors.obter_objetivo(escopo, objetivo_pk)
    if objetivo.encerrado:
        raise ErroDeNegocio("Objetivo concluído ou cancelado não recebe novos KRs.")
    form = KRForm(request.POST or None, objetivo=objetivo)
    if request.method == "POST" and form.is_valid():
        kr = _executar(
            form,
            lambda: services.criar_kr(
                objetivo_id=objetivo.pk,
                dados=form.dados(),
                ator=ator_da_requisicao(request),
                escopo=escopo,
            ),
        )
        if kr:
            messages.success(request, "KR cadastrado.")
            return redirect("okrs:kr_detalhe", pk=kr.pk)
    return render(
        request,
        "okrs/kr_form.html",
        {"form": form, "objetivo": objetivo, "kr": None},
    )


def kr_detalhe(request, pk):
    kr = selectors.obter_kr(escopo_da_requisicao(request), pk)
    return render(
        request,
        "okrs/kr_detalhe.html",
        {
            "kr": kr,
            "objetivo": kr.objetivo,
            "situacao": selectors.situacao_do_kr(kr),
            "marcos": kr.marcos.all(),
            "form_marco": MarcoForm(),
            "historico": historico_legivel(kr),
        },
    )


def kr_editar(request, pk):
    escopo = escopo_da_requisicao(request)
    kr = selectors.obter_kr(escopo, pk)
    form = KRForm(request.POST or None, objetivo=kr.objetivo, kr=kr)
    if request.method == "POST" and form.is_valid():
        atualizado = _executar(
            form,
            lambda: services.atualizar_kr(
                pk,
                dados=form.dados(),
                versao=form.cleaned_data["versao"] or 0,
                ator=ator_da_requisicao(request),
                escopo=escopo,
            ),
        )
        if atualizado:
            messages.success(request, "KR atualizado.")
            return redirect("okrs:kr_detalhe", pk=pk)
    return render(
        request,
        "okrs/kr_form.html",
        {"form": form, "objetivo": kr.objetivo, "kr": kr},
    )


@require_POST
def marco_adicionar(request, pk):
    form = MarcoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Informe a descrição do marco.")
        return redirect("okrs:kr_detalhe", pk=pk)
    try:
        services.adicionar_marco(
            pk,
            descricao=form.cleaned_data["descricao"],
            prazo=form.cleaned_data["prazo"],
            ator=ator_da_requisicao(request),
            escopo=escopo_da_requisicao(request),
        )
    except ValidationError as erro:
        messages.error(request, " ".join(erro.messages))
    except ErroDeNegocio as erro:
        messages.error(request, erro.mensagem)
    else:
        messages.success(request, "Marco adicionado.")
    return redirect("okrs:kr_detalhe", pk=pk)


@require_POST
def marco_remover(request, pk, marco_pk):
    try:
        services.remover_marco(
            marco_pk, ator=ator_da_requisicao(request), escopo=escopo_da_requisicao(request)
        )
    except ErroDeNegocio as erro:
        messages.error(request, erro.mensagem)
    else:
        messages.success(request, "Marco removido. O registro permanece no histórico do KR.")
    return redirect("okrs:kr_detalhe", pk=pk)
