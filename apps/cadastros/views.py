from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from apps.auditoria.selectors import historico_legivel
from apps.cadastros import selectors, services
from apps.cadastros.forms import EmpresaForm, PessoaForm
from apps.core.acesso import ator_da_requisicao, escopo_da_requisicao
from apps.core.erros import ErroDeNegocio
from apps.core.formularios import aplicar_erros

ITENS_POR_PAGINA = 25


def _pagina(request, queryset):
    return Paginator(queryset, ITENS_POR_PAGINA).get_page(request.GET.get("pagina"))


def _filtros(request, *nomes):
    valores = {nome: request.GET.get(nome, "").strip() for nome in nomes}
    return valores, urlencode({k: v for k, v in valores.items() if v})


def _executar(form, operacao):
    """Executa a operação do service e leva eventuais erros para o formulário."""
    try:
        return operacao()
    except ValidationError as erro:
        aplicar_erros(form, erro)
    except ErroDeNegocio as erro:
        form.add_error(None, erro.mensagem)
    return None


def _alternar_arquivamento(request, operacao, mensagem_sucesso):
    try:
        versao = int(request.POST.get("versao", ""))
    except ValueError:
        messages.error(request, "Requisição inválida: versão do registro ausente.")
        return
    try:
        operacao(versao)
    except ErroDeNegocio as erro:
        messages.error(request, erro.mensagem)
    else:
        messages.success(request, mensagem_sucesso)


# ---------------------------------------------------------------- empresas


def empresa_lista(request):
    escopo = escopo_da_requisicao(request)
    filtros, filtros_qs = _filtros(request, "busca", "situacao")
    situacao = filtros["situacao"] if filtros["situacao"] in selectors.SITUACOES else "ativas"
    empresas = selectors.listar_empresas(escopo, situacao=situacao, busca=filtros["busca"])
    return render(
        request,
        "cadastros/empresa_lista.html",
        {
            "pagina": _pagina(request, empresas),
            "busca": filtros["busca"],
            "situacao": situacao,
            "situacoes": selectors.SITUACOES,
            "filtros_qs": filtros_qs,
        },
    )


def empresa_detalhe(request, pk):
    escopo = escopo_da_requisicao(request)
    empresa = selectors.obter_empresa(escopo, pk)
    return render(
        request,
        "cadastros/empresa_detalhe.html",
        {
            "empresa": empresa,
            "pessoas": selectors.pessoas_da_empresa(escopo, empresa),
            "historico": historico_legivel(empresa),
        },
    )


def empresa_nova(request):
    form = EmpresaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        empresa = _executar(
            form,
            lambda: services.criar_empresa(
                nome=form.cleaned_data["nome"],
                sigla=form.cleaned_data["sigla"],
                ator=ator_da_requisicao(request),
                escopo=escopo_da_requisicao(request),
            ),
        )
        if empresa:
            messages.success(request, f"Empresa {empresa.sigla} cadastrada.")
            return redirect("cadastros:empresa_detalhe", pk=empresa.pk)
    return render(request, "cadastros/empresa_form.html", {"form": form, "empresa": None})


def empresa_editar(request, pk):
    escopo = escopo_da_requisicao(request)
    empresa = selectors.obter_empresa(escopo, pk)
    inicial = {"nome": empresa.nome, "sigla": empresa.sigla, "versao": empresa.versao}
    form = EmpresaForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        atualizada = _executar(
            form,
            lambda: services.atualizar_empresa(
                pk,
                nome=form.cleaned_data["nome"],
                sigla=form.cleaned_data["sigla"],
                versao=form.cleaned_data["versao"] or 0,
                ator=ator_da_requisicao(request),
                escopo=escopo,
            ),
        )
        if atualizada:
            messages.success(request, f"Empresa {atualizada.sigla} atualizada.")
            return redirect("cadastros:empresa_detalhe", pk=pk)
    return render(request, "cadastros/empresa_form.html", {"form": form, "empresa": empresa})


@require_POST
def empresa_arquivar(request, pk):
    escopo, ator = escopo_da_requisicao(request), ator_da_requisicao(request)
    _alternar_arquivamento(
        request,
        lambda versao: services.arquivar_empresa(pk, versao=versao, ator=ator, escopo=escopo),
        "Empresa arquivada. Os registros e o histórico foram preservados.",
    )
    return redirect("cadastros:empresa_detalhe", pk=pk)


