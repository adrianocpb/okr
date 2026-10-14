"""Regras de gravação de objetivos e de seus vínculos."""

from django.db import transaction
from django.db.models import Max

from apps.auditoria.models import RegistroAlteracao
from apps.auditoria.services import registrar_alteracao
from apps.cadastros import selectors as cadastros
from apps.cadastros.models import Ciclo, Pessoa
from apps.core import services
from apps.core.acesso import Ator, EscopoAcesso
from apps.core.erros import ErroDeNegocio
from apps.core.texto import espacos_simples
from apps.okrs import selectors
from apps.okrs.models import Marco, Objetivo, ResultadoChave, VinculoObjetivo

Acao = RegistroAlteracao.Acao

CAMPOS_EDITAVEIS = (
    "ciclo",
    "titulo",
    "descricao",
    "owner",
    "sponsor",
    "status",
    "comentario_status",
)


def _resolver_referencias(dados: dict) -> dict:
    """Aceita ids de ciclo, owner e sponsor e devolve as instâncias."""
    resolvidos = dict(dados)
    if isinstance(resolvidos.get("ciclo"), int):
        resolvidos["ciclo"] = Ciclo.objects.get(pk=resolvidos["ciclo"])
    for campo in ("owner", "sponsor"):
        if isinstance(resolvidos.get(campo), int):
            resolvidos[campo] = Pessoa.objects.get(pk=resolvidos[campo])
    return resolvidos


def criar_objetivo(*, empresa_id: int, dados: dict, ator: Ator, escopo: EscopoAcesso) -> Objetivo:
    empresa = cadastros.obter_empresa(escopo, empresa_id)
    if empresa.arquivado:
        raise ErroDeNegocio("Empresa arquivada não pode receber novos objetivos.")
    dados = _resolver_referencias({k: v for k, v in dados.items() if k in CAMPOS_EDITAVEIS})
    return services.criar(Objetivo(empresa=empresa, **dados), ator=ator)


def atualizar_objetivo(
    objetivo_id: int, *, dados: dict, versao: int, ator: Ator, escopo: EscopoAcesso
) -> Objetivo:
    """Atualiza o objetivo. A empresa não muda após a criação."""
    objetivo = selectors.obter_objetivo(escopo, objetivo_id)
    dados = _resolver_referencias({k: v for k, v in dados.items() if k in CAMPOS_EDITAVEIS})
    return services.atualizar(objetivo, dados, versao_esperada=versao, ator=ator)


def _registrar_vinculo(acao: str, vinculo: VinculoObjetivo, ator: Ator) -> None:
    """Registra o vínculo no histórico dos dois objetivos envolvidos."""
    anual, trimestral = vinculo.objetivo_anual, vinculo.objetivo_trimestral
    rotulo_anual = f"{anual.titulo} ({anual.ciclo.rotulo})"
    rotulo_trimestral = f"{trimestral.titulo} ({trimestral.ciclo.rotulo})"
    criando = acao == Acao.VINCULO
    registrar_alteracao(
        objeto=trimestral,
        acao=acao,
        ator=ator,
        alteracoes={
            "objetivo_anual": {
                "antes": None if criando else rotulo_anual,
                "depois": rotulo_anual if criando else None,
            }
        },
    )
    registrar_alteracao(
        objeto=anual,
        acao=acao,
        ator=ator,
        alteracoes={
            "objetivo_trimestral": {
                "antes": None if criando else rotulo_trimestral,
                "depois": rotulo_trimestral if criando else None,
            }
        },
    )


@transaction.atomic
def vincular(
    *, objetivo_trimestral_id: int, objetivo_anual_id: int, ator: Ator, escopo: EscopoAcesso
) -> VinculoObjetivo:
    trimestral = selectors.obter_objetivo(escopo, objetivo_trimestral_id)
    anual = selectors.obter_objetivo(escopo, objetivo_anual_id)
    vinculo = VinculoObjetivo(objetivo_anual=anual, objetivo_trimestral=trimestral)
    vinculo.full_clean()
    vinculo.save()
    _registrar_vinculo(Acao.VINCULO, vinculo, ator)
    return vinculo


