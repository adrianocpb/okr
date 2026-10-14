from django.shortcuts import render

from apps.core.selectors import situacao_banco


def inicio(request):
    return render(request, "core/inicio.html", {"banco": situacao_banco()})