@require_POST
def empresa_reativar(request, pk):
    escopo, ator = escopo_da_requisicao(request), ator_da_requisicao(request)
    _alternar_arquivamento(
        request,
        lambda versao: services.reativar_empresa(pk, versao=versao, ator=ator, escopo=escopo),
        "Empresa reativada.",
    )
    return redirect("cadastros:empresa_detalhe", pk=pk)


# ----------------------------------------------------------------- pessoas


def pessoa_lista(request):
    escopo = escopo_da_requisicao(request)
    filtros, filtros_qs = _filtros(request, "busca", "situacao", "empresa")
    situacao = filtros["situacao"] if filtros["situacao"] in selectors.SITUACOES else "ativas"
    empresa_id = int(filtros["empresa"]) if filtros["empresa"].isdigit() else None
    pessoas = selectors.listar_pessoas(
        escopo, situacao=situacao, busca=filtros["busca"], empresa_id=empresa_id
    )
    return render(
        request,
        "cadastros/pessoa_lista.html",
        {
            "pagina": _pagina(request, pessoas),
            "busca": filtros["busca"],
            "situacao": situacao,
            "situacoes": selectors.SITUACOES,
            "empresa_id": empresa_id,
            "empresas": selectors.listar_empresas(escopo, situacao="todas"),
            "filtros_qs": filtros_qs,
        },
    )


def pessoa_detalhe(request, pk):
    pessoa = selectors.obter_pessoa(escopo_da_requisicao(request), pk)
    return render(
        request,
        "cadastros/pessoa_detalhe.html",
        {"pessoa": pessoa, "historico": historico_legivel(pessoa)},
    )


def pessoa_nova(request):
    escopo = escopo_da_requisicao(request)
    inicial = {}
    if request.GET.get("empresa", "").isdigit():
        inicial["empresas"] = [int(request.GET["empresa"])]
    form = PessoaForm(request.POST or None, initial=inicial, escopo=escopo)
    if request.method == "POST" and form.is_valid():
        pessoa = _executar(
            form,
            lambda: services.criar_pessoa(
                nome=form.cleaned_data["nome"],
                email=form.cleaned_data["email"] or None,
                empresas_ids=[e.pk for e in form.cleaned_data["empresas"]],
                ator=ator_da_requisicao(request),
                escopo=escopo,
            ),
        )
        if pessoa:
            messages.success(request, f"Pessoa {pessoa.nome} cadastrada.")
            return redirect("cadastros:pessoa_detalhe", pk=pessoa.pk)
    return render(request, "cadastros/pessoa_form.html", {"form": form, "pessoa": None})


def pessoa_editar(request, pk):
    escopo = escopo_da_requisicao(request)
    pessoa = selectors.obter_pessoa(escopo, pk)
    inicial = {
        "nome": pessoa.nome,
        "email": pessoa.email or "",
        "empresas": [e.pk for e in pessoa.empresas_visiveis],
        "versao": pessoa.versao,
    }
    form = PessoaForm(request.POST or None, initial=inicial, escopo=escopo, pessoa=pessoa)
    if request.method == "POST" and form.is_valid():
        atualizada = _executar(
            form,
            lambda: services.atualizar_pessoa(
                pk,
                nome=form.cleaned_data["nome"],
                email=form.cleaned_data["email"] or None,
                empresas_ids=[e.pk for e in form.cleaned_data["empresas"]],
                versao=form.cleaned_data["versao"] or 0,
                ator=ator_da_requisicao(request),
                escopo=escopo,
            ),
        )
        if atualizada:
            messages.success(request, f"Pessoa {atualizada.nome} atualizada.")
            return redirect("cadastros:pessoa_detalhe", pk=pk)
    return render(request, "cadastros/pessoa_form.html", {"form": form, "pessoa": pessoa})


@require_POST
def pessoa_arquivar(request, pk):
    escopo, ator = escopo_da_requisicao(request), ator_da_requisicao(request)
    _alternar_arquivamento(
        request,
        lambda versao: services.arquivar_pessoa(pk, versao=versao, ator=ator, escopo=escopo),
        "Pessoa arquivada. Os registros e o histórico foram preservados.",
    )
    return redirect("cadastros:pessoa_detalhe", pk=pk)


@require_POST
def pessoa_reativar(request, pk):
    escopo, ator = escopo_da_requisicao(request), ator_da_requisicao(request)
    _alternar_arquivamento(
        request,
        lambda versao: services.reativar_pessoa(pk, versao=versao, ator=ator, escopo=escopo),
        "Pessoa reativada.",
    )
    return redirect("cadastros:pessoa_detalhe", pk=pk)
