from django.contrib.auth.decorators import login_not_required
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render

from apps.core.selectors import situacao_banco


def inicio(request):
    return render(request, "core/inicio.html", {"banco": situacao_banco()})


@login_not_required
def saude(request):
    """Verificação de funcionamento para o servidor (sem login e sem dados)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")
