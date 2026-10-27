from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_not_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from apps.contas import services
from apps.contas.forms import EntrarForm, TrocarSenhaForm, UsuarioForm
from apps.contas.models import Usuario
from apps.core.formularios import aplicar_erros

# Limitação de tentativas de login: após LIMITE_TENTATIVAS erros seguidos para o
# mesmo e-mail ou o mesmo endereço, novas tentativas ficam bloqueadas por
# BLOQUEIO_SEGUNDOS. O contador fica no cache (uma máquina no protótipo).
LIMITE_TENTATIVAS = 5
BLOQUEIO_SEGUNDOS = 15 * 60


def _ip(request) -> str:
    # Fly.io informa o IP real do visitante neste cabeçalho; localmente, REMOTE_ADDR.
    return request.META.get("HTTP_FLY_CLIENT_IP") or request.META.get("REMOTE_ADDR", "")


def _chaves_tentativas(request, email: str) -> list[str]:
    return [f"login-falhas:email:{email}", f"login-falhas:ip:{_ip(request)}"]


def _bloqueado(chaves: list[str]) -> bool:
    return any(cache.get(chave, 0) >= LIMITE_TENTATIVAS for chave in chaves)


def _registrar_falha(chaves: list[str]) -> None:
    for chave in chaves:
        cache.add(chave, 0, BLOQUEIO_SEGUNDOS)
        try:
            cache.incr(chave)
        except ValueError:
            cache.set(chave, 1, BLOQUEIO_SEGUNDOS)


def _destino_seguro(request) -> str:
    destino = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return destino
    return "/"


@login_not_required
@never_cache
@csrf_protect
def entrar(request):
    if request.user.is_authenticated:
        return redirect(_destino_seguro(request))
    form = EntrarForm(request, data=request.POST or None)
    bloqueio = ""
    if request.method == "POST":
        email = services.normalizar_email(request.POST.get("username", ""))
        chaves = _chaves_tentativas(request, email)
        if _bloqueado(chaves):
            form = EntrarForm(request, initial={"username": email})
            bloqueio = "Muitas tentativas sem sucesso. Aguarde 15 minutos e tente de novo."
        elif form.is_valid():
            for chave in chaves:
                cache.delete(chave)
            login(request, form.get_user())
            return redirect(_destino_seguro(request))
        else:
            _registrar_falha(chaves)
    return render(
        request,
        "contas/entrar.html",
        {"form": form, "bloqueio": bloqueio, "next": _destino_seguro(request)},
    )


@require_POST
def sair(request):
    logout(request)
    messages.info(request, "Você saiu do sistema.")
    return redirect("contas:entrar")


@never_cache
def trocar_senha(request):
    form = TrocarSenhaForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        usuario.deve_trocar_senha = False
        usuario.save(update_fields=["deve_trocar_senha"])
        update_session_auth_hash(request, usuario)
        messages.success(request, "Senha alterada.")
        return redirect("/")
    return render(
        request,
        "contas/trocar_senha.html",
        {"form": form, "obrigatoria": request.user.deve_trocar_senha},
    )


# ---------------------------------------------------------------- administração


def somente_administrador(view):
    """Usuário comum recebe "acesso negado" (403), e não um novo pedido de login."""

    @wraps(view)
    def _view(request, *args, **kwargs):
        if not request.user.administrador:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return _view


@somente_administrador
def usuario_lista(request):
    usuarios = Usuario.objects.order_by("-is_active", "first_name", "last_name", "email")
    return render(request, "contas/usuario_lista.html", {"usuarios": usuarios})


@somente_administrador
@never_cache
def usuario_novo(request):
    form = UsuarioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            usuario, senha = services.criar_usuario(**form.cleaned_data)
        except ValidationError as erro:
            aplicar_erros(form, erro)
        else:
            return _mostrar_senha(request, usuario, senha, nova_conta=True)
    return render(request, "contas/usuario_form.html", {"form": form})


@somente_administrador
@require_POST
@never_cache
def usuario_redefinir_senha(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    return _mostrar_senha(request, usuario, services.redefinir_senha(usuario), nova_conta=False)


@somente_administrador
@require_POST
def usuario_ativo(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    ativo = request.POST.get("ativo") == "1"
    try:
        services.definir_ativo(usuario, ativo, por=request.user)
    except ValidationError as erro:
        messages.error(request, " ".join(erro.messages))
    else:
        situacao = "reativada" if ativo else "desativada"
        messages.success(request, f"Conta de {usuario.nome_exibicao} {situacao}.")
    return redirect("contas:usuario_lista")


def _mostrar_senha(request, usuario, senha, *, nova_conta):
    # A senha temporária aparece só nesta resposta: não é gravada em texto em
    # lugar nenhum e não volta a ser exibida.
    return render(
        request,
        "contas/usuario_senha.html",
        {
            "usuario": usuario,
            "senha": senha,
            "nova_conta": nova_conta,
            "endereco": request.build_absolute_uri("/"),
        },
    )
