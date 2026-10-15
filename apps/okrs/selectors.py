"""Consultas de objetivos, sempre limitadas pelo escopo de acesso."""

from datetime import date

from django.db.models import F, Q, QuerySet
from django.utils import timezone

from apps.cadastros.models import Ciclo, Empresa, Pessoa
from apps.core.acesso import EscopoAcesso
from apps.core.erros import AcessoNegado
from apps.core.texto import chave_busca
from apps.okrs.models import Iniciativa, Objetivo, ResultadoChave, VinculoObjetivo

STATUS_FILTRO = {"": "Todos", **dict(Objetivo.Status.choices)}


def _objetivos_visiveis(escopo: EscopoAcesso) -> QuerySet:
    return escopo.filtrar(
        Objetivo.objects.select_related("empresa", "ciclo", "owner", "sponsor"), "empresa_id"
    )


def listar_objetivos(
    escopo: EscopoAcesso,
    *,
    empresa_id: int | None = None,
    ciclo_id: int | None = None,
    status: str = "",
    busca: str = "",
) -> QuerySet:
    objetivos = _objetivos_visiveis(escopo)
    if empresa_id:
        objetivos = objetivos.filter(empresa_id=empresa_id)
    if ciclo_id:
        objetivos = objetivos.filter(ciclo_id=ciclo_id)
    if status in Objetivo.Status.values:
        objetivos = objetivos.filter(status=status)
    if busca.strip():
        objetivos = objetivos.filter(chave_titulo__contains=chave_busca(busca))
    return objetivos.order_by(
        "empresa__sigla", "-ciclo__ano", "ciclo__tipo", "ciclo__trimestre", "chave_titulo", "id"
    )


def obter_objetivo(escopo: EscopoAcesso, objetivo_id: int) -> Objetivo:
    try:
        return _objetivos_visiveis(escopo).get(pk=objetivo_id)
    except Objetivo.DoesNotExist as exc:
        raise AcessoNegado() from exc


def ciclos_para_objetivo(empresa: Empresa, atual: Ciclo | None = None) -> QuerySet:
    """Ciclos ativos da empresa (mais o atual do objetivo, mesmo se arquivado)."""
    filtro = Q(empresa=empresa, arquivado_em__isnull=True)
    if atual is not None:
        filtro |= Q(pk=atual.pk)
    return Ciclo.objects.filter(filtro).order_by("-ano", "tipo", "trimestre")


def pessoas_para_responsabilidade(empresa: Empresa, *atuais: Pessoa | None) -> QuerySet:
    """Pessoas ativas vinculadas à empresa (mais as já atribuídas, para não perdê-las)."""
    filtro = Q(vinculos__empresa=empresa, arquivado_em__isnull=True)
    ids_atuais = [p.pk for p in atuais if p is not None]
    if ids_atuais:
        filtro |= Q(pk__in=ids_atuais)
    return Pessoa.objects.filter(filtro).distinct().order_by("chave_nome", "id")


def vinculos_do_objetivo(objetivo: Objetivo) -> dict:
    vinculos = VinculoObjetivo.objects.select_related(
        "objetivo_anual__ciclo", "objetivo_trimestral__ciclo"
    )
    return {
        "anuais": vinculos.filter(objetivo_trimestral=objetivo).order_by("objetivo_anual__titulo"),
        "trimestrais": vinculos.filter(objetivo_anual=objetivo).order_by(
            "objetivo_trimestral__ciclo__trimestre", "objetivo_trimestral__titulo"
        ),
    }


def anuais_vinculaveis(objetivo: Objetivo) -> QuerySet:
    """Objetivos anuais aos quais um objetivo trimestral ainda pode ser vinculado."""
    if objetivo.ciclo.tipo != Ciclo.Tipo.TRIMESTRAL:
        return Objetivo.objects.none()
    return (
        Objetivo.objects.filter(
            empresa_id=objetivo.empresa_id,
            ciclo_id=objetivo.ciclo.ciclo_anual_id,
        )
        .exclude(vinculos_como_anual__objetivo_trimestral=objetivo)
        .exclude(status=Objetivo.Status.CANCELADO)
        .order_by("chave_titulo")
    )


def responsabilidades_da_pessoa(escopo: EscopoAcesso, pessoa: Pessoa) -> dict:
    objetivos = _objetivos_visiveis(escopo).order_by("-ciclo__ano", "chave_titulo")
    return {
        "owner": objetivos.filter(owner=pessoa),
        "sponsor": objetivos.filter(sponsor=pessoa),
        "iniciativas": _marcar_atraso(
            _iniciativas_visiveis(escopo)
            .filter(responsavel=pessoa)
            .order_by("-objetivo__ciclo__ano", "chave_titulo")
        ),
        "krs": _krs_visiveis(escopo)
        .filter(responsavel=pessoa)
        .order_by("-objetivo__ciclo__ano", "chave_titulo"),
    }