@transaction.atomic
def desvincular(vinculo_id: int, *, ator: Ator, escopo: EscopoAcesso) -> None:
    vinculo = (
        VinculoObjetivo.objects.select_related(
            "objetivo_anual__ciclo", "objetivo_trimestral__ciclo"
        )
        .filter(pk=vinculo_id)
        .first()
    )
    if vinculo is None:
        raise ErroDeNegocio("Vínculo não encontrado.")
    # Verifica o acesso pelo objetivo (lança AcessoNegado se estiver fora do escopo).
    selectors.obter_objetivo(escopo, vinculo.objetivo_trimestral_id)
    _registrar_vinculo(Acao.DESVINCULO, vinculo, ator)
    vinculo.delete()


# --------------------------------------------------------------------- KRs

CAMPOS_KR = (
    "titulo",
    "descricao",
    "responsavel",
    "tipo_medicao",
    "regra",
    "unidade",
    "casas_decimais",
    "valor_inicial",
    "meta",
    "limite_inferior",
    "limite_superior",
    "frequencia_checkin_dias",
    "status",
)


def _dados_kr(dados: dict) -> dict:
    filtrados = {k: v for k, v in dados.items() if k in CAMPOS_KR}
    if isinstance(filtrados.get("responsavel"), int):
        filtrados["responsavel"] = Pessoa.objects.get(pk=filtrados["responsavel"])
    if filtrados.get("regra") is None and "regra" in filtrados:
        filtrados["regra"] = ""
    return filtrados


def criar_kr(*, objetivo_id: int, dados: dict, ator: Ator, escopo: EscopoAcesso) -> ResultadoChave:
    objetivo = selectors.obter_objetivo(escopo, objetivo_id)
    if objetivo.encerrado:
        raise ErroDeNegocio("Objetivo concluído ou cancelado não recebe novos KRs.")
    return services.criar(ResultadoChave(objetivo=objetivo, **_dados_kr(dados)), ator=ator)


def atualizar_kr(
    kr_id: int, *, dados: dict, versao: int, ator: Ator, escopo: EscopoAcesso
) -> ResultadoChave:
    """Atualiza o KR. O objetivo ao qual pertence não muda."""
    kr = selectors.obter_kr(escopo, kr_id)
    return services.atualizar(kr, _dados_kr(dados), versao_esperada=versao, ator=ator)


@transaction.atomic
def adicionar_marco(
    kr_id: int, *, descricao: str, prazo=None, ator: Ator, escopo: EscopoAcesso
) -> Marco:
    kr = selectors.obter_kr(escopo, kr_id)
    if kr.tipo_medicao != ResultadoChave.TipoMedicao.MARCOS:
        raise ErroDeNegocio("Marcos só podem ser cadastrados em KRs do tipo Marcos.")
    ultima = kr.marcos.aggregate(maior=Max("ordem"))["maior"] or 0
    marco = Marco(kr=kr, descricao=espacos_simples(descricao), ordem=ultima + 1, prazo=prazo)
    marco.full_clean()
    marco.save()
    registrar_alteracao(
        objeto=kr,
        acao=Acao.ALTERACAO,
        ator=ator,
        alteracoes={"marco": {"antes": None, "depois": str(marco)}},
    )
    return marco


@transaction.atomic
def remover_marco(marco_id: int, *, ator: Ator, escopo: EscopoAcesso) -> None:
    marco = Marco.objects.filter(pk=marco_id).first()
    if marco is None:
        raise ErroDeNegocio("Marco não encontrado.")
    kr = selectors.obter_kr(escopo, marco.kr_id)
    registrar_alteracao(
        objeto=kr,
        acao=Acao.ALTERACAO,
        ator=ator,
        alteracoes={"marco": {"antes": str(marco), "depois": None}},
    )
    marco.delete()
