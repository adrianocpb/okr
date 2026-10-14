"""Erros de negócio com mensagens destinadas ao usuário (em português)."""


class ErroDeNegocio(Exception):
    """Regra de negócio violada. A mensagem é exibida ao usuário."""

    status_http = 400

    def __init__(self, mensagem: str):
        super().__init__(mensagem)
        self.mensagem = mensagem


class ConflitoDeVersao(ErroDeNegocio):
    status_http = 409

    def __init__(self, mensagem: str | None = None):
        super().__init__(
            mensagem
            or "Este registro foi alterado por outra pessoa enquanto você editava. "
            "Recarregue a página para ver a versão atual e refaça a alteração."
        )


class AcessoNegado(ErroDeNegocio):
    status_http = 404  # não revela a existência de registros de outras empresas

    def __init__(self, mensagem: str = "Registro não encontrado."):
        super().__init__(mensagem)
