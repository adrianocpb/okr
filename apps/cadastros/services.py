"""Regras de gravação de empresas, pessoas e ciclos."""

from collections.abc import Iterable
from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.auditoria.models import RegistroAlteracao
from apps.auditoria.services import registrar_alteracao
from apps.cadastros import selectors
from apps.cadastros.models import Ciclo, Empresa, Pessoa, VinculoPessoaEmpresa
from apps.core import services
from apps.core.acesso import Ator, EscopoAcesso
from apps.core.datas import fim_do_periodo, somar_meses
from apps.core.erros import ErroDeNegocio, PermissaoNegada

Acao = RegistroAlteracao.Acao


def _gravar_protegido(funcao, mensagem_duplicidade: str):
    """Converte violação de unicidade do banco (corrida entre duas gravações) em erro amigável."""
    try:
        with transaction.atomic():
            return funcao()
    except IntegrityError as exc:
        raise ErroDeNegocio(mensagem_duplicidade) from exc


# ---------------------------------------------------------------- empresas


def criar_empresa(*, nome: str, sigla: str, ator: Ator, escopo: EscopoAcesso) -> Empresa:
    if not escopo.irrestrito:
        raise PermissaoNegada("Somente administradores podem cadastrar empresas.")
    return _gravar_protegido(
        lambda: services.criar(Empresa(nome=nome, sigla=sigla), ator=ator),
        "Já existe uma empresa com este nome ou sigla.",
    )


def atualizar_empresa(
    empresa_id: int, *, nome: str, sigla: str, versao: int, ator: Ator, escopo: EscopoAcesso
) -> Empresa:
    empresa = selectors.obter_empresa(escopo, empresa_id)
    return _gravar_protegido(
        lambda: services.atualizar(
            empresa, {"nome": nome, "sigla": sigla}, versao_esperada=versao, ator=ator
        ),
        "Já existe uma empresa com este nome ou sigla.",
    )


def arquivar_empresa(empresa_id: int, *, versao: int, ator: Ator, escopo: EscopoAcesso) -> Empresa:
    empresa = selectors.obter_empresa(escopo, empresa_id)
    return services.arquivar(empresa, versao_esperada=versao, ator=ator)


def reativar_empresa(empresa_id: int, *, versao: int, ator: Ator, escopo: EscopoAcesso) -> Empresa:
    empresa = selectors.obter_empresa(escopo, empresa_id)
    return services.reativar(empresa, versao_esperada=versao, ator=ator)


# ----------------------------------------------------------------- pessoas


def _validar_empresas_selecionadas(
    selecionadas: set[int], *, ja_vinculadas: set[int], escopo: EscopoAcesso
) -> dict[int, Empresa]:
    """Confere se as empresas existem, estão no escopo e, se novas, estão ativas."""
    empresas = {e.pk: e for e in escopo.filtrar(Empresa.objects.filter(pk__in=selecionadas), "id")}
    if set(empresas) != selecionadas:
        raise ValidationError({"empresas": "Selecione apenas empresas disponíveis."})
    arquivadas_novas = [
        e.sigla for pk, e in empresas.items() if e.arquivado and pk not in ja_vinculadas
    ]
    if arquivadas_novas:
        siglas = ", ".join(arquivadas_novas)
        raise ValidationError(
            {"empresas": f"Empresa arquivada não pode receber novos vínculos: {siglas}."}
        )
    return empresas


def _vincular(pessoa: Pessoa, empresa: Empresa, ator: Ator) -> None:
    VinculoPessoaEmpresa.objects.create(pessoa=pessoa, empresa=empresa)
    registrar_alteracao(
        objeto=pessoa,
        acao=Acao.VINCULO,
        ator=ator,
        alteracoes={"empresa": {"antes": None, "depois": str(empresa)}},
        empresa_id=empresa.pk,
    )


def _desvincular(pessoa: Pessoa, empresa: Empresa, ator: Ator) -> None:
    VinculoPessoaEmpresa.objects.filter(pessoa=pessoa, empresa=empresa).delete()
    registrar_alteracao(
        objeto=pessoa,
        acao=Acao.DESVINCULO,
        ator=ator,
        alteracoes={"empresa": {"antes": str(empresa), "depois": None}},
        empresa_id=empresa.pk,
    )


def criar_pessoa(
    *,
    nome: str,
    email: str | None,
    empresas_ids: Iterable[int],
    ator: Ator,
    escopo: EscopoAcesso,
) -> Pessoa:
    selecionadas = set(empresas_ids)
    if not selecionadas:
        raise ValidationError({"empresas": "Selecione ao menos uma empresa."})
    empresas = _validar_empresas_selecionadas(selecionadas, ja_vinculadas=set(), escopo=escopo)

    def gravar():
        pessoa = services.criar(Pessoa(nome=nome, email=email), ator=ator)
        for empresa in sorted(empresas.values(), key=lambda e: e.sigla):
            _vincular(pessoa, empresa, ator)
        return pessoa

    return _gravar_protegido(gravar, "Já existe uma pessoa com este e-mail.")


