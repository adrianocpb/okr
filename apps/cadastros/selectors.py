"""Consultas de empresas, pessoas e ciclos, sempre limitadas pelo escopo de acesso."""

from datetime import date

from django.db.models import Count, Prefetch, Q, QuerySet
from django.utils import timezone

from apps.cadastros.models import Ciclo, Empresa, Pessoa
from apps.core.acesso import EscopoAcesso
from apps.core.erros import AcessoNegado
from apps.core.texto import chave_busca

SITUACOES = {
    "ativas": "Ativas",
    "arquivadas": "Arquivadas",
    "todas": "Todas",
}


def _filtrar_situacao(queryset: QuerySet, situacao: str) -> QuerySet:
    if situacao == "arquivadas":
        return queryset.filter(arquivado_em__isnull=False)
    if situacao == "todas":
        return queryset
    return queryset.filter(arquivado_em__isnull=True)


# ---------------------------------------------------------------- empresas


def _empresas_visiveis(escopo: EscopoAcesso) -> QuerySet:
    return escopo.filtrar(Empresa.objects.all(), campo="id")


def listar_empresas(escopo: EscopoAcesso, *, situacao: str = "ativas", busca: str = "") -> QuerySet:
    empresas = _filtrar_situacao(_empresas_visiveis(escopo), situacao)
    if busca.strip():
        empresas = empresas.filter(
            Q(chave_nome__contains=chave_busca(busca)) | Q(sigla__icontains=busca.strip())
        )
    return empresas.annotate(
        total_pessoas=Count("vinculos", filter=Q(vinculos__pessoa__arquivado_em__isnull=True))
    ).order_by("chave_nome")


def obter_empresa(escopo: EscopoAcesso, empresa_id: int) -> Empresa:
    try:
        return _empresas_visiveis(escopo).get(pk=empresa_id)
    except Empresa.DoesNotExist as exc:
        raise AcessoNegado() from exc


def empresas_para_vinculo(escopo: EscopoAcesso) -> QuerySet:
    """Empresas que podem receber novos vínculos: ativas e dentro do escopo."""
    return _filtrar_situacao(_empresas_visiveis(escopo), "ativas")


# ----------------------------------------------------------------- pessoas


def _pessoas_visiveis(escopo: EscopoAcesso) -> QuerySet:
    """Uma pessoa é visível se tiver vínculo com ao menos uma empresa do escopo."""
    pessoas = Pessoa.objects.all()
    if not escopo.irrestrito:
        pessoas = pessoas.filter(vinculos__empresa_id__in=escopo.empresas_ids).distinct()
    return pessoas


def _com_empresas(pessoas: QuerySet, escopo: EscopoAcesso) -> QuerySet:
    return pessoas.prefetch_related(
        Prefetch(
            "empresas",
            queryset=escopo.filtrar(Empresa.objects.order_by("sigla"), campo="id"),
            to_attr="empresas_visiveis",
        )
    )


def listar_pessoas(
    escopo: EscopoAcesso,
    *,
    situacao: str = "ativas",
    busca: str = "",
    empresa_id: int | None = None,
) -> QuerySet:
    pessoas = _filtrar_situacao(_pessoas_visiveis(escopo), situacao)
    if empresa_id:
        pessoas = pessoas.filter(vinculos__empresa_id=empresa_id)
    if busca.strip():
        pessoas = pessoas.filter(
            Q(chave_nome__contains=chave_busca(busca)) | Q(email__icontains=busca.strip())
        )
    return _com_empresas(pessoas.distinct(), escopo)


def obter_pessoa(escopo: EscopoAcesso, pessoa_id: int) -> Pessoa:
    try:
        return _com_empresas(_pessoas_visiveis(escopo), escopo).get(pk=pessoa_id)
    except Pessoa.DoesNotExist as exc:
        raise AcessoNegado() from exc


def pessoas_da_empresa(escopo: EscopoAcesso, empresa: Empresa) -> QuerySet:
    return listar_pessoas(escopo, situacao="todas", empresa_id=empresa.pk).order_by(
        "arquivado_em", "chave_nome"
    )


# ------------------------------------------------------------------ ciclos

SITUACOES_CICLO = {
    "": "Todas",
    Ciclo.Situacao.PLANEJADO: Ciclo.Situacao.PLANEJADO.label,
    Ciclo.Situacao.EM_ANDAMENTO: Ciclo.Situacao.EM_ANDAMENTO.label,
    Ciclo.Situacao.ENCERRADO: Ciclo.Situacao.ENCERRADO.label,
}


def _ciclos_visiveis(escopo: EscopoAcesso) -> QuerySet:
    return escopo.filtrar(Ciclo.objects.select_related("empresa", "ciclo_anual"), "empresa_id")


def _filtrar_situacao_ciclo(ciclos: QuerySet, situacao: str, hoje: date) -> QuerySet:
    if situacao == Ciclo.Situacao.PLANEJADO:
        return ciclos.filter(data_inicio__gt=hoje)
    if situacao == Ciclo.Situacao.EM_ANDAMENTO:
        return ciclos.filter(data_inicio__lte=hoje, data_fim__gte=hoje)
    if situacao == Ciclo.Situacao.ENCERRADO:
        return ciclos.filter(data_fim__lt=hoje)
    return ciclos


def listar_ciclos(
    escopo: EscopoAcesso,
    *,
    empresa_id: int | None = None,
    ano: int | None = None,
    tipo: str = "",
    situacao: str = "",
    incluir_arquivados: bool = False,
    hoje: date | None = None,
) -> QuerySet:
    ciclos = _ciclos_visiveis(escopo)
    if not incluir_arquivados:
        ciclos = ciclos.filter(arquivado_em__isnull=True)
    if empresa_id:
        ciclos = ciclos.filter(empresa_id=empresa_id)
    if ano:
        ciclos = ciclos.filter(ano=ano)
    if tipo in Ciclo.Tipo.values:
        ciclos = ciclos.filter(tipo=tipo)
    ciclos = _filtrar_situacao_ciclo(ciclos, situacao, hoje or timezone.localdate())
    return ciclos.order_by("empresa__sigla", "-ano", "tipo", "trimestre", "id")


def anos_com_ciclos(escopo: EscopoAcesso) -> list[int]:
    return sorted(set(_ciclos_visiveis(escopo).values_list("ano", flat=True)), reverse=True)


def obter_ciclo(escopo: EscopoAcesso, ciclo_id: int) -> Ciclo:
    try:
        return _ciclos_visiveis(escopo).get(pk=ciclo_id)
    except Ciclo.DoesNotExist as exc:
        raise AcessoNegado() from exc


def ciclos_da_empresa(escopo: EscopoAcesso, empresa: Empresa) -> QuerySet:
    return listar_ciclos(escopo, empresa_id=empresa.pk)


def trimestres_do_ciclo(ciclo: Ciclo) -> QuerySet:
    return ciclo.trimestres.select_related("empresa").order_by("arquivado_em", "trimestre")