# --------------------------------------------------------------------- KRs


def _krs_visiveis(escopo: EscopoAcesso) -> QuerySet:
    return escopo.filtrar(
        ResultadoChave.objects.select_related(
            "objetivo__empresa", "objetivo__ciclo", "responsavel"
        ),
        "objetivo__empresa_id",
    )


def obter_kr(escopo: EscopoAcesso, kr_id: int) -> ResultadoChave:
    try:
        return _krs_visiveis(escopo).get(pk=kr_id)
    except ResultadoChave.DoesNotExist as exc:
        raise AcessoNegado() from exc


def krs_do_objetivo(objetivo: Objetivo) -> list[ResultadoChave]:
    """KRs do objetivo, cada um com sua situação de progresso em `kr.situacao`.

    Cada KR é exibido individualmente; não há soma nem média entre KRs (Q-09).
    """
    krs = list(
        objetivo.krs.select_related("responsavel", "objetivo__ciclo")
        .prefetch_related("marcos")
        .order_by("id")
    )
    from apps.acompanhamento.selectors import situacoes_em_lote

    situacoes_em_lote(krs)
    return krs


def situacao_do_kr(kr: ResultadoChave):
    """Progresso atual do KR, a partir do check-in vigente (cinza se não houver)."""
    # Importação local: o módulo de acompanhamento depende dos modelos de OKRs.
    from apps.acompanhamento.selectors import situacao_do_kr as situacao

    return situacao(kr)


# ------------------------------------------------------------- iniciativas


def _iniciativas_visiveis(escopo: EscopoAcesso) -> QuerySet:
    return escopo.filtrar(
        Iniciativa.objects.select_related("objetivo__empresa", "objetivo__ciclo", "responsavel"),
        "objetivo__empresa_id",
    )


def obter_iniciativa(escopo: EscopoAcesso, iniciativa_id: int) -> Iniciativa:
    try:
        return _iniciativas_visiveis(escopo).get(pk=iniciativa_id)
    except Iniciativa.DoesNotExist as exc:
        raise AcessoNegado() from exc


def _marcar_atraso(iniciativas, hoje: date | None = None) -> list[Iniciativa]:
    hoje = hoje or timezone.localdate()
    lista = list(iniciativas)
    for iniciativa in lista:
        iniciativa.atrasada = iniciativa.atrasada_em(hoje)
    return lista


def iniciativas_do_objetivo(objetivo: Objetivo, hoje: date | None = None) -> list[Iniciativa]:
    """Iniciativas do objetivo, com `iniciativa.atrasada` (prazo vencido e não encerrada)."""
    iniciativas = (
        objetivo.iniciativas.select_related("responsavel")
        .prefetch_related("krs")
        .order_by(F("prazo").asc(nulls_last=True), "id")
    )
    return _marcar_atraso(iniciativas, hoje)


def iniciativas_do_kr(kr: ResultadoChave, hoje: date | None = None) -> list[Iniciativa]:
    iniciativas = kr.iniciativas.select_related("responsavel").order_by(
        F("prazo").asc(nulls_last=True), "id"
    )
    return _marcar_atraso(iniciativas, hoje)


# ------------------------------------------------- comparação entre períodos


def desdobramento_trimestral(objetivo: Objetivo) -> list[dict]:
    """Objetivos trimestrais vinculados a um objetivo anual, agrupados por trimestre.

    Cada KR aparece com o próprio progresso; não há valor combinado entre KRs nem
    entre trimestres (as medidas podem ter unidades e naturezas diferentes).
    """
    if objetivo.ciclo.tipo != Ciclo.Tipo.ANUAL:
        return []
    from apps.acompanhamento.selectors import situacoes_em_lote

    trimestrais = [
        vinculo.objetivo_trimestral
        for vinculo in VinculoObjetivo.objects.filter(objetivo_anual=objetivo).select_related(
            "objetivo_trimestral__ciclo", "objetivo_trimestral__owner"
        )
    ]
    krs = list(
        ResultadoChave.objects.filter(objetivo__in=trimestrais)
        .exclude(status=ResultadoChave.Status.CANCELADO)
        .select_related("objetivo__ciclo")
        .order_by("id")
    )
    situacoes_em_lote(krs)
    for trimestral in trimestrais:
        trimestral.krs_lista = [kr for kr in krs if kr.objetivo_id == trimestral.pk]

    colunas = []
    ciclos = {c.trimestre: c for c in objetivo.ciclo.trimestres.filter(arquivado_em__isnull=True)}
    for numero, rotulo in Ciclo.TRIMESTRES:
        colunas.append(
            {
                "rotulo": rotulo,
                "ciclo": ciclos.get(numero),
                "objetivos": sorted(
                    (o for o in trimestrais if o.ciclo.trimestre == numero),
                    key=lambda o: o.chave_titulo,
                ),
            }
        )
    return colunas