def atualizar_pessoa(
    pessoa_id: int,
    *,
    nome: str,
    email: str | None,
    empresas_ids: Iterable[int],
    versao: int,
    ator: Ator,
    escopo: EscopoAcesso,
) -> Pessoa:
    """Atualiza dados e vínculos. Vínculos com empresas fora do escopo de quem
    edita são preservados (não aparecem para essa pessoa, então não podem ser
    removidos por ela)."""
    pessoa = selectors.obter_pessoa(escopo, pessoa_id)
    atuais = set(pessoa.vinculos.values_list("empresa_id", flat=True))
    fora_do_escopo = {pk for pk in atuais if not escopo.permite(pk)}
    selecionadas = set(empresas_ids)
    empresas = _validar_empresas_selecionadas(selecionadas, ja_vinculadas=atuais, escopo=escopo)

    finais = fora_do_escopo | selecionadas
    if not finais:
        raise ValidationError({"empresas": "Selecione ao menos uma empresa."})
    adicionar = selecionadas - atuais
    remover = (atuais - fora_do_escopo) - selecionadas

    def gravar():
        versao_antes = pessoa.versao
        atualizada = services.atualizar(
            pessoa, {"nome": nome, "email": email}, versao_esperada=versao, ator=ator
        )
        if (adicionar or remover) and atualizada.versao == versao_antes:
            services.confirmar_versao(atualizada, versao)
        for empresa in Empresa.objects.filter(pk__in=remover).order_by("sigla"):
            _desvincular(atualizada, empresa, ator)
        for pk in sorted(adicionar, key=lambda pk: empresas[pk].sigla):
            _vincular(atualizada, empresas[pk], ator)
        return atualizada

    return _gravar_protegido(gravar, "Já existe uma pessoa com este e-mail.")


def arquivar_pessoa(pessoa_id: int, *, versao: int, ator: Ator, escopo: EscopoAcesso) -> Pessoa:
    pessoa = selectors.obter_pessoa(escopo, pessoa_id)
    return services.arquivar(pessoa, versao_esperada=versao, ator=ator)


def reativar_pessoa(pessoa_id: int, *, versao: int, ator: Ator, escopo: EscopoAcesso) -> Pessoa:
    pessoa = selectors.obter_pessoa(escopo, pessoa_id)
    return services.reativar(pessoa, versao_esperada=versao, ator=ator)


# ------------------------------------------------------------------ ciclos

MENSAGEM_CICLO_DUPLICADO = "Já existe um ciclo ativo igual para esta empresa."


def periodo_padrao_do_trimestre(anual: Ciclo, trimestre: int) -> tuple[date, date] | None:
    """Datas sugeridas para o trimestre: blocos de 3 meses a partir do início do ano.

    Só há sugestão quando o ciclo anual começa no dia 1 e dura exatamente 12 meses.
    """
    if not anual_regular(anual):
        return None
    inicio = somar_meses(anual.data_inicio, 3 * (trimestre - 1))
    return inicio, fim_do_periodo(inicio, 3)


def anual_regular(anual: Ciclo) -> bool:
    return anual.data_inicio.day == 1 and anual.data_fim == fim_do_periodo(anual.data_inicio, 12)


