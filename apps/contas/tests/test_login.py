import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from apps.auditoria.models import RegistroAlteracao
from apps.cadastros.models import Empresa
from apps.contas import services
from apps.contas.models import Usuario
from apps.contas.views import LIMITE_TENTATIVAS

pytestmark = pytest.mark.django_db

ROTAS_PUBLICAS = {"contas:entrar", "core:saude"}


@pytest.fixture(autouse=True)
def limpar_cache():
    cache.clear()
    yield
    cache.clear()


def _rotas(resolver=None, prefixo=""):
    """Todas as rotas nomeadas, com argumentos fictícios para as que pedem."""
    resolver = resolver or get_resolver()
    for item in resolver.url_patterns:
        if isinstance(item, URLResolver):
            namespace = f"{item.namespace}:" if item.namespace else ""
            yield from _rotas(item, prefixo + namespace)
        elif isinstance(item, URLPattern) and item.name:
            argumentos = {nome: 1 for nome in item.pattern.regex.groupindex}
            yield prefixo + item.name, argumentos


def test_todas_as_rotas_de_dados_exigem_login(cliente_anonimo):
    rotas = [(nome, args) for nome, args in _rotas() if nome not in ROTAS_PUBLICAS]
    assert len(rotas) > 30

    for nome, argumentos in rotas:
        url = reverse(nome, kwargs=argumentos)
        resposta = cliente_anonimo.get(url)
        assert resposta.status_code == 302, nome
        assert resposta.url.startswith(reverse("contas:entrar")), nome


def test_verificacao_de_saude_nao_exige_login(cliente_anonimo):
    resposta = cliente_anonimo.get(reverse("core:saude"))

    assert resposta.status_code == 200
    assert resposta.content == b"ok"


def test_entrar_com_email_e_senha(cliente_anonimo):
    usuario, senha = services.criar_usuario(nome="Ana Souza", email="Ana@Exemplo.com")
    usuario.deve_trocar_senha = False
    usuario.save()

    resposta = cliente_anonimo.post(
        reverse("contas:entrar"), {"username": " ana@exemplo.COM ", "password": senha}
    )

    assert resposta.status_code == 302
    assert resposta.url == "/"
    assert cliente_anonimo.get("/").status_code == 200


def test_senha_errada_mostra_mensagem(cliente_anonimo):
    services.criar_usuario(nome="Ana", email="ana@exemplo.com")

    resposta = cliente_anonimo.post(
        reverse("contas:entrar"), {"username": "ana@exemplo.com", "password": "errada"}
    )

    assert resposta.status_code == 200
    assert "E-mail ou senha incorretos." in resposta.content.decode()


def test_bloqueia_apos_muitas_tentativas(cliente_anonimo):
    _, senha = services.criar_usuario(nome="Ana", email="ana@exemplo.com")
    url = reverse("contas:entrar")
    for _ in range(LIMITE_TENTATIVAS):
        cliente_anonimo.post(url, {"username": "ana@exemplo.com", "password": "errada"})

    # Mesmo a senha certa é recusada durante o bloqueio.
    resposta = cliente_anonimo.post(url, {"username": "ana@exemplo.com", "password": senha})

    assert resposta.status_code == 200
    assert "Muitas tentativas sem sucesso" in resposta.content.decode()


def test_destino_externo_e_ignorado(cliente_anonimo):
    usuario, senha = services.criar_usuario(nome="Ana", email="ana@exemplo.com")
    usuario.deve_trocar_senha = False
    usuario.save()

    resposta = cliente_anonimo.post(
        reverse("contas:entrar") + "?next=https://outro-site.com/",
        {"username": "ana@exemplo.com", "password": senha},
    )

    assert resposta.url == "/"


