"""Regras de gravação de objetivos e de seus vínculos."""

from django.core.exceptions import ValidationError
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
from apps.okrs.models import (
    Iniciativa,
    IniciativaKR,
    Marco,
    Objetivo,
    ResultadoChave,
    VinculoObjetivo,
)

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
    if marco.itens_checkin.exists():
        raise ErroDeNegocio("Este marco já foi registrado em check-ins e não pode ser removido.")
    registrar_alteracao(
        objeto=kr,
        acao=Acao.ALTERACAO,
        ator=ator,
        alteracoes={"marco": {"antes": str(marco), "depois": None}},
    )
    marco.delete()


# ------------------------------------------------------------- iniciativas

CAMPOS_INICIATIVA = ("titulo", "descricao", "responsavel", "prazo", "status")


def _dados_iniciativa(dados: dict) -> dict:
    filtrados = {k: v for k, v in dados.items() if k in CAMPOS_INICIATIVA}
    if isinstance(filtrados.get("responsavel"), int):
        filtrados["responsavel"] = Pessoa.objects.get(pk=filtrados["responsavel"])
    return filtrados


def _krs_do_objetivo(objetivo: Objetivo, kr_ids) -> dict[int, ResultadoChave]:
    ids = set(kr_ids or [])
    krs = {kr.pk: kr for kr in objetivo.krs.filter(pk__in=ids)}
    if set(krs) != ids:
        raise ValidationError({"krs": "Selecione apenas KRs do mesmo objetivo da iniciativa."})
    return krs


def _registrar_vinculo_kr(iniciativa: Iniciativa, kr: ResultadoChave, acao: str, ator: Ator):
    criando = acao == Acao.VINCULO
    registrar_alteracao(
        objeto=iniciativa,
        acao=acao,
        ator=ator,
        alteracoes={
            "kr": {
                "antes": None if criando else kr.titulo,
                "depois": kr.titulo if criando else None,
            }
        },
    )


@transaction.atomic
def criar_iniciativa(
    *, objetivo_id: int, dados: dict, kr_ids=(), ator: Ator, escopo: EscopoAcesso
) -> Iniciativa:
    objetivo = selectors.obter_objetivo(escopo, objetivo_id)
    if objetivo.encerrado:
        raise ErroDeNegocio("Objetivo concluído ou cancelado não recebe novas iniciativas.")
    krs = _krs_do_objetivo(objetivo, kr_ids)
    iniciativa = services.criar(
        Iniciativa(objetivo=objetivo, **_dados_iniciativa(dados)), ator=ator
    )
    for kr in sorted(krs.values(), key=lambda k: k.pk):
        IniciativaKR.objects.create(iniciativa=iniciativa, kr=kr)
        _registrar_vinculo_kr(iniciativa, kr, Acao.VINCULO, ator)
    return iniciativa


@transaction.atomic
def atualizar_iniciativa(
    iniciativa_id: int,
    *,
    dados: dict,
    kr_ids=None,
    versao: int,
    ator: Ator,
    escopo: EscopoAcesso,
) -> Iniciativa:
    """Atualiza dados e, se `kr_ids` for informado, os KRs ligados. O objetivo não muda."""
    iniciativa = selectors.obter_iniciativa(escopo, iniciativa_id)
    versao_antes = iniciativa.versao
    iniciativa = services.atualizar(
        iniciativa, _dados_iniciativa(dados), versao_esperada=versao, ator=ator
    )
    if kr_ids is None:
        return iniciativa
    novos = _krs_do_objetivo(iniciativa.objetivo, kr_ids)
    atuais = {v.kr_id: v.kr for v in iniciativa.vinculos_kr.select_related("kr")}
    adicionar, remover = set(novos) - set(atuais), set(atuais) - set(novos)
    if (adicionar or remover) and iniciativa.versao == versao_antes:
        services.confirmar_versao(iniciativa, versao)
    for kr_id in sorted(remover):
        IniciativaKR.objects.filter(iniciativa=iniciativa, kr_id=kr_id).delete()
        _registrar_vinculo_kr(iniciativa, atuais[kr_id], Acao.DESVINCULO, ator)
    for kr_id in sorted(adicionar):
        IniciativaKR.objects.create(iniciativa=iniciativa, kr=novos[kr_id])
        _registrar_vinculo_kr(iniciativa, novos[kr_id], Acao.VINCULO, ator)
    return iniciativa