def criar_ciclo_anual(
    *,
    empresa_id: int,
    ano: int,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    ator: Ator,
    escopo: EscopoAcesso,
) -> Ciclo:
    """Cria um ciclo anual. Sem datas, assume o ano civil (01/01 a 31/12)."""
    empresa = selectors.obter_empresa(escopo, empresa_id)
    if empresa.arquivado:
        raise ErroDeNegocio("Empresa arquivada não pode receber novos ciclos.")
    if (data_inicio is None) != (data_fim is None):
        raise ValidationError(
            {"data_fim": "Informe as duas datas ou deixe ambas em branco para usar o ano civil."}
        )
    if data_inicio is None:
        data_inicio, data_fim = date(ano, 1, 1), date(ano, 12, 31)
    ciclo = Ciclo(
        empresa=empresa,
        tipo=Ciclo.Tipo.ANUAL,
        ano=ano,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
    return _gravar_protegido(lambda: services.criar(ciclo, ator=ator), MENSAGEM_CICLO_DUPLICADO)


def criar_trimestre(
    *,
    ciclo_anual_id: int,
    trimestre: int,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    ator: Ator,
    escopo: EscopoAcesso,
) -> Ciclo:
    """Cria um trimestre no ciclo anual. Sem datas, usa o período padrão do trimestre."""
    anual = selectors.obter_ciclo(escopo, ciclo_anual_id)
    if anual.tipo != Ciclo.Tipo.ANUAL:
        raise ErroDeNegocio("Trimestres só podem ser criados em ciclos anuais.")
    if anual.arquivado:
        raise ErroDeNegocio("Ciclo anual arquivado não pode receber novos trimestres.")
    if (data_inicio is None) != (data_fim is None):
        raise ValidationError(
            {
                "data_fim": "Informe as duas datas ou deixe ambas em branco "
                "para usar o período padrão."
            }
        )
    if data_inicio is None:
        padrao = periodo_padrao_do_trimestre(anual, trimestre)
        if padrao is None:
            raise ValidationError(
                {
                    "data_inicio": "Este ciclo anual não começa no dia 1 ou não dura 12 meses; "
                    "informe as datas do trimestre."
                }
            )
        data_inicio, data_fim = padrao
    ciclo = Ciclo(
        empresa_id=anual.empresa_id,
        tipo=Ciclo.Tipo.TRIMESTRAL,
        ano=anual.ano,
        trimestre=trimestre,
        ciclo_anual=anual,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )
    return _gravar_protegido(lambda: services.criar(ciclo, ator=ator), MENSAGEM_CICLO_DUPLICADO)


def gerar_trimestres(ciclo_anual_id: int, *, ator: Ator, escopo: EscopoAcesso) -> list[Ciclo]:
    """Cria, de uma vez, os trimestres que ainda não existem no ciclo anual."""
    anual = selectors.obter_ciclo(escopo, ciclo_anual_id)
    if anual.tipo != Ciclo.Tipo.ANUAL:
        raise ErroDeNegocio("Trimestres só podem ser gerados em ciclos anuais.")
    if not anual_regular(anual):
        raise ErroDeNegocio(
            "A geração automática exige um ciclo anual que comece no dia 1 e dure 12 meses. "
            "Cadastre os trimestres individualmente, informando as datas."
        )
    existentes = set(
        anual.trimestres.filter(arquivado_em__isnull=True).values_list("trimestre", flat=True)
    )
    faltantes = [t for t in (1, 2, 3, 4) if t not in existentes]
    if not faltantes:
        raise ErroDeNegocio("Este ciclo anual já tem os quatro trimestres.")
    with transaction.atomic():
        return [
            criar_trimestre(ciclo_anual_id=anual.pk, trimestre=t, ator=ator, escopo=escopo)
            for t in faltantes
        ]


def atualizar_ciclo(
    ciclo_id: int,
    *,
    dados: dict,
    versao: int,
    ator: Ator,
    escopo: EscopoAcesso,
) -> Ciclo:
    """Atualiza datas e o ano (anual) ou o trimestre (trimestral).

    Empresa, tipo e ciclo anual não mudam após a criação.
    """
    ciclo = selectors.obter_ciclo(escopo, ciclo_id)
    if ciclo.arquivado:
        raise ErroDeNegocio("Reative o ciclo antes de editá-lo.")
    permitidos = {"data_inicio", "data_fim"} | (
        {"ano"} if ciclo.tipo == Ciclo.Tipo.ANUAL else {"trimestre"}
    )
    return _gravar_protegido(
        lambda: services.atualizar(
            ciclo,
            {campo: valor for campo, valor in dados.items() if campo in permitidos},
            versao_esperada=versao,
            ator=ator,
        ),
        MENSAGEM_CICLO_DUPLICADO,
    )


def arquivar_ciclo(ciclo_id: int, *, versao: int, ator: Ator, escopo: EscopoAcesso) -> Ciclo:
    ciclo = selectors.obter_ciclo(escopo, ciclo_id)
    if (
        ciclo.tipo == Ciclo.Tipo.ANUAL
        and ciclo.trimestres.filter(arquivado_em__isnull=True).exists()
    ):
        raise ErroDeNegocio("Arquive primeiro os trimestres ativos deste ciclo anual.")
    return services.arquivar(ciclo, versao_esperada=versao, ator=ator)


def reativar_ciclo(ciclo_id: int, *, versao: int, ator: Ator, escopo: EscopoAcesso) -> Ciclo:
    ciclo = selectors.obter_ciclo(escopo, ciclo_id)
    if ciclo.empresa.arquivado:
        raise ErroDeNegocio("Reative a empresa antes de reativar o ciclo.")
    if ciclo.tipo == Ciclo.Tipo.TRIMESTRAL and ciclo.ciclo_anual.arquivado:
        raise ErroDeNegocio("Reative o ciclo anual antes de reativar o trimestre.")
    # Ao voltar a ficar ativo, o ciclo não pode conflitar com outro ciclo ativo.
    if ciclo.tipo == Ciclo.Tipo.TRIMESTRAL and (
        Ciclo.objects.filter(
            ciclo_anual_id=ciclo.ciclo_anual_id,
            trimestre=ciclo.trimestre,
            arquivado_em__isnull=True,
        ).exists()
    ):
        raise ErroDeNegocio(f"O ciclo anual já tem outro {ciclo.trimestre}º trimestre ativo.")
    if ciclo.tipo == Ciclo.Tipo.ANUAL and (
        Ciclo.objects.filter(
            empresa_id=ciclo.empresa_id,
            tipo=Ciclo.Tipo.ANUAL,
            ano=ciclo.ano,
            arquivado_em__isnull=True,
        ).exists()
    ):
        raise ErroDeNegocio(f"A empresa já tem outro ciclo anual de {ciclo.ano} ativo.")
    conflito = ciclo.conflito_de_periodo()
    if conflito:
        raise ErroDeNegocio(
            f"O período se sobrepõe ao ciclo ativo {conflito.rotulo} ({conflito.periodo})."
        )
    return services.reativar(ciclo, versao_esperada=versao, ator=ator)