def test_senha_temporaria_obriga_a_criar_senha_nova(cliente_anonimo):
    _, senha = services.criar_usuario(nome="Ana", email="ana@exemplo.com")
    cliente_anonimo.post(
        reverse("contas:entrar"), {"username": "ana@exemplo.com", "password": senha}
    )

    resposta = cliente_anonimo.get(reverse("okrs:objetivo_lista"))
    assert resposta.url == reverse("contas:trocar_senha")

    nova = "Uma-senha-nova-e-longa-2026"
    resposta = cliente_anonimo.post(
        reverse("contas:trocar_senha"), {"new_password1": nova, "new_password2": nova}
    )
    assert resposta.status_code == 302
    assert cliente_anonimo.get(reverse("okrs:objetivo_lista")).status_code == 200
    usuario = Usuario.objects.get(email="ana@exemplo.com")
    assert usuario.check_password(nova)
    assert usuario.deve_trocar_senha is False


def test_sair_encerra_a_sessao(client):
    resposta = client.post(reverse("contas:sair"))

    assert resposta.url == reverse("contas:entrar")
    assert client.get("/").status_code == 302


def test_alteracoes_registram_o_usuario_autenticado(client, usuario_admin):
    client.post(reverse("cadastros:empresa_nova"), {"nome": "Empresa Alfa", "sigla": "ALF"})

    empresa = Empresa.objects.get(sigla="ALF")
    registro = RegistroAlteracao.objects.get(objeto_id=empresa.pk, acao="criacao")
    assert registro.usuario == usuario_admin
    assert registro.ator_descricao == "Admin Teste"


# ---------------------------------------------------------------- usuários


def test_usuario_comum_nao_acessa_a_tela_de_usuarios(cliente_anonimo):
    usuario, _ = services.criar_usuario(nome="Ana", email="ana@exemplo.com")
    usuario.deve_trocar_senha = False
    usuario.save()
    cliente_anonimo.force_login(usuario)

    assert cliente_anonimo.get(reverse("contas:usuario_lista")).status_code == 403
    assert "Usuários" not in cliente_anonimo.get("/").content.decode().split("</nav>")[0]


def test_administrador_cria_usuario_e_ve_a_senha_uma_vez(client):
    resposta = client.post(
        reverse("contas:usuario_novo"),
        {"nome": "Bruno Lima", "email": "bruno@exemplo.com"},
    )

    conteudo = resposta.content.decode()
    usuario = Usuario.objects.get(email="bruno@exemplo.com")
    assert "Usuário criado" in conteudo
    assert usuario.deve_trocar_senha is True
    assert usuario.administrador is False
    assert "Bruno Lima" in client.get(reverse("contas:usuario_lista")).content.decode()


def test_email_repetido_e_recusado(client):
    services.criar_usuario(nome="Bruno", email="bruno@exemplo.com")

    resposta = client.post(
        reverse("contas:usuario_novo"), {"nome": "Outro", "email": "BRUNO@exemplo.com"}
    )

    assert "Já existe uma conta com este e-mail." in resposta.content.decode()


def test_redefinir_senha_troca_a_senha(client):
    usuario, antiga = services.criar_usuario(nome="Bruno", email="bruno@exemplo.com")

    client.post(reverse("contas:usuario_redefinir_senha", args=[usuario.pk]))

    usuario.refresh_from_db()
    assert not usuario.check_password(antiga)
    assert usuario.deve_trocar_senha is True


def test_desativar_e_reativar_usuario(client):
    usuario, _ = services.criar_usuario(nome="Bruno", email="bruno@exemplo.com")
    url = reverse("contas:usuario_ativo", args=[usuario.pk])

    client.post(url, {"ativo": "0"})
    usuario.refresh_from_db()
    assert usuario.is_active is False

    client.post(url, {"ativo": "1"})
    usuario.refresh_from_db()
    assert usuario.is_active is True


def test_administrador_nao_desativa_a_propria_conta(client, usuario_admin):
    resposta = client.post(
        reverse("contas:usuario_ativo", args=[usuario_admin.pk]), {"ativo": "0"}, follow=True
    )

    usuario_admin.refresh_from_db()
    assert usuario_admin.is_active is True
    assert "Você não pode desativar a própria conta." in resposta.content.decode()


def test_comando_cria_administrador(capsys):
    call_command("criar_administrador", "--email", "Chefe@Exemplo.com", "--nome", "Chefe Geral")

    usuario = Usuario.objects.get(email="chefe@exemplo.com")
    assert usuario.administrador is True
    assert usuario.deve_trocar_senha is True
    assert "Senha temporária:" in capsys.readouterr().out
