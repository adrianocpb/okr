from django.shortcuts import redirect
from django.urls import reverse


class TrocaDeSenhaObrigatoriaMiddleware:
    """Quem entrou com senha temporária só acessa a troca de senha (e o sair)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario is not None and usuario.is_authenticated and usuario.deve_trocar_senha:
            liberadas = {reverse("contas:trocar_senha"), reverse("contas:sair")}
            if request.path not in liberadas and not request.path.startswith("/static/"):
                return redirect("contas:trocar_senha")
        return self.get_response(request)
