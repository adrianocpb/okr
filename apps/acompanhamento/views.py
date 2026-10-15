from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.acompanhamento import services
from apps.acompanhamento.forms import AtualizacaoIniciativaForm, CheckInForm
from apps.acompanhamento.models import CheckIn
from apps.core.acesso import ator_da_requisicao, escopo_da_requisicao
from apps.core.erros import AcessoNegado
from apps.core.views_apoio import executar
from apps.okrs import selectors as okrs


def checkin_novo(request, kr_pk):
    escopo = escopo_da_requisicao(request)
    kr = okrs.obter_kr(escopo, kr_pk)
    hoje = timezone.localdate()
    form = CheckInForm(request.POST or None, kr=kr, hoje=hoje)
    if request.method == "POST" and form.is_valid():
        checkin = executar(
            form,
            lambda: services.registrar_checkin(
                kr_id=kr.pk,
                dados=form.dados(),
                ator=ator_da_requisicao(request),
                escopo=escopo,
                hoje=hoje,
            ),
        )
        if checkin:
            messages.success(request, "Check-in registrado.")
            return redirect("okrs:kr_detalhe", pk=kr.pk)
    return render(
        request,
        "acompanhamento/checkin_form.html",
        {"form": form, "kr": kr, "original": None, "hoje": hoje},
    )


def checkin_retificar(request, pk):
    escopo = escopo_da_requisicao(request)
    original = CheckIn.objects.select_related("autor_informado").filter(pk=pk).first()
    if original is None:
        raise AcessoNegado()
    kr = okrs.obter_kr(escopo, original.kr_id)
    hoje = timezone.localdate()
    form = CheckInForm(request.POST or None, kr=kr, hoje=hoje, original=original)
    if request.method == "POST" and form.is_valid():
        checkin = executar(
            form,
            lambda: services.retificar_checkin(
                original.pk,
                dados=form.dados(),
                ator=ator_da_requisicao(request),
                escopo=escopo,
                hoje=hoje,
            ),
        )
        if checkin:
            messages.success(request, "Retificação registrada. O check-in original foi preservado.")
            return redirect("okrs:kr_detalhe", pk=kr.pk)
    return render(
        request,
        "acompanhamento/checkin_form.html",
        {"form": form, "kr": kr, "original": original, "hoje": hoje},
    )


def atualizacao_nova(request, iniciativa_pk):
    escopo = escopo_da_requisicao(request)
    iniciativa = okrs.obter_iniciativa(escopo, iniciativa_pk)
    hoje = timezone.localdate()
    form = AtualizacaoIniciativaForm(request.POST or None, iniciativa=iniciativa, hoje=hoje)
    if request.method == "POST" and form.is_valid():
        atualizacao = executar(
            form,
            lambda: services.registrar_atualizacao(
                iniciativa_id=iniciativa.pk,
                dados=form.cleaned_data,
                ator=ator_da_requisicao(request),
                escopo=escopo,
                hoje=hoje,
            ),
        )
        if atualizacao:
            messages.success(request, "Atualização registrada.")
            return redirect("okrs:iniciativa_detalhe", pk=iniciativa.pk)
    return render(
        request,
        "acompanhamento/atualizacao_form.html",
        {"form": form, "iniciativa": iniciativa},
    )
